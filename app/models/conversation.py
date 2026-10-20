
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Conversation(Base):
    """AI 客服会话模型"""

    __tablename__ = "conversations"

    # 会话唯一 ID
    id: Mapped[UUID] = mapped_column(
        #`as_uuid=True` 表示查询时自动把数据库返回的字符串转成 Python `UUID` 对象
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # 会话标题
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="新会话",
    )

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


    # 是否有正在处理的聊天请求
    is_processing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )


    # 当前会话处理权的唯一持有者标识
    processing_token: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )


    # 当前会话处理权的到期时间
    processing_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

