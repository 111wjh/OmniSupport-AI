
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.customer import (
    CustomerRegisterRequest,
    CustomerResponse,
)
from app.services.customer_service import (
    EmailAlreadyRegisteredError,
    register_customer,
)


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
