
import json
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.services.order_service import (
    get_order_by_number,
    get_latest_order_for_customer,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import logging
from app.services.rag_service import retrieve_relevant_knowledge
from app.mcp_client.client import call_mcp_tool

logger = logging.getLogger("uvicorn.error")

class OrderStatusArguments(BaseModel):
    """订单查询工具的参数。"""

    model_config = ConfigDict(extra="forbid")

    order_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9-]+$",
    )

class KnowledgeSearchArguments(BaseModel):
    """知识库检索工具的参数。"""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=500,
    )


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
) -> dict:
    """统一执行 Agent 工具。"""

    logger.info(
    "Agent tool requested: %s",
    tool_name,
    )

    # 1. 执行知识库检索工具
    if tool_name == "search_knowledge":
        try:
            args = KnowledgeSearchArguments.model_validate_json(
                arguments
            )
        except ValidationError:
            return {
                "success": False,
                "error": "invalid_arguments",
                "message": "知识检索参数不合法",
            }

        try:
            results = await retrieve_relevant_knowledge(
                question=args.query,
                recall_k=5,
                top_n=3,
            )
        except Exception:
            logger.exception("Knowledge search failed")
            return {
                "success": False,
                "error": "knowledge_search_failed",
                "message": "知识库检索暂时不可用，请稍后再试。",
            }

        return {
            "success": True,
            "data": results,
        }


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




    # 2. 其他未注册的工具一律拒绝
    if tool_name != "get_order_status":
        return {
            "success": False,
            "error": "unknown_tool",
            "message": "不支持的工具",
        }


    # 2. 验证模型传来的 JSON 参数
    try:
        args = OrderStatusArguments.model_validate_json(
            arguments
        )
    except ValidationError:
        return {
            "success": False,
            "error": "invalid_arguments",
            "message": "订单查询参数不合法",
        }


    # 3. 未提供经过验证的客户身份时，拒绝查询
    if customer_id is None:
        return {
            "success": False,
            "error": "authentication_required",
            "message": "订单查询需要先登录。",
        }


    # 4. 根据参数查询指定订单或最近一笔订单
    async with AsyncSessionLocal() as session:
        if args.order_number is not None:
            order = await get_order_by_number(
                session=session,
                order_number=args.order_number,
                customer_id=customer_id,
            )
        else:
            order = await get_latest_order_for_customer(
                session=session,
                customer_id=customer_id,
            )

    # 5. 处理订单不存在的情况
    if order is None:
        if args.order_number is None:
            return {
                "success": False,
                "error": "no_orders_found",
                "message": "当前账号暂时没有可查询的订单。",
            }

        return {
            "success": False,
            "error": "order_not_found",
            "message": "未找到该订单，或当前账号无权查看。",
        }


    # 6. 返回当前客户有权查看的订单信息
    return {
        "success": True,
        "data": {
            "order_number": order.order_number,
            "product_name": order.product_name,
            "total_amount": str(order.total_amount),
            "status": order.status,
            "purchased_at": order.purchased_at.isoformat(),
        },
    }
