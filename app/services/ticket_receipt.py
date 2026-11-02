"""工具正常执行和提交后恢复共用的业务回执。"""

from typing import Any
from app.models.ticket import Ticket


def ticket_creation_result(ticket: Ticket) -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "id": str(ticket.id), "subject": ticket.subject, "status": ticket.status,
            "conversation_id": str(ticket.conversation_id) if ticket.conversation_id else None,
            "created_at": ticket.created_at.isoformat(),
        },
        "message": "人工服务工单记录已确认，状态以 data.status 为准。这不代表人工客服已经接入。",
    }
