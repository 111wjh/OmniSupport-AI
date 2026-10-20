
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


async def get_order_by_number(
    session: AsyncSession,
    order_number: str,
) -> Order | None:
    """根据订单编号查询订单。"""

    stmt = (
        select(Order)
        .where(Order.order_number == order_number)
    )

    result = await session.execute(stmt)

    return result.scalar_one_or_none()
