
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
from app.models.staff import Staff, StaffRole
from collections.abc import Callable

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


    # 客户认证只接受客户类型的 JWT
    if payload.get("actor_type") != "customer":
        raise HTTPException(
            status_code=401,
            detail="令牌身份类型不匹配",
            headers={"WWW-Authenticate": "Bearer"},
        )

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




async def get_current_staff(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Staff:
    """验证员工 JWT 并获取当前有效员工。"""

    # 1. 检查是否提供访问令牌
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="未提供访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. 验证 JWT 签名和有效期
    try:
        payload = decode_access_token(
            credentials.credentials
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail="访问令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # 3. 确认令牌属于员工，而不是客户
    if payload.get("actor_type") != "staff":
        raise HTTPException(
            status_code=401,
            detail="令牌身份类型不匹配",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. 获取员工 UUID
    subject = payload.get("sub")

    if not isinstance(subject, str):
        raise HTTPException(
            status_code=401,
            detail="访问令牌缺少有效的员工身份",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        staff_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="访问令牌中的员工身份无效",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # 5. 从数据库读取员工当前状态
    stmt = select(Staff).where(Staff.id == staff_id)
    result = await session.execute(stmt)
    staff = result.scalar_one_or_none()

    # 6. 禁止不存在或已停用的员工访问
    if staff is None or not staff.is_active:
        raise HTTPException(
            status_code=401,
            detail="员工不存在或账号不可用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return staff


def require_staff_roles(
    *allowed_roles: StaffRole,
) -> Callable:
    """创建员工角色权限依赖，管理员具有完整后台权限。"""

    allowed_values = {
        role.value for role in allowed_roles
    }

    async def role_checker(
        current_staff: Annotated[
            Staff,
            Depends(get_current_staff),
        ],
    ) -> Staff:
        # 管理员拥有后台管理权限
        if current_staff.role == StaffRole.ADMIN.value:
            return current_staff

        # 其他员工必须拥有明确授权的角色
        if current_staff.role not in allowed_values:
            raise HTTPException(
                status_code=403,
                detail="当前员工没有执行此操作的权限",
            )

        return current_staff

    return role_checker
