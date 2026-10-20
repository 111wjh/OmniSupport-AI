
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,#Identity：让 PostgreSQL 自动生成递增编号。
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Message(Base):
    """AI 客服聊天消息模型"""

    __tablename__ = "messages"

    # 消息唯一 ID
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )


    # 消息全局递增编号，用于辅助确定聊天顺序
    message_seq: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        nullable=False,
        unique=True,
    )

    # 关联所属会话
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )

    # 消息角色：user / assistant
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # 消息内容
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # 消息创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
