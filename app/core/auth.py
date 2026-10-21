
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.customer import Customer


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_customer(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Customer:
    """验证 JWT 并获取当前登录客户。"""

    # 1. 检查请求是否携带 Bearer 令牌
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="未提供访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. 验证 JWT 签名与有效期
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail="访问令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # 3. 获取并验证客户 ID
    subject = payload.get("sub")

    if not isinstance(subject, str):
        raise HTTPException(
            status_code=401,
            detail="访问令牌缺少有效的客户身份",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        customer_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="访问令牌中的客户身份无效",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # 4. 从数据库查询客户
    stmt = select(Customer).where(Customer.id == customer_id)
    result = await session.execute(stmt)
    customer = result.scalar_one_or_none()

    # 5. 确认客户存在且账号启用
    if customer is None or not customer.is_active:
        raise HTTPException(
            status_code=401,
            detail="客户不存在或账号不可用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return customer
