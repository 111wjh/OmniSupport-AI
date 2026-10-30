from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.order import Order
from app.schemas.demo_order import DemoOrderCreate


async def create_demo_order(
    session: AsyncSession,
    data: DemoOrderCreate,
) -> Order:
    """创建演示订单，由调用方负责提交事务。"""

    # 1. 统一邮箱大小写，查找已有客户。
    email = str(data.customer_email).lower()

    result = await session.execute(
        select(Customer).where(Customer.email == email)
    )
    customer = result.scalar_one_or_none()

    if customer is None or not customer.is_active:
        raise ValueError("客户不存在或账号已停用")

    # 2. 创建带明确模拟标识的订单。
    order = Order(
        order_number=f"OMNI-DEMO-{uuid4().hex.upper()}",
        customer_id=customer.id,
        customer_name=customer.display_name,
        product_name=f"{data.product_name}（模拟）",
        total_amount=data.total_amount,
        status="paid",
        purchased_at=datetime.now(timezone.utc),
    )

    # 3. 将数据写入当前事务，但暂不提交。
    session.add(order)
    await session.flush()

    return order