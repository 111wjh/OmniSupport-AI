
from pydantic import BaseModel, Field,field_validator
from uuid import UUID

# 用户发送消息的数据模型
class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户发送的聊天消息",
        
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="会话唯一标识，首次聊天时可以为空",
    )
    @field_validator("message")
    @classmethod
    def validate_message(cls,value: str) -> str:
         # 去掉消息首尾的空白字符
        value = value.strip()

        # 禁止纯空白消息
        if not value:
            raise ValueError("消息不能为空或仅包含空白字符")
        return value

# AI 返回消息的数据模型

class ChatResponse(BaseModel):
    reply: str = Field(
        ...,
        description="AI 客服返回的消息",
    )

    conversation_id: UUID = Field(
        ...,
        description="当前聊天会话的唯一标识",
    )

