
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefundExecutionAuditEvent(Base):
    """记录退款执行过程的独立审计事件。"""

    __tablename__ = "refund_execution_audit_events"

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('succeeded', 'failed')",
            name="ck_refund_execution_audit_event_type",
        ),
        CheckConstraint(
            "amount IS NULL OR amount > 0",
            name="ck_refund_execution_audit_amount_positive",
        ),
        UniqueConstraint(
            "refund_execution_id",
            name="uq_refund_execution_audit_execution",
        ),
        Index(
            "ix_refund_execution_audit_request_created",
            "refund_request_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # 对应的退款申请
    refund_request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("refund_requests.id"),
        nullable=False,
        index=True,
    )

    # 对应的退款执行记录；失败事件可以没有执行记录
    refund_execution_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("refund_executions.id"),
        nullable=True,
    )

    # 触发退款执行的员工
    executor_staff_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("staff.id"),
        nullable=False,
        index=True,
    )

    # succeeded / failed
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # 退款金额；执行失败且金额尚未确定时可以为空
    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    # 执行前后的订单状态
    previous_order_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    new_order_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    # 记录经过处理的业务说明，不存储敏感信息
    detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 审计事件创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
