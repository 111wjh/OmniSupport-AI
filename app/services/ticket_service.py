from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.models.conversation import Conversation
from app.models.ticket import Ticket, TicketStatus
from app.schemas.ticket import TicketCreateRequest
from app.services.order_service import get_order_by_number


class TicketRelatedResourceNotFoundError(Exception):
    """关联对象不存在，或不属于当前客户。"""

class TicketNotFoundError(Exception):
    """工单不存在。"""


class TicketClaimConflictError(Exception):
    """工单已被其他员工领取，或已经关闭。"""

class TicketCloseNotAllowedError(Exception):
    """工单当前状态不允许关闭。"""

async def create_customer_ticket(
    session: AsyncSession,
    customer_id: UUID,
    data: TicketCreateRequest,
) -> Ticket:
    """校验关联对象归属，并创建当前客户的工单。"""

    try:
        order_id: UUID | None = None
        conversation_id: UUID | None = None

        # 1. 提供了订单号，就检查订单是否属于当前客户。
        if data.order_number is not None:
            order = await get_order_by_number(
                session=session,
                order_number=data.order_number,
                customer_id=customer_id,
            )

            if order is None:
                raise TicketRelatedResourceNotFoundError(
                    "订单不存在或无权关联"
                )

            order_id = order.id

        # 2. 提供了会话编号，就检查会话是否属于当前客户。
        if data.conversation_id is not None:
            conversation_id = await session.scalar(
                select(Conversation.id).where(
                    Conversation.id == data.conversation_id,
                    Conversation.customer_id == customer_id,
                )
            )

            if conversation_id is None:
                raise TicketRelatedResourceNotFoundError(
                    "会话不存在或无权关联"
                )

        # 3. 使用经过验证的身份与关联对象创建工单。
        ticket = Ticket(
            customer_id=customer_id,
            order_id=order_id,
            conversation_id=conversation_id,
            subject=data.subject,
            description=data.description,
            status=TicketStatus.OPEN.value,
        )

        session.add(ticket)
        await session.commit()

    except Exception:
        await session.rollback()
        raise

    # 4. 读取数据库生成的字段。
    await session.refresh(ticket)

    return ticket

async def list_customer_tickets(
    session: AsyncSession,
    customer_id: UUID,
    status: TicketStatus | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Ticket], int]:
    """分页查询当前客户的工单，可按状态筛选。"""

    filters = [
        Ticket.customer_id == customer_id,
    ]

    if status is not None:
        filters.append(Ticket.status == status.value)

    # 1. 统计符合条件的工单总数。
    count_stmt = (
        select(func.count())
        .select_from(Ticket)
        .where(*filters)
    )

    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # 2. 查询当前页，按创建时间从新到旧排列。
    stmt = (
        select(Ticket)
        .where(*filters)
        .order_by(
            Ticket.created_at.desc(),
            Ticket.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def get_customer_ticket(
    session: AsyncSession,
    ticket_id: UUID,
    customer_id: UUID,
) -> Ticket | None:
    """查询当前客户有权查看的一张工单。"""

    stmt = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.customer_id == customer_id,
    )

    result = await session.execute(stmt)

    return result.scalar_one_or_none()

async def list_open_tickets(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Ticket], int]:
    """分页查询待领取工单，供有权限的员工使用。"""

    queue_filter = Ticket.status == TicketStatus.OPEN.value

    # 1. 统计待领取工单总数。
    count_stmt = (
        select(func.count())
        .select_from(Ticket)
        .where(queue_filter)
    )

    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # 2. 优先展示等待时间较长的工单。
    stmt = (
        select(Ticket)
        .where(queue_filter)
        .order_by(
            Ticket.created_at.asc(),
            Ticket.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return items, total

async def claim_ticket(
    session: AsyncSession,
    ticket_id: UUID,
    staff_id: UUID,
) -> Ticket:
    """领取工单；同一员工重复领取时返回现有结果。"""

    try:
        # 1. 锁定工单，并读取数据库中的最新状态。
        stmt = (
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        ticket = await session.scalar(stmt)

        if ticket is None:
            raise TicketNotFoundError("工单不存在")

        # 2. 待领取工单可以分配给当前员工。
        if ticket.status == TicketStatus.OPEN.value:
            ticket.assigned_staff_id = staff_id
            ticket.status = TicketStatus.IN_PROGRESS.value

        # 3. 同一员工重复领取，不再修改工单。
        elif (
            ticket.status == TicketStatus.IN_PROGRESS.value
            and ticket.assigned_staff_id == staff_id
        ):
            pass

        else:
            raise TicketClaimConflictError(
                "工单已被其他员工领取或已关闭"
            )

        # 4. 处理员工与状态在同一个事务中提交。
        await session.commit()

    except Exception:
        await session.rollback()
        raise

    await session.refresh(ticket)

    return ticket

async def list_assigned_tickets(
    session: AsyncSession,
    staff_id: UUID,
    status: TicketStatus | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Ticket], int]:
    """分页查询分配给指定员工的工单。"""

    filters = [
        Ticket.assigned_staff_id == staff_id,
    ]

    if status is not None:
        filters.append(Ticket.status == status.value)

    count_stmt = (
        select(func.count())
        .select_from(Ticket)
        .where(*filters)
    )

    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    stmt = (
        select(Ticket)
        .where(*filters)
        .order_by(
            Ticket.updated_at.desc(),
            Ticket.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def get_assigned_ticket(
    session: AsyncSession,
    ticket_id: UUID,
    staff_id: UUID,
) -> Ticket | None:
    """查询分配给指定员工的一张工单。"""

    stmt = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.assigned_staff_id == staff_id,
    )

    result = await session.execute(stmt)

    return result.scalar_one_or_none()



async def close_ticket(
    session: AsyncSession,
    ticket_id: UUID,
    staff_id: UUID,
) -> Ticket:
    """由处理员工关闭工单，重复关闭时保留原结果。"""

    try:
        # 1. 限定处理员工，并锁定工单。
        stmt = (
            select(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.assigned_staff_id == staff_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        ticket = await session.scalar(stmt)

        if ticket is None:
            raise TicketNotFoundError(
                "工单不存在或未分配给当前员工"
            )

        # 2. 处理中的工单可以关闭。
        if ticket.status == TicketStatus.IN_PROGRESS.value:
            now = datetime.now(timezone.utc)

            ticket.status = TicketStatus.CLOSED.value
            ticket.closed_at = now
            ticket.updated_at = now

        # 3. 本人重复关闭，保持原关闭时间。
        elif ticket.status == TicketStatus.CLOSED.value:
            pass

        else:
            raise TicketCloseNotAllowedError(
                "当前工单状态不允许关闭"
            )

        await session.commit()

    except Exception:
        await session.rollback()
        raise

    await session.refresh(ticket)

    return ticket
