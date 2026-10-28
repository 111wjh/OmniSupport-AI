
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StaffRole(StrEnum):
    """员工角色。"""

    ADMIN = "admin"
    CUSTOMER_SUPPORT = "customer_support"
    REFUND_REVIEWER = "refund_reviewer"


class Staff(Base):
    """独立的企业员工账号模型。"""

    __tablename__ = "staff"

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'customer_support', 'refund_reviewer')",
            name="ck_staff_role_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # 员工登录邮箱，与客户账号表相互独立
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # 只保存密码哈希
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # 员工显示名称
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 员工角色，默认仅具有普通客服权限
    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=StaffRole.CUSTOMER_SUPPORT.value,
        server_default=StaffRole.CUSTOMER_SUPPORT.value,
    )

    # 是否允许员工登录
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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
