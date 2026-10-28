
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_staff
from app.models.staff import Staff
from app.schemas.staff import StaffResponse
from app.db.session import get_db
from app.schemas.staff import (
    StaffLoginRequest,
    StaffTokenResponse,
)
from app.services.staff_service import (
    InvalidStaffCredentialsError,
    login_staff,
)


router = APIRouter(
    prefix="/api/v1/staff",
    tags=["Staff"],
)


@router.post(
    "/login",
    response_model=StaffTokenResponse,
)
async def login(
    data: StaffLoginRequest,
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> StaffTokenResponse:
    """验证员工身份并签发员工访问令牌。"""

    try:
        access_token = await login_staff(
            session=session,
            data=data,
        )
    except InvalidStaffCredentialsError as exc:
        raise HTTPException(
            status_code=401,
            detail="员工邮箱或密码错误，或账号不可用",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return StaffTokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=StaffResponse,
)
async def get_my_staff_profile(
    current_staff: Annotated[
        Staff,
        Depends(get_current_staff),
    ],
) -> StaffResponse:
    """获取当前登录员工的信息。"""

    return StaffResponse.model_validate(current_staff)
