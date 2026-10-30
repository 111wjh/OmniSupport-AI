from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_customer
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.order import OrderListResponse, OrderResponse
from app.services.order_service import (
    get_order_by_number,
    list_customer_orders,
)


router = APIRouter(
    prefix="/api/v1/orders",
    tags=["Orders"],
)


@router.get("", response_model=OrderListResponse)
async def list_my_orders(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> OrderListResponse:
    """分页查询当前登录客户自己的订单。"""

    items, total = await list_customer_orders(
        session=session,
        customer_id=current_customer.id,
        limit=limit,
        offset=offset,
    )

    return OrderListResponse(
        items=[
            OrderResponse.model_validate(item)
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{order_number}",
    response_model=OrderResponse,
)
async def get_my_order(
    order_number: Annotated[
        str,
        Path(min_length=1, max_length=50),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
) -> OrderResponse:
    """查询当前登录客户自己的指定订单。"""

    order = await get_order_by_number(
        session=session,
        order_number=order_number,
        customer_id=current_customer.id,
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="订单不存在或无权查看",
        )

    return OrderResponse.model_validate(order)