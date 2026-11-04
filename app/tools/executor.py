
import json
from uuid import UUID

from app.db.session import AsyncSessionLocal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import logging
from app.tools.registry import REGISTERED_TOOLS
from app.mcp_client.client import call_mcp_tool
from app.schemas.refund import (
    RefundCreateRequest,
    RefundExecutionResponse,
)
from app.services.refund_execution_service import (
    get_customer_refund_execution,
)

from app.services.refund_service import (
    create_refund_request,
    list_customer_refund_requests,
    RefundOrderNotFoundError,
    RefundNotAllowedError,
    RefundAlreadyExistsError,
)
from app.tools.ticket_tools import execute_create_support_ticket
from app.tools.context import ToolContext
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

class ListMyRefundsArguments(BaseModel):
    """查询当前客户退款申请的参数。"""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SubmitRefundRequestArguments(BaseModel):
    """提交退款申请的参数。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    order_number: str = Field(
        min_length=1,
        max_length=50,
    )

    reason: str = Field(
        min_length=5,
        max_length=2000,
    )

class GetRefundExecutionArguments(BaseModel):
    """查询退款执行结果的参数。"""

    model_config = ConfigDict(extra="forbid")

    refund_request_id: UUID

async def execute_tool(
    tool_name: str,
    arguments: str,
    customer_id: UUID | None = None,
    conversation_id: UUID | None = None,
    ticket_idempotency_key: str | None = None,
) -> dict:
    """统一执行 Agent 工具。"""

    logger.info(
    "Agent tool requested: %s",
    tool_name,
    )
    # 为当前客户创建人工服务工单。
    if tool_name == "create_support_ticket":
        return await execute_create_support_ticket(
            arguments=arguments,
            customer_id=customer_id,
            conversation_id=conversation_id,
            idempotency_key=ticket_idempotency_key,
        )

    # 按名称分发已注册的本地工具。
    registered = REGISTERED_TOOLS.get(tool_name)
    if registered is not None:
        context = ToolContext(customer_id=customer_id)
        return await registered.handler(arguments, context)

    # 查询当前客户自己的退款申请
    if tool_name == "list_my_refunds":
        try:
            args = ListMyRefundsArguments.model_validate_json(
                arguments
            )
        except ValidationError:
            return {
                "success": False,
                "error": "invalid_arguments",
                "message": "退款查询参数不合法。",
            }

        if customer_id is None:
            return {
                "success": False,
                "error": "authentication_required",
                "message": "请先登录，再查询退款申请。",
            }

        try:
            async with AsyncSessionLocal() as session:
                items, total = await list_customer_refund_requests(
                    session=session,
                    customer_id=customer_id,
                    limit=args.limit,
                    offset=args.offset,
                )

            return {
                "success": True,
                "data": {
                    "items": [
                        {
                            "id": str(item.id),
                            "order_id": str(item.order_id),
                            "reason": item.reason,
                            "status": item.status,
                            "review_comment": item.review_comment,
                            "requested_at": (
                                item.requested_at.isoformat()
                            ),
                            "reviewed_at": (
                                item.reviewed_at.isoformat()
                                if item.reviewed_at
                                else None
                            ),
                        }
                        for item in items
                    ],
                    "total": total,
                    "limit": args.limit,
                    "offset": args.offset,
                },
            }

        except Exception:
            logger.exception("Refund list tool failed")
            return {
                "success": False,
                "error": "refund_list_failed",
                "message": "退款申请查询暂时不可用，请稍后重试。",
            }

    # 为当前客户提交退款申请
    if tool_name == "submit_refund_request":
        try:
            args = SubmitRefundRequestArguments.model_validate_json(
                arguments
            )
        except ValidationError:
            return {
                "success": False,
                "error": "invalid_arguments",
                "message": "退款申请参数不合法，请检查订单编号和退款原因。",
            }

        if customer_id is None:
            return {
                "success": False,
                "error": "authentication_required",
                "message": "请先登录，再提交退款申请。",
            }

        data = RefundCreateRequest(
            order_number=args.order_number,
            reason=args.reason,
        )

        try:
            async with AsyncSessionLocal() as session:
                refund_request = await create_refund_request(
                    session=session,
                    customer_id=customer_id,
                    data=data,
                )

                return {
                    "success": True,
                    "data": {
                        "id": str(refund_request.id),
                        "order_id": str(refund_request.order_id),
                        "status": refund_request.status,
                        "reason": refund_request.reason,
                        "requested_at": (
                            refund_request.requested_at.isoformat()
                        ),
                    },
                    "message": (
                        "退款申请已提交，等待工作人员审核。"
                    ),
                }

        except RefundOrderNotFoundError:
            return {
                "success": False,
                "error": "order_not_found",
                "message": "未找到该订单，或当前账号无权申请退款。",
            }

        except RefundNotAllowedError as exc:
            return {
                "success": False,
                "error": "refund_not_allowed",
                "message": str(exc),
            }

        except RefundAlreadyExistsError as exc:
            return {
                "success": False,
                "error": "refund_already_exists",
                "message": str(exc),
            }

        except Exception:
            logger.exception("Refund submission tool failed")
            return {
                "success": False,
                "error": "refund_submission_failed",
                "message": "退款申请提交失败，请稍后重试。",
            }

        # 查询当前客户自己的退款执行结果
    if tool_name == "get_refund_execution":
        try:
            args = GetRefundExecutionArguments.model_validate_json(
                arguments
            )
        except ValidationError:
            return {
                "success": False,
                "error": "invalid_arguments",
                "message": "退款申请编号格式不合法。",
            }

        if customer_id is None:
            return {
                "success": False,
                "error": "authentication_required",
                "message": "请先登录，再查询退款执行结果。",
            }

        try:
            async with AsyncSessionLocal() as session:
                execution = await get_customer_refund_execution(
                    session=session,
                    refund_request_id=args.refund_request_id,
                    customer_id=customer_id,
                )

                if execution is None:
                    return {
                        "success": False,
                        "error": "refund_execution_not_found",
                        "message": (
                            "未找到可查看的退款执行记录。"
                            "可先查询退款申请的审核状态；"
                            "审核通过不代表已经执行退款。"
                        ),
                    }

                data = RefundExecutionResponse.model_validate(
                    execution
                ).model_dump(mode="json")

                return {
                    "success": True,
                    "data": data,
                    "mode": "simulated",
                    "message": (
                        "已查询到模拟退款执行记录，"
                        "该结果不代表真实资金到账。"
                    ),
                }

        except Exception:
            logger.exception("Refund execution query tool failed")
            return {
                "success": False,
                "error": "refund_execution_query_failed",
                "message": "退款执行结果暂时无法查询，请稍后重试。",
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

    return {
        "success": False,
        "error": "unknown_tool",
        "message": "不支持的工具",
    }
