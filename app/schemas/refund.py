
from datetime import datetime
from typing import Literal
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class RefundCreateRequest(BaseModel):
    """客户提交退款申请的请求。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    order_number: str = Field(
        min_length=1,
        max_length=50,
    )

    reason: str = Field(
        min_length=5,
        max_length=2000,
    )


class RefundReviewRequest(BaseModel):
    """员工审核退款申请的请求。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    decision: Literal["approved", "rejected"]

    review_comment: str = Field(
        min_length=1,
        max_length=2000,
    )


class RefundResponse(BaseModel):
    """退款申请详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    customer_id: UUID
    reason: str
    status: Literal["pending", "approved", "rejected"]
    reviewer_staff_id: UUID | None
    review_comment: str | None
    requested_at: datetime
    reviewed_at: datetime | None


class RefundListResponse(BaseModel):
    """客户退款申请列表响应。"""

    model_config = ConfigDict(from_attributes=True)

    items: list[RefundResponse]

    # 符合查询条件的退款申请总数
    total: int = Field(ge=0)

    # 本次返回的最大记录数
    limit: int = Field(ge=1, le=100)

    # 本次查询跳过的记录数
    offset: int = Field(ge=0)



class StaffRefundListItem(BaseModel):
    """供有审核权限的员工查看的退款申请条目。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    order_number: str
    order_status: str
    order_total_amount: Decimal

    customer_id: UUID
    customer_email: str
    customer_display_name: str

    reason: str
    status: Literal["pending", "approved", "rejected"]
    requested_at: datetime


class StaffRefundListResponse(BaseModel):
    """员工退款申请分页响应。"""

    items: list[StaffRefundListItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class RefundExecutionResponse(BaseModel):
    """模拟退款执行结果响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    refund_request_id: UUID
    order_id: UUID
    amount: Decimal
    status: Literal["pending", "succeeded", "failed"]
    executed_at: datetime | None
    created_at: datetime
