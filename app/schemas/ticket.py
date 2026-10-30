from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ticket import TicketStatus
from app.models.ticket_message import TicketMessageSender

class TicketCreateRequest(BaseModel):
    """客户创建工单时提交的数据。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    subject: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str = Field(
        min_length=5,
        max_length=4000,
    )

    order_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    conversation_id: UUID | None = None


class TicketResponse(BaseModel):
    """工单主体信息，后续回复通过单独接口读取。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    order_id: UUID | None
    conversation_id: UUID | None
    subject: str
    description: str
    status: TicketStatus
    assigned_staff_id: UUID | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class TicketListResponse(BaseModel):
    """工单分页列表。"""

    items: list[TicketResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

class TicketMessageCreateRequest(BaseModel):
    """客户或员工提交一条工单回复。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    content: str = Field(
        min_length=1,
        max_length=4000,
    )


class TicketMessageResponse(BaseModel):
    """一条工单回复。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    sender_type: TicketMessageSender
    sender_customer_id: UUID | None
    sender_staff_id: UUID | None
    message_seq: int = Field(ge=1)
    content: str
    created_at: datetime


class TicketMessageListResponse(BaseModel):
    """指定工单的回复分页列表。"""

    ticket_id: UUID
    items: list[TicketMessageResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)