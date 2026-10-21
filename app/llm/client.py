
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.prompts.customer_service import SYSTEM_PROMPT
import json
from typing import Any

from app.tools.definitions import AGENT_TOOLS
from app.tools.executor import execute_tool
from uuid import UUID


def build_llm_messages(
    message: str,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """将系统提示词、历史消息和当前问题组合起来。"""

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # 添加历史聊天记录
    if history:
        messages.extend(history)

    # 添加用户当前的问题
    messages.append(
        {
            "role": "user",
            "content": message,
        }
    )

    return messages


async def generate_llm_reply(
    message: str,
    history: list[dict[str, str]] | None = None,
    customer_id: UUID | None = None,
) -> str:
    """调用大模型，并处理工具调用及最终回复。"""

    settings = get_settings()

    if not all([
        settings.LLM_API_KEY,
        settings.LLM_MODEL,
        settings.LLM_BASE_URL,
    ]):
        raise ValueError("大模型配置不完整，请检查 .env 文件")

    messages = build_llm_messages(
        message=message,
        history=history,
    )

    async with AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=60.0,
        max_retries=1,
    ) as client:

        # 最多进行 4 轮模型请求，防止工具调用无限循环
        for _ in range(4):
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                tools=AGENT_TOOLS,
                tool_choice="auto",
                extra_body={
                    "enable_thinking": False,
                },
            )

            assistant_message = response.choices[0].message

            # 模型没有请求调用工具，说明可以返回最终回答
            if not assistant_message.tool_calls:
                reply = assistant_message.content

                if not reply:
                    raise ValueError("大模型没有返回有效文本")

                return reply

            # 保存模型提出的工具调用请求
            messages.append(
                assistant_message.model_dump(exclude_none=True)
            )

            # 由后端执行工具，并把结果交还模型
            for tool_call in assistant_message.tool_calls:
                tool_result = await execute_tool(
                    tool_name=tool_call.function.name,
                    arguments=tool_call.function.arguments,
                    customer_id=customer_id,
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        tool_result,
                        ensure_ascii=False,
                    ),
                })

    raise ValueError("大模型工具调用轮次超过限制")

