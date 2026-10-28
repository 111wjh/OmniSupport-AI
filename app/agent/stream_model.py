
from typing import Any, Callable

from openai import AsyncOpenAI

from app.agent.stream_parser import collect_streamed_response
from app.core.config import get_settings




async def request_streamed_model(
    messages: list[dict[str, Any]],
    on_text_delta: Callable[[str], None] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = "auto",
) -> dict[str, Any]:

    """流式调用 Qwen，返回完整的助手消息。"""

    settings = get_settings()

    if not all([
        settings.LLM_API_KEY,
        settings.LLM_MODEL,
        settings.LLM_BASE_URL,
    ]):
        raise ValueError("大模型配置不完整")
    if tools is None:
        raise ValueError("流式模型调用必须提供工具列表")

    async with AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=60.0,
        max_retries=1,
    ) as client:

        stream = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
            extra_body={
                "enable_thinking": False,
            },
        )

        return await collect_streamed_response(
            stream,
            on_text_delta=on_text_delta,
            )