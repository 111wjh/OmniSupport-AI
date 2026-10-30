from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrderResponse(BaseModel):
    """当前客户有权查看的一条订单。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str
    product_name: str
    total_amount: Decimal
    status: str
    purchased_at: datetime
    created_at: datetime


class OrderListResponse(BaseModel):
    """当前客户的订单分页列表。"""

    items: list[OrderResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)