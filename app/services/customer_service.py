
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.customer import Customer
from app.schemas.customer import CustomerRegisterRequest


class EmailAlreadyRegisteredError(Exception):
    """邮箱已经注册。"""


async def register_customer(
    session: AsyncSession,
    data: CustomerRegisterRequest,
) -> Customer:
    """创建客户账号。"""

    # 1. 统一邮箱大小写
    email = str(data.email).lower()

    # 2. 检查邮箱是否已经存在
    stmt = select(Customer).where(
        Customer.email == email
    )
    result = await session.execute(stmt)

    if result.scalar_one_or_none() is not None:
        raise EmailAlreadyRegisteredError(
            "该邮箱已被注册"
        )

    # 3. 对用户密码进行安全哈希
    hashed_password = hash_password(data.password)

    # 4. 创建客户对象
    customer = Customer(
        email=email,
        password_hash=hashed_password,
        display_name=data.display_name,
        is_active=True,
    )

    # 5. 添加到数据库事务
    session.add(customer)

    # 6. 提交事务
    await session.commit()

    # 7. 刷新对象，获取数据库生成的字段
    await session.refresh(customer)

    return customer
