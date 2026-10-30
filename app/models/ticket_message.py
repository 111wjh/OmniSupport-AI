from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketMessageSender(StrEnum):
    """工单回复的发送者类型。"""

    CUSTOMER = "customer"
    STAFF = "staff"


class TicketMessage(Base):
    """客户补充说明或客服回复。"""

    __tablename__ = "ticket_messages"

    __table_args__ = (
        CheckConstraint(
            "sender_type IN ('customer', 'staff')",
            name="ck_ticket_messages_sender_type_valid",
        ),
        CheckConstraint(
            """
            (
                sender_type = 'customer'
                AND sender_customer_id IS NOT NULL
                AND sender_staff_id IS NULL
            )
            OR
            (
                sender_type = 'staff'
                AND sender_customer_id IS NULL
                AND sender_staff_id IS NOT NULL
            )
            """,
            name="ck_ticket_messages_sender_fields_valid",
        ),
        CheckConstraint(
            "message_seq > 0",
            name="ck_ticket_messages_seq_positive",
        ),
        CheckConstraint(
            "length(trim(content)) > 0",
            name="ck_ticket_messages_content_not_empty",
        ),
        UniqueConstraint(
            "ticket_id",
            "message_seq",
            name="uq_ticket_messages_ticket_seq",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    ticket_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tickets.id"),
        nullable=False,
    )

    sender_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    sender_customer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=True,
    )

    sender_staff_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("staff.id"),
        nullable=True,
    )

    message_seq: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )