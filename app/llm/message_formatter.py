
from app.models.message import Message


def format_history_for_llm(
    messages: list[Message],
) -> list[dict[str, str]]:
    """将数据库聊天记录转换为大模型消息格式。"""

    formatted_messages = []

    for message in messages:
        if message.role not in ("user", "assistant"):
            raise ValueError(
                f"不支持的消息角色: {message.role}"
            )

        formatted_messages.append(
            {
                "role": message.role,
                "content": message.content,
            }
        )

    return formatted_messages
