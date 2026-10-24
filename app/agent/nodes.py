
from typing import Any

from openai import AsyncOpenAI
import logging
from app.agent.state import AgentState
from app.core.config import get_settings
from app.tools.definitions import AGENT_TOOLS
import json

from app.tools.executor import execute_tool
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

    # 创建异步大模型客户端

    logger.info(
        "LangGraph 模型调用开始：model=%s, call_number=%s",
        settings.LLM_MODEL,
        state["model_calls"] + 1,
    )

    try:
        async with AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=60.0,
            max_retries=1,
        ) as client:

            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=state["messages"],
                tools=AGENT_TOOLS,
                tool_choice="auto",
                extra_body={
                    "enable_thinking": False,
                },
            )

    except Exception:
        logger.exception(
            "LangGraph 模型调用失败：model=%s, call_number=%s",
            settings.LLM_MODEL,
            state["model_calls"] + 1,
        )
        raise

    logger.info(
        "LangGraph 模型调用成功：model=%s, call_number=%s",
        settings.LLM_MODEL,
        state["model_calls"] + 1,
    )


    # 获取模型返回的助手消息
    assistant_message = response.choices[0].message

    # 如果既没有工具调用，也没有有效文本，则报错
    if not assistant_message.tool_calls and not assistant_message.content:
        raise ValueError("大模型没有返回有效文本")

    # 将助手消息追加到 LangGraph 的共享状态
    return {
        "messages": [
            assistant_message.model_dump(exclude_none=True)
        ],
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

    for tool_call in tool_calls:
        function = tool_call["function"]

        
        tool_name = function["name"]

        logger.info(
            "LangGraph 工具执行开始：tool=%s",
            tool_name,
        )

        try:
            tool_result = await execute_tool(
                tool_name=tool_name,
                arguments=function["arguments"],
                customer_id=state["customer_id"],
            )
        except Exception:
            logger.exception(
                "LangGraph 工具执行异常：tool=%s",
                tool_name,
            )

            tool_result = {
                "success": False,
                "error": "tool_execution_failed",
                "message": "工具执行暂时失败，请稍后重试。",
            }


        if tool_result.get("success") is True:
            logger.info(
                "LangGraph 工具执行成功：tool=%s",
                tool_name,
            )
        else:
            logger.warning(
                "LangGraph 工具执行失败：tool=%s, error=%s",
                tool_name,
                tool_result.get("error", "unknown_error"),
            )


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
