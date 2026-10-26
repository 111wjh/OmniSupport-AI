
from typing import Any


def convert_mcp_tool_to_qwen(tool: Any) -> dict:
    """将 MCP 工具定义转换为 Qwen Function Calling 格式。"""

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }
