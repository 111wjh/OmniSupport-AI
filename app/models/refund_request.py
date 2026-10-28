
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefundRequest(Base):
    """客户退款申请及人工审核记录。"""

    __tablename__ = "refund_requests"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_refund_requests_status_valid",
        ),
        CheckConstraint(
            """
            (
                status = 'pending'
                AND reviewer_staff_id IS NULL
                AND reviewed_at IS NULL
            )
            OR
            (
                status IN ('approved', 'rejected')
                AND reviewer_staff_id IS NOT NULL
                AND reviewed_at IS NOT NULL
            )
            """,
            name="ck_refund_requests_review_fields_valid",
        ),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_refund_requests_reason_not_empty",
        ),
        Index(
            "uq_refund_requests_order_active",
            "order_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'approved')"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # 申请退款的订单
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )

    # 提交申请的客户
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    # 客户填写的退款原因
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # pending / approved / rejected
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    # 审核人员；待审核时为空
    reviewer_staff_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("staff.id"),
        nullable=True,
    )

    # 审核意见
    review_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 提交时间
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # 审核时间；待审核时为空
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
