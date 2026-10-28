from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefundExecution(Base):
    """退款执行记录。"""

    __tablename__ = "refund_executions"

    __table_args__ = (
        UniqueConstraint(
            "refund_request_id",
            name="uq_refund_executions_request",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_refund_executions_amount_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_refund_executions_status_valid",
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
    )

    # 对应的订单
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )

    # 退款金额
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # pending / succeeded / failed
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    # 退款成功时间
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )