import logging
from typing import Any
from pydantic import ValidationError

from app.db.session import AsyncSessionLocal
from app.schemas.agent_ticket import CreateSupportTicketArguments
from app.schemas.ticket import TicketCreateRequest
from app.services.ticket_receipt import ticket_creation_result
from app.services.ticket_service import (
    TicketRelatedResourceNotFoundError,
    TicketIdempotencyConflictError,
    create_customer_ticket,
)
from app.tools.context import ToolContext

logger = logging.getLogger(__name__)


async def execute_create_support_ticket(
    arguments: str,
    context: ToolContext,
) -> dict[str, Any]:
    """校验工具参数，并为当前客户创建关联当前会话的工单。"""
    customer_id = context.customer_id
    conversation_id = context.conversation_id
    idempotency_key = context.ticket_idempotency_key

    # 1. 客户身份和会话必须由后端提供。
    if customer_id is None:
        return {
            "success": False,
            "error": "authentication_required",
            "message": "请先登录，再创建人工服务工单。",
        }

    if conversation_id is None:
        return {
            "success": False,
            "error": "conversation_required",
            "message": "缺少当前聊天会话，未创建工单。",
        }

    # 2. 校验模型参数，再组合后端提供的会话编号。
    try:
        args = CreateSupportTicketArguments.model_validate_json(
            arguments
        )

        data = TicketCreateRequest(
            subject=args.subject,
            description=args.description,
            order_number=args.order_number,
            conversation_id=conversation_id,
        )

    except ValidationError:
        return {
            "success": False,
            "error": "invalid_arguments",
            "message": "工单参数不合法，请检查标题、问题说明和订单编号。",
        }

    # 3. 复用工单 Service，校验归属并提交数据库事务。
    try:
        async with AsyncSessionLocal() as session:
            ticket = await create_customer_ticket(
                session=session,
                customer_id=customer_id,
                data=data,
                idempotency_key=idempotency_key,
            )

            return ticket_creation_result(ticket)

    except TicketIdempotencyConflictError:
        return {
            "success": False,
            "error": "ticket_idempotency_conflict",
            "message": "本次未新建工单：同一次发送已有不同内容的建单记录，请查询已有工单。",
        }

    except TicketRelatedResourceNotFoundError:
        return {
            "success": False,
            "error": "related_resource_not_found",
            "message": "关联的订单或会话不存在，或当前客户无权关联。",
        }

    except Exception:
        logger.exception("Support ticket creation result unconfirmed")

        return {
            "success": False,
            "error": "ticket_creation_unconfirmed",
            "message": (
                "暂时无法确认工单是否创建成功。"
                "请先查询工单列表核对，确认前请勿重复创建。"
            ),
        }