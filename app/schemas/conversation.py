from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationSummary(BaseModel):
    """会话列表中的一条会话摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """当前客户的会话分页列表。"""

    items: list[ConversationSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class MessageResponse(BaseModel):
    """会话中的一条聊天消息。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationMessagesResponse(BaseModel):
    """指定会话的消息分页列表。"""

    conversation_id: UUID
    items: list[MessageResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)