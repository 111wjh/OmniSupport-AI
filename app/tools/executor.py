import logging
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.mcp_client.client import call_mcp_tool
from app.tools.context import ToolContext
from app.tools.registry import REGISTERED_TOOLS


logger = logging.getLogger("uvicorn.error")


class ProductInfoArguments(BaseModel):
    """MCP 商品查询工具的参数。"""

    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(
        min_length=1,
        max_length=100,
    )


class ListProductsArguments(BaseModel):
    """MCP 商品列表查询工具的参数。"""

    model_config = ConfigDict(extra="forbid")


async def execute_tool(
    tool_name: str,
    arguments: str,
    customer_id: UUID | None = None,
    conversation_id: UUID | None = None,
    ticket_idempotency_key: str | None = None,
) -> dict:
    """统一执行 Agent 工具。"""

    logger.info("Agent tool requested: %s", tool_name)

    # 按名称分发已注册的本地工具。
    registered = REGISTERED_TOOLS.get(tool_name)
    if registered is not None:
        context = ToolContext(
            customer_id=customer_id,
            conversation_id=conversation_id,
            ticket_idempotency_key=ticket_idempotency_key,
        )
        return await registered.handler(arguments, context)

    # MCP 工具统一分发
    mcp_argument_models = {
        "get_product_info": ProductInfoArguments,
        "list_products": ListProductsArguments,
    }

    # 根据工具名称找到对应的参数验证模型
    argument_model = mcp_argument_models.get(tool_name)

    if argument_model is not None:
        # 1. 验证大模型传入的 JSON 参数
        try:
            args = argument_model.model_validate_json(
                arguments
            )
        except ValidationError:
            return {
                "success": False,
                "error": "invalid_arguments",
                "message": "MCP 工具参数不合法",
            }

        # 2. 使用通用 MCP Client 执行工具
        try:
            result = await call_mcp_tool(
                tool_name=tool_name,
                arguments=args.model_dump(),
            )

            return result

        except Exception:
            logger.exception(
                "MCP tool execution failed: %s",
                tool_name,
            )

            return {
                "success": False,
                "error": "mcp_tool_failed",
                "message": "MCP 工具暂时不可用，请稍后重试。",
            }

    return {
        "success": False,
        "error": "unknown_tool",
        "message": "不支持的工具",
    }
