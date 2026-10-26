
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from app.core.auth import get_current_customer
from app.models.customer import Customer
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import (
    generate_reply_and_save,
    ConversationBusyError,
    ConversationLockExpiredError,
)
from app.services.conversation_service import resolve_conversation_id
from openai import APITimeoutError, APIConnectionError, APIStatusError
from app.services.conversation_service import delete_empty_conversation
import logging
import asyncio

from app.api.sse import create_sse_response, format_sse_event

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["Chat"],
)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
) -> ChatResponse:
    """处理用户聊天请求。"""

    # 判断是否属于首次聊天
    is_new_conversation = request.conversation_id is None

    # 创建新会话或验证已有会话
    try:
        conversation_id = await resolve_conversation_id(
            request.conversation_id,
            customer_id=current_customer.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="会话不存在",
        ) from exc

    try:
        # 读取历史、调用 Qwen、保存聊天记录
        reply = await generate_reply_and_save(
            message=request.message,
            conversation_id=conversation_id,
            customer_id=current_customer.id,
            )

    except Exception as exc:
        # 仅对本次新创建的空会话执行清理
        if is_new_conversation:
            try:
                await delete_empty_conversation(conversation_id)
            except Exception:
                # 清理失败不能覆盖最初的聊天异常
                import logging
                logging.getLogger(__name__).exception(
                    "清理空会话失败"
                )
        if isinstance(exc, ConversationBusyError):
            raise HTTPException(
                status_code=409,
                detail="会话正在处理中，请稍后重试",
            ) from exc

        if isinstance(exc, ConversationLockExpiredError):
            raise HTTPException(
                status_code=409,
                detail="会话处理权已失效，请重新发送消息",
            ) from exc
        # Qwen 超时
        if isinstance(exc, APITimeoutError):
            raise HTTPException(
                status_code=504,
                detail="AI 服务响应超时，请稍后重试",
            ) from exc

        # Qwen 网络连接或 API 状态异常
        if isinstance(exc, (APIConnectionError, APIStatusError)):
            raise HTTPException(
                status_code=502,
                detail="AI 服务暂时不可用，请稍后重试",
            ) from exc

        # 未知异常：记录堆栈后继续抛出
        logger.exception(
            "聊天接口发生未处理异常"
        )
        raise

    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
    )



@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
):
    """通过 SSE 流式返回 Agent 回复。"""

    is_new_conversation = request.conversation_id is None

    # 先验证或创建会话
    try:
        conversation_id = await resolve_conversation_id(
            request.conversation_id,
            customer_id=current_customer.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="会话不存在",
        ) from exc

    async def event_generator():
        queue: asyncio.Queue[object] = asyncio.Queue()
        sentinel = object()
        succeeded = False

        # Agent 的同步文本回调将文本放入异步队列
        def on_text_delta(text: str) -> None:
            queue.put_nowait(text)

        async def run_chat():
            try:
                await generate_reply_and_save(
                    message=request.message,
                    conversation_id=conversation_id,
                    customer_id=current_customer.id,
                    on_text_delta=on_text_delta,
                )
            finally:
                # 无论成功还是失败，都通知消费者结束读取
                queue.put_nowait(sentinel)

        task = asyncio.create_task(run_chat())

        try:
            # 逐个读取文本片段并转换为 SSE 事件
            while True:
                item = await queue.get()

                if item is sentinel:
                    break

                yield format_sse_event(
                    "token",
                    {"content": item},
                )

            # 确认聊天服务已经完成，包括消息事务保存
            await task
            succeeded = True

            yield format_sse_event(
                "done",
                {
                    "conversation_id": str(conversation_id),
                },
            )

        except asyncio.CancelledError:
            # 客户端断开时，进入 finally 清理任务
            raise

        except Exception as exc:
            if isinstance(exc, ConversationBusyError):
                detail = "会话正在处理中，请稍后重试"

            elif isinstance(exc, ConversationLockExpiredError):
                detail = "会话处理权已失效，请重新发送消息"

            elif isinstance(exc, APITimeoutError):
                detail = "AI 服务响应超时，请稍后重试"

            elif isinstance(exc, (APIConnectionError, APIStatusError)):
                detail = "AI 服务暂时不可用，请稍后重试"

            else:
                logger.exception("流式聊天接口发生未处理异常")
                detail = "聊天服务暂时不可用，请稍后重试"

            yield format_sse_event(
                "error",
                {"detail": detail},
            )

        finally:
             # 客户端断开时取消尚未完成的聊天任务
            if not task.done():
                task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                # 异常已在上面的处理分支记录或转换
                pass

            # 仅清理本次新建且未成功完成的空会话
            if is_new_conversation and not succeeded:
                try:
                    await delete_empty_conversation(
                        conversation_id
                    )
                except Exception:
                    logger.exception("清理流式聊天空会话失败")

    return create_sse_response(event_generator())
