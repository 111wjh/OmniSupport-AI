
from typing import Any
import asyncio
from openai import AsyncOpenAI
import logging
from app.agent.state import AgentState
from app.core.config import get_settings
import json
import time
from app.tools.executor import execute_tool
from app.core.request_context import get_request_id
from app.core.langfuse_client import get_langfuse_client
from app.agent.stream_model import request_streamed_model
#自定义事件写入器。
from langgraph.config import get_stream_writer
from app.mcp_client.catalog import build_agent_tools


logger = logging.getLogger(__name__)


async def call_model(
    state: AgentState,
) -> dict[str, Any]:
    """调用大模型，生成助手回复或工具调用请求。"""
    # 最多调用大模型 4 次，防止工具循环失控
    if state["model_calls"] >= 4:
        raise ValueError("大模型工具调用轮次超过限制")
    settings = get_settings()

    # 检查大模型配置是否完整
    if not all([
        settings.LLM_API_KEY,
        settings.LLM_MODEL,
        settings.LLM_BASE_URL,
    ]):
        raise ValueError("大模型配置不完整，请检查 .env 文件")

    # 动态获取本地工具和经过白名单审核的 MCP 工具
    agent_tools = await build_agent_tools()
    # 创建异步大模型客户端

    logger.info(
    "LangGraph 模型调用开始：request_id=%s, model=%s, call_number=%s",
    get_request_id(),
    settings.LLM_MODEL,
    state["model_calls"] + 1,
)
    start_time = time.perf_counter()

    try:
        langfuse = get_langfuse_client()

        with langfuse.start_as_current_observation(
            as_type="generation",
            name="Qwen 模型调用",
            model=settings.LLM_MODEL,
            metadata={
                "request_id": get_request_id() or "local",
                "call_number": state["model_calls"] + 1,
                "stream_enabled": state.get("stream_enabled", False),
            },
        ) as generation:

            if state.get("stream_enabled", False):
                writer = get_stream_writer()

                # 暂存本轮模型生成的文本片段
                pending_text_parts = []

                def collect_text_delta(text: str) -> None:
                    pending_text_parts.append(text)

                assistant_message = await request_streamed_model(
                    messages=state["messages"],
                    on_text_delta=collect_text_delta,
                    tools=agent_tools,
                )

                # 只有本轮没有调用工具，才允许发送文本
                if not assistant_message.get("tool_calls"):
                    for text in pending_text_parts:
                        writer({
                            "type": "token",
                            "content": text,
                        })


            else:
                # 非流式模式：保留原来的 Qwen 调用
                async with AsyncOpenAI(
                    api_key=settings.LLM_API_KEY,
                    base_url=settings.LLM_BASE_URL,
                    timeout=60.0,
                    max_retries=1,
                ) as client:

                    response = await client.chat.completions.create(
                        model=settings.LLM_MODEL,
                        messages=state["messages"],
                        tools=agent_tools,
                        tool_choice="auto",
                        extra_body={
                            "enable_thinking": False,
                        },
                    )

                assistant_message = (
                    response.choices[0].message.model_dump(
                        exclude_none=True
                    )
                )

                # 当前仅在非流式模式记录 Token 用量
                if response.usage is not None:
                    generation.update(
                        usage_details={
                            "input": response.usage.prompt_tokens,
                            "output": response.usage.completion_tokens,
                        }
                    )

            # 两种模式统一记录执行状态
            generation.update(
                output={
                    "status": "success",
                    "has_tool_calls": bool(
                        assistant_message.get("tool_calls")
                    ),
                },
            )

    except asyncio.CancelledError:
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.warning(
            "LangGraph 模型调用被取消：request_id=%s, "
            "model=%s, call_number=%s, duration_ms=%.2f",
            get_request_id(),
            settings.LLM_MODEL,
            state["model_calls"] + 1,
            duration_ms,
        )

        raise
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000

        
        logger.exception(
            "LangGraph 模型调用失败：request_id=%s, model=%s, call_number=%s, duration_ms=%.2f",
            get_request_id(),
            settings.LLM_MODEL,
            state["model_calls"] + 1,
            duration_ms,
        )

        raise


    duration_ms = (time.perf_counter() - start_time) * 1000

    
    logger.info(
        "LangGraph 模型调用成功：request_id=%s, model=%s, call_number=%s, duration_ms=%.2f",
        get_request_id(),
        settings.LLM_MODEL,
        state["model_calls"] + 1,
        duration_ms,
    )


    # 如果既没有工具调用，也没有有效文本，则报错
    if not assistant_message.get("tool_calls") and not assistant_message.get("content"):
        raise ValueError("大模型没有返回有效文本")

    # 将助手消息追加到 LangGraph 的共享状态
    return {
    "messages": [assistant_message],
    "model_calls": state["model_calls"] + 1,
    }

async def execute_tools(
    state: AgentState,
) -> dict[str, Any]:
    """执行模型请求的工具，并将结果写回共享状态。"""

    # 1. 获取当前会话的消息
    messages = state["messages"]

    if not messages:
        raise ValueError("Agent 消息列表为空")

    # 2. 获取模型刚刚生成的助手消息
    assistant_message = messages[-1]
    tool_calls = assistant_message.get("tool_calls")

    if not tool_calls:
        raise ValueError("当前助手消息没有工具调用请求")

    # 3. 逐个执行模型请求的工具
    tool_messages = []
    submitted_refund_id = None

    for tool_call in tool_calls:
        function = tool_call["function"]

        
        tool_name = function["name"]

        logger.info(
        "LangGraph 工具执行开始：request_id=%s, tool=%s",
        get_request_id(),
        tool_name,
        )
        
        start_time = time.perf_counter()

        # 为当前工具创建独立的 Langfuse Tool 记录
        langfuse = get_langfuse_client()

        with langfuse.start_as_current_observation(
            as_type="tool",
            name=tool_name,
            metadata={
                "request_id": get_request_id() or "local",
            },
        ) as tool_span:
            try:
                tool_result = await execute_tool(
                    tool_name=tool_name,
                    arguments=function["arguments"],
                    customer_id=state["customer_id"],
                )
            except Exception:
                logger.exception(
                    "LangGraph 工具执行异常：request_id=%s, tool=%s",
                    get_request_id(),
                    tool_name,
                )

                tool_result = {
                    "success": False,
                    "error": "tool_execution_failed",
                    "message": "工具执行暂时失败，请稍后重试。",
                }

            # 只记录执行状态，不上传工具参数或业务结果
            success = tool_result.get("success") is True

            tool_span.update(
                output={
                    "success": success,
                    "error": tool_result.get("error") if not success else None,
                },
                level="DEFAULT" if success else "ERROR",
            )

        duration_ms = (time.perf_counter() - start_time) * 1000

        
        if tool_result.get("success") is True:
            logger.info(
                "LangGraph 工具执行成功：request_id=%s, tool=%s, duration_ms=%.2f",
                get_request_id(),
                tool_name,
                duration_ms,
            )
        else:
            logger.warning(
                "LangGraph 工具执行失败：request_id=%s, tool=%s, error=%s, duration_ms=%.2f",
                get_request_id(),
                tool_name,
                tool_result.get("error", "unknown_error"),
                duration_ms,
            )

                # 仅在本次只调用退款提交工具，且提交成功时，
        # 记录申请编号，供后续路由使用。
        if (
            len(tool_calls) == 1
            and tool_name == "submit_refund_request"
            and tool_result.get("success") is True
        ):
            refund_data = tool_result.get("data")

            if (
                isinstance(refund_data, dict)
                and refund_data.get("status") == "pending"
            ):
                refund_id = refund_data.get("id")

                if isinstance(refund_id, str) and refund_id.strip():
                    submitted_refund_id = refund_id
        # 4. 将执行结果转换为模型可以读取的工具消息
        tool_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(
                tool_result,
                ensure_ascii=False,
            ),
        })

    # 5. 将工具结果追加到 LangGraph 状态
    return {
        "messages": tool_messages,
        "submitted_refund_id": submitted_refund_id,
    }




def route_after_model(state: AgentState) -> str:
    """根据模型输出和调用次数决定下一步路由。"""

    assistant_message = state["messages"][-1]

    # 没有工具调用，直接结束
    if not assistant_message.get("tool_calls"):
        return "end"

    # 已达到上限，不再执行新的工具调用
    if state["model_calls"] >= 4:
        return "limit"

    # 还有剩余次数，正常执行工具
    return "tools"


def handle_call_limit(
    state: AgentState,
) -> dict[str, Any]:
    """达到调用上限后，返回明确的兜底回复。"""

    return {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "抱歉，本次请求已达到工具调用次数上限，"
                    "暂时无法继续处理。请稍后重试，"
                    "或补充更明确的信息。"
                ),
            }
        ]
    }


def route_after_tools(state: AgentState) -> str:
    """根据退款提交结果，决定工具执行后的下一步。"""

    if state.get("submitted_refund_id"):
        return "refund_submitted"

    return "model"


def handle_refund_submitted(
    state: AgentState,
) -> dict[str, Any]:
    """根据真实提交结果，生成待审核回复。"""

    refund_id = state.get("submitted_refund_id")

    if not isinstance(refund_id, str) or not refund_id.strip():
        raise ValueError("退款提交回复节点缺少申请编号")

    reply = (
        "退款申请已成功提交，提交时状态为待审核。\n"
        f"申请编号：{refund_id}\n"
        "后续由有权限的工作人员审核；"
        "审核通过后，还需单独执行模拟退款。\n"
        "你可以稍后询问审核进度或退款执行结果。"
    )

    logger.info(
        "LangGraph 退款提交回复节点：request_id=%s",
        get_request_id(),
    )

    if state.get("stream_enabled", False):
        writer = get_stream_writer()
        writer({
            "type": "token",
            "content": reply,
        })

    return {
        "messages": [
            {
                "role": "assistant",
                "content": reply,
            }
        ],
        "submitted_refund_id": None,
    }
