"""Agent 的退款工具。"""

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.db.session import AsyncSessionLocal
from app.services.refund_service import list_customer_refund_requests
from app.tools.context import ToolContext
from uuid import UUID

from app.schemas.refund import RefundCreateRequest, RefundExecutionResponse
from app.services.refund_service import (
    RefundAlreadyExistsError,
    RefundNotAllowedError,
    RefundOrderNotFoundError,
    create_refund_request,
    list_customer_refund_requests,
)

logger = logging.getLogger("uvicorn.error")


class ListMyRefundsArguments(BaseModel):
    """查询当前客户退款申请的参数。"""

    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=20, ge=1, le=100, description="最多返回的记录数")
    offset: int = Field(default=0, ge=0, description="分页时跳过的记录数")


async def execute_list_my_refunds(arguments: str, context: ToolContext) -> dict:
    """查询当前客户的退款申请列表。"""
    try:
        args = ListMyRefundsArguments.model_validate_json(arguments)
    except ValidationError:
        return {
            "success": False,
            "error": "invalid_arguments",
            "message": "退款查询参数不合法。",
        }

    customer_id = context.customer_id
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
                        "requested_at": item.requested_at.isoformat(),
                        "reviewed_at": (
                            item.reviewed_at.isoformat()
                            if item.reviewed_at is not None
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

class GetRefundExecutionArguments(BaseModel):
    """查询退款执行结果的参数。"""

    model_config = ConfigDict(extra="forbid")
    refund_request_id: UUID = Field(description="退款申请的 UUID")


async def execute_get_refund_execution(
    arguments: str,
    context: ToolContext,
) -> dict:
    """查询当前客户自己的退款执行结果。"""
    try:
        args = GetRefundExecutionArguments.model_validate_json(arguments)
    except ValidationError:
        return {
            "success": False,
            "error": "invalid_arguments",
            "message": "退款申请编号格式不合法。",
        }

    customer_id = context.customer_id
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

            data = RefundExecutionResponse.model_validate(execution).model_dump(
                mode="json"
            )
            return {
                "success": True,
                "data": data,
                "mode": "simulated",
                "message": "已查询到模拟退款执行记录，该结果不代表真实资金到账。",
            }
    except Exception:
        logger.exception("Refund execution query tool failed")
        return {
            "success": False,
            "error": "refund_execution_query_failed",
            "message": "退款执行结果暂时无法查询，请稍后重试。",
        }


async def execute_submit_refund_request(
    arguments: str,
    context: ToolContext,
) -> dict:
    """为当前客户提交待审核的退款申请。"""
    try:
        data = RefundCreateRequest.model_validate_json(arguments)
    except ValidationError:
        return {
            "success": False,
            "error": "invalid_arguments",
            "message": "退款申请参数不合法，请检查订单编号和退款原因。",
        }

    customer_id = context.customer_id
    if customer_id is None:
        return {
            "success": False,
            "error": "authentication_required",
            "message": "请先登录，再提交退款申请。",
        }

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
                    "requested_at": refund_request.requested_at.isoformat(),
                },
                "message": "退款申请已提交，等待工作人员审核。",
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