
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message

from sqlalchemy import select,func

from app.models.conversation import Conversation

async def create_message(
    session: AsyncSession,
    conversation_id: UUID,
    role: str,
    content: str,
) -> Message:
    """
    保存一条聊天消息。

    由调用方负责提交数据库事务。
    """

    # 检查消息角色
    if role not in ("user", "assistant"):
        raise ValueError("不支持的消息角色")

    # 检查消息内容
    if not content.strip():
        raise ValueError("消息内容不能为空")

    # 创建 Message ORM 对象
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )

    # 添加到当前数据库 Session
    session.add(message)

    # 执行 INSERT，但不提交事务
    await session.flush()

    return message


async def get_conversation_messages(
    session: AsyncSession,
    conversation_id: UUID,
) -> list[Message]:
    """
    根据会话 ID 查询历史聊天消息。

    按创建时间升序排列。
    """

    # 构建 SQLAlchemy 查询语句
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.message_seq.asc())
    )

    # 异步执行 SQL 查询
    result = await session.execute(stmt)

    # 获取 Message ORM 对象列表
    messages = result.scalars().all()

    return list(messages)



async def save_chat_turn_with_token(
    session: AsyncSession,
    conversation_id: UUID,
    token: UUID,
    user_content: str,
    assistant_content: str,
) -> None:
    """验证处理权并原子保存一轮聊天消息。"""

    # 锁定当前会话行，避免验证期间被其他请求接管
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .with_for_update()
    )

    result = await session.execute(stmt)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise ValueError("会话不存在")

    # 使用数据库时间检查处理权是否仍有效
    now_result = await session.execute(select(func.clock_timestamp()))
    database_now = now_result.scalar_one()

    if (
        not conversation.is_processing
        or conversation.processing_token != token
        or conversation.processing_expires_at is None
        or conversation.processing_expires_at <= database_now
    ):
        raise ValueError("会话处理权已失效")

    # 验证成功后，在调用方提供的同一事务中保存消息
    await create_message(
        session=session,
        conversation_id=conversation_id,
        role="user",
        content=user_content,
    )

    await create_message(
        session=session,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
    )
