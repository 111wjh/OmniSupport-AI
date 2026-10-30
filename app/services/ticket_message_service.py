from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_message import (
    TicketMessage,
    TicketMessageSender,
)
from app.schemas.ticket import TicketMessageCreateRequest
from app.services.ticket_service import TicketNotFoundError


class TicketReplyNotAllowedError(Exception):
    """当前工单状态不允许继续回复。"""


def _ticket_access_filter(
    actor_type: TicketMessageSender,
    actor_id: UUID,
) -> ColumnElement[bool]:
    """根据请求身份，生成工单访问条件。"""

    if actor_type == TicketMessageSender.CUSTOMER:
        return Ticket.customer_id == actor_id

    if actor_type == TicketMessageSender.STAFF:
        return Ticket.assigned_staff_id == actor_id

    raise ValueError("不支持的工单访问身份")


async def add_ticket_message(
    session: AsyncSession,
    ticket_id: UUID,
    actor_type: TicketMessageSender,
    actor_id: UUID,
    data: TicketMessageCreateRequest,
) -> TicketMessage:
    """验证身份与状态，按序号保存一条工单回复。"""

    try:
        # 1. 限定访问范围，并锁定对应工单。
        stmt = (
            select(Ticket)
            .where(
                Ticket.id == ticket_id,
                _ticket_access_filter(actor_type, actor_id),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        ticket = await session.scalar(stmt)

        if ticket is None:
            raise TicketNotFoundError(
                "工单不存在或无权访问"
            )

        # 2. 关闭后的工单禁止继续回复。
        if ticket.status == TicketStatus.CLOSED.value:
            raise TicketReplyNotAllowedError(
                "工单已关闭，不能继续回复"
            )

        # 3. 持有工单锁时，计算下一条回复的序号。
        last_seq = await session.scalar(
            select(func.max(TicketMessage.message_seq))
            .where(TicketMessage.ticket_id == ticket.id)
        )

        message = TicketMessage(
            ticket_id=ticket.id,
            sender_type=actor_type.value,
            sender_customer_id=(
                actor_id
                if actor_type == TicketMessageSender.CUSTOMER
                else None
            ),
            sender_staff_id=(
                actor_id
                if actor_type == TicketMessageSender.STAFF
                else None
            ),
            message_seq=(last_seq or 0) + 1,
            content=data.content,
        )

        session.add(message)

        # 4. 回复写入时，同时更新工单的最近活动时间。
        ticket.updated_at = datetime.now(timezone.utc)

        await session.commit()

    except Exception:
        await session.rollback()
        raise

    await session.refresh(message)

    return message



async def list_ticket_messages(
    session: AsyncSession,
    ticket_id: UUID,
    actor_type: TicketMessageSender,
    actor_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[TicketMessage], int]:
    """验证工单访问权限，分页读取双方回复。"""

    # 1. 先确认请求者有权查看这张工单。
    visible_ticket_id = await session.scalar(
        select(Ticket.id).where(
            Ticket.id == ticket_id,
            _ticket_access_filter(actor_type, actor_id),
        )
    )

    if visible_ticket_id is None:
        raise TicketNotFoundError(
            "工单不存在或无权访问"
        )

    message_filter = (
        TicketMessage.ticket_id == visible_ticket_id
    )

    # 2. 统计该工单的回复总数。
    count_stmt = (
        select(func.count())
        .select_from(TicketMessage)
        .where(message_filter)
    )

    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # 3. 按工单内的序号，从早到晚读取回复。
    stmt = (
        select(TicketMessage)
        .where(message_filter)
        .order_by(TicketMessage.message_seq.asc())
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return items, total