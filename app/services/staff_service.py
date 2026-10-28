
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.staff import Staff
from app.schemas.staff import StaffLoginRequest


# 使用虚拟密码哈希，降低通过登录耗时判断邮箱是否存在的风险。
# 该哈希仅用于无对应员工账号时的密码验证，不用于任何真实账号。
_DUMMY_PASSWORD_HASH = hash_password(
    "dummy-staff-password-not-used-for-login"
)


class InvalidStaffCredentialsError(Exception):
    """员工登录凭据无效或账号不可用。"""


async def login_staff(
    session: AsyncSession,
    data: StaffLoginRequest,
) -> str:
    """验证员工身份并签发员工专属 JWT。"""

    # 1. 统一邮箱大小写
    email = str(data.email).lower()

    # 2. 查询独立的员工账号表
    stmt = select(Staff).where(Staff.email == email)
    result = await session.execute(stmt)
    staff = result.scalar_one_or_none()

    # 3. 账号不存在时，也执行一次密码哈希验证
    if staff is None:
        verify_password(
            data.password,
            _DUMMY_PASSWORD_HASH,
        )
        raise InvalidStaffCredentialsError(
            "员工邮箱或密码错误，或账号不可用"
        )

    # 4. 验证密码，并检查账号是否启用
    password_valid = verify_password(
        data.password,
        staff.password_hash,
    )

    if not password_valid or not staff.is_active:
        raise InvalidStaffCredentialsError(
            "员工邮箱或密码错误，或账号不可用"
        )

    # 5. 签发员工身份令牌，不在令牌中授予业务角色权限
    return create_access_token(
        subject=str(staff.id),
        actor_type="staff",
    )
