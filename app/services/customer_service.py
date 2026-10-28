
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    hash_password,
    create_access_token,
    verify_password)
from app.models.customer import Customer
from app.schemas.customer import CustomerRegisterRequest,CustomerLoginRequest



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

class InvalidCredentialsError(Exception):
    """登录凭据无效。"""


async def login_customer(
    session: AsyncSession,
    data: CustomerLoginRequest,
) -> str:
    """验证客户身份并返回 JWT 访问令牌。"""

    email = str(data.email).lower()

    stmt = select(Customer).where(
        Customer.email == email
    )
    result = await session.execute(stmt)
    customer = result.scalar_one_or_none()

    # 不区分邮箱不存在和密码错误，避免泄露账号信息
    if customer is None:
        raise InvalidCredentialsError("邮箱或密码错误")

    if not verify_password(data.password, customer.password_hash):
        raise InvalidCredentialsError("邮箱或密码错误")

    # 已停用账号不能登录
    if not customer.is_active:
        raise InvalidCredentialsError("邮箱或密码错误")

    # 使用客户的 UUID 作为 JWT 的 subject
    return create_access_token(
    subject=str(customer.id),
    actor_type="customer",
    )