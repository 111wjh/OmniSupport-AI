
import json
import sys

from mcp import Client, StdioServerParameters
from mcp.types import TextContent
from typing import Any

from app.mcp_client.catalog import ALLOWED_MCP_TOOLS
import asyncio
MCP_TOOL_TIMEOUT_SECONDS = 30

async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict:
    """通用 MCP 工具调用入口。"""

    # 1. 验证工具是否经过授权
    if tool_name not in ALLOWED_MCP_TOOLS:
        raise ValueError("不允许调用该 MCP 工具")

    # 2. 配置 MCP Server
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server.server"],
    )

    
    # 3. 限制 MCP 连接和工具调用的总等待时间
    try:
        async with asyncio.timeout(MCP_TOOL_TIMEOUT_SECONDS):
            async with Client(server) as client:
                result = await client.call_tool(
                    tool_name,
                    arguments=arguments,
                )

                if result.is_error:
                    raise RuntimeError("MCP 工具执行失败")

                # 4. 解析工具返回结果
                for block in result.content:
                    if isinstance(block, TextContent):
                        data = json.loads(block.text)

                        if not isinstance(data, dict):
                            raise ValueError("MCP 返回格式不正确")

                        return data

    except TimeoutError as exc:
        raise TimeoutError(
            f"MCP 工具调用超时：{tool_name}"
        ) from exc


    raise ValueError("MCP 工具没有返回有效数据")
