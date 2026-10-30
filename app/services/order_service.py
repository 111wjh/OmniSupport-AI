
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


async def get_order_by_number(
    session: AsyncSession,
    order_number: str,
    customer_id: UUID,
) -> Order | None:
    """根据订单编号和当前客户 ID 查询订单。"""

    stmt = (
        select(Order)
        .where(
            Order.order_number == order_number,
            Order.customer_id == customer_id,
        )
    )

    result = await session.execute(stmt)

    return result.scalar_one_or_none()


async def get_latest_order_for_customer(
    session: AsyncSession,
    customer_id: UUID,
) -> Order | None:
    """查询当前客户最近的一笔订单。"""

    stmt = (
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(
            Order.purchased_at.desc(),
            Order.created_at.desc(),
        )
        .limit(1)
    )

    result = await session.execute(stmt)

    return result.scalar_one_or_none()

async def list_customer_orders(
    session: AsyncSession,
    customer_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Order], int]:
    """分页查询指定客户自己的订单。"""

    # 总数查询和列表查询使用相同的客户范围。
    customer_filter = Order.customer_id == customer_id

    # 1. 统计当前客户的订单总数。
    count_stmt = (
        select(func.count())
        .select_from(Order)
        .where(customer_filter)
    )

    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # 2. 查询当前页订单，新购买的订单排在前面。
    stmt = (
        select(Order)
        .where(customer_filter)
        .order_by(
            Order.purchased_at.desc(),
            Order.created_at.desc(),
            Order.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return items, total
