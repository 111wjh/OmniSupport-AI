
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

        # 未知异常继续抛出，不隐藏真正的问题
        raise

    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
    )
