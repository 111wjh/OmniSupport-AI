from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketStatus(StrEnum):
    """工单状态。"""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Ticket(Base):
    """客户提交的人工服务工单。"""

    __tablename__ = "tickets"

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'closed')",
            name="ck_tickets_status_valid",
        ),
        CheckConstraint(
            """
            (
                status = 'open'
                AND assigned_staff_id IS NULL
                AND closed_at IS NULL
            )
            OR
            (
                status = 'in_progress'
                AND assigned_staff_id IS NOT NULL
                AND closed_at IS NULL
            )
            OR
            (
                status = 'closed'
                AND assigned_staff_id IS NOT NULL
                AND closed_at IS NOT NULL
            )
            """,
            name="ck_tickets_state_fields_valid",
        ),
        CheckConstraint(
            "length(trim(subject)) > 0",
            name="ck_tickets_subject_not_empty",
        ),
        CheckConstraint(
            "length(trim(description)) > 0",
            name="ck_tickets_description_not_empty",
        ),
        Index(
            "ix_tickets_customer_created",
            "customer_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_tickets_status_created",
            "status",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )

    # 工单可以关联订单，也可以用于非订单问题。
    order_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=True,
        index=True,
    )

    # 可关联发起人工服务的 AI 会话。
    conversation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=True,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TicketStatus.OPEN.value,
        server_default=TicketStatus.OPEN.value,
    )

    assigned_staff_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("staff.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )