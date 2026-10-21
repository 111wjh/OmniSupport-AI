
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.customer import (
    CustomerLoginRequest,
    CustomerRegisterRequest,
    CustomerResponse,
    TokenResponse,
)
from app.services.customer_service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    login_customer,
    register_customer,
)
from app.core.auth import get_current_customer
from app.models.customer import Customer

router = APIRouter(
    prefix="/api/v1/customers",
    tags=["Customers"],
)


@router.post(
    "/register",
    response_model=CustomerResponse,
    status_code=201,
)
async def register(
    data: CustomerRegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerResponse:
    """注册客户账号。"""

    try:
        customer = await register_customer(
            session=session,
            data=data,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=409,
            detail="该邮箱已被注册",
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="注册信息与现有数据冲突，请检查邮箱是否已注册",
        ) from exc

    return CustomerResponse.model_validate(customer)



@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    data: CustomerLoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """验证客户身份并签发访问令牌。"""

    try:
        access_token = await login_customer(
            session=session,
            data=data,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=401,
            detail="邮箱或密码错误，或账号不可用",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=CustomerResponse,
)
async def get_my_profile(
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
) -> CustomerResponse:
    """获取当前登录客户的信息。"""

    return CustomerResponse.model_validate(
        current_customer
    )
