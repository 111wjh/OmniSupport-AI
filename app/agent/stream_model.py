
from typing import Any, Callable

from openai import AsyncOpenAI

from app.agent.stream_parser import collect_streamed_response
from app.core.config import get_settings
from app.tools.definitions import AGENT_TOOLS


async def request_streamed_model(
    messages: list[dict[str, Any]],
    on_text_delta: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """流式调用 Qwen，返回完整的助手消息。"""

    settings = get_settings()

    if not all([
        settings.LLM_API_KEY,
        settings.LLM_MODEL,
        settings.LLM_BASE_URL,
    ]):
        raise ValueError("大模型配置不完整")

    async with AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=60.0,
        max_retries=1,
    ) as client:

        stream = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            stream=True,
            extra_body={
                "enable_thinking": False,
            },
        )

        return await collect_streamed_response(
            stream,
            on_text_delta=on_text_delta,
            )