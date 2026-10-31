
import asyncio
import copy
import logging
import sys
import time
from mcp import Client, StdioServerParameters

from app.mcp_client.schema import convert_mcp_tool_to_qwen
from app.tools.definitions import AGENT_TOOLS


logger = logging.getLogger(__name__)
# 只允许向 Agent 暴露经过审核的 MCP 工具
ALLOWED_MCP_TOOLS = {
    "get_product_info",
    "list_products",
}

# MCP 工具目录缓存有效期：300 秒
MCP_TOOL_CACHE_TTL_SECONDS = 300
#失败重试
MCP_TOOL_CACHE_FAILURE_TTL_SECONDS = 30
#超时
MCP_TOOL_DISCOVERY_TIMEOUT_SECONDS = 15
_cached_mcp_tools: list[dict] | None = None
_mcp_tool_cache_expires_at = 0.0
_mcp_tool_cache_lock = asyncio.Lock()



async def discover_mcp_tools() -> list[dict]:
    """发现并转换经过白名单过滤的 MCP 工具定义。"""

    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server.server"],
    )

    # 限制 MCP Server 启动及工具发现的总等待时间
    async with asyncio.timeout(
        MCP_TOOL_DISCOVERY_TIMEOUT_SECONDS
    ):
        async with Client(server) as client:
            result = await client.list_tools()

            tools = []

            for tool in result.tools:
                # 未在白名单中的工具不能提供给模型
                if tool.name not in ALLOWED_MCP_TOOLS:
                    continue

                qwen_tool = convert_mcp_tool_to_qwen(tool)
                tools.append(qwen_tool)

            return tools



async def get_cached_mcp_tools() -> list[dict]:
    """获取缓存的 MCP 工具目录，过期后重新发现。"""

    global _cached_mcp_tools
    global _mcp_tool_cache_expires_at

    # 1. 缓存仍有效时，直接返回副本
    if (
        _cached_mcp_tools is not None
        and time.monotonic() < _mcp_tool_cache_expires_at
    ):
        return copy.deepcopy(_cached_mcp_tools)

    # 2. 防止并发请求同时启动多个发现进程
    async with _mcp_tool_cache_lock:
        # 获取锁后再次检查，避免重复发现
        if (
            _cached_mcp_tools is not None
            and time.monotonic() < _mcp_tool_cache_expires_at
        ):
            return copy.deepcopy(_cached_mcp_tools)

        # 3. 缓存不存在或已过期，重新发现工具

        try:
            tools = await discover_mcp_tools()

        except Exception:
            logger.exception(
                "MCP 工具发现失败，暂时只使用本地工具"
            )

            # 缓存空的 MCP 工具列表，避免频繁重试
            _cached_mcp_tools = []
            _mcp_tool_cache_expires_at = (
                time.monotonic()
                + MCP_TOOL_CACHE_FAILURE_TTL_SECONDS
            )

            return []

        # MCP 工具发现成功，缓存完整工具列表
        _cached_mcp_tools = copy.deepcopy(tools)
        _mcp_tool_cache_expires_at = (
            time.monotonic() + MCP_TOOL_CACHE_TTL_SECONDS
        )

        return copy.deepcopy(_cached_mcp_tools)



async def build_agent_tools() -> list[dict]:
    """合并本地工具与经过白名单过滤的 MCP 工具。"""

        # 使用统一维护的本地工具列表，返回独立副本。
    local_tools = copy.deepcopy(AGENT_TOOLS)

    # 2. 获取缓存的 MCP 工具
    mcp_tools = await get_cached_mcp_tools()

    # 3. 合并两个工具列表
    all_tools = local_tools + mcp_tools

    # 4. 防止工具名称重复
    tool_names = [
        tool["function"]["name"]
        for tool in all_tools
    ]

    if len(tool_names) != len(set(tool_names)):
        raise ValueError("Agent 工具名称存在重复")

    return all_tools
