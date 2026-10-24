
from uuid import UUID

from sqlalchemy import select
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
