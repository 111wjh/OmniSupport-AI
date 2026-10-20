
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from decimal import Decimal

class Order(Base):
    """企业客服系统的订单模型。"""

    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # 用户可输入的业务订单编号
    order_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    # 客户名称（后续会增加身份认证）
    customer_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 购买产品
    product_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # 订单金额
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
)

    # 订单状态
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="paid",
    )

    # 购买时间
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # 创建记录的时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
