import logging
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.db.session import AsyncSessionLocal
from app.schemas.agent_ticket import CreateSupportTicketArguments
from app.schemas.ticket import TicketCreateRequest
from app.services.ticket_service import (
    TicketRelatedResourceNotFoundError,
    create_customer_ticket,
)


logger = logging.getLogger(__name__)


async def execute_create_support_ticket(
    arguments: str,
    customer_id: UUID | None,
    conversation_id: UUID | None,
) -> dict[str, Any]:
    """校验工具参数，并为当前客户创建关联当前会话的工单。"""

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
            )

            return {
                "success": True,
                "data": {
                    "id": str(ticket.id),
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "conversation_id": str(ticket.conversation_id),
                    "created_at": ticket.created_at.isoformat(),
                },
                "message": (
                    "人工服务工单已创建，等待工作人员领取。"
                    "这不代表人工客服已经接入。"
                ),
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