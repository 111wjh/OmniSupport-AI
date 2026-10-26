
import json
from typing import Any
from typing import Any, Callable

async def collect_streamed_response(
stream,
on_text_delta: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """收集 Qwen 流式输出，拼接文本和工具调用。"""

    content_parts = []
    tool_calls = {}

    async for chunk in stream:
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        # 1. 收集普通文本
        if delta.content:
            content_parts.append(delta.content)

            if on_text_delta is not None:
                on_text_delta(delta.content)
        # 2. 收集工具调用
        for tool in delta.tool_calls or []:
            index = tool.index

            if index not in tool_calls:
                tool_calls[index] = {
                    "id": "",
                    "type": "function",
                    "function": {
                        "name": "",
                        "arguments": "",
                    },
                }

            current = tool_calls[index]

            if tool.id:
                current["id"] += tool.id

            if tool.function:
                if tool.function.name:
                    current["function"]["name"] += tool.function.name

                if tool.function.arguments:
                    current["function"]["arguments"] += (
                        tool.function.arguments
                    )

    # 3. 组装完整助手消息
    content = "".join(content_parts)
    result = {
        "role": "assistant",
        "content": content or None,
    }

    # 4. 如果模型调用了工具，则附加完整工具信息
    if tool_calls:
        ordered_calls = [
            tool_calls[index]
            for index in sorted(tool_calls)
        ]

        # 检查工具调用是否拼接完整
        for call in ordered_calls:
            if not call["id"] or not call["function"]["name"]:
                raise ValueError("流式工具调用缺少 ID 或名称")

            json.loads(call["function"]["arguments"])

        result["tool_calls"] = ordered_calls

    return result
