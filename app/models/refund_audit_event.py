
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
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefundAuditEvent(Base):
    """记录退款审核过程的独立审计事件。"""

    __tablename__ = "refund_audit_events"

    __table_args__ = (
        CheckConstraint(
            "previous_status = 'pending'",
            name="ck_refund_audit_previous_status",
        ),
        CheckConstraint(
            "new_status IN ('approved', 'rejected')",
            name="ck_refund_audit_new_status",
        ),
        Index(
            "ix_refund_audit_request_created",
            "refund_request_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # 对应被审核的退款申请
    refund_request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("refund_requests.id"),
        nullable=False,
        index=True,
    )

    # 执行审核的员工
    reviewer_staff_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("staff.id"),
        nullable=False,
        index=True,
    )

    # 审核前的状态
    previous_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # 审核后的状态
    new_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # 本次审核时提交的意见快照
    review_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 审计事件的创建时间，由数据库生成
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
