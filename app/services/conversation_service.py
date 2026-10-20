
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.db.session import AsyncSessionLocal
from sqlalchemy import delete, exists, select, update,or_, text, func
from app.models.message import Message

def create_conversation_id() -> UUID:
    """生成唯一会话 ID。"""
    return uuid4()


async def create_conversation(
    session: AsyncSession,
    title: str = "新会话",
) -> Conversation:
    """
    创建新的聊天会话。

    由调用方负责提交数据库事务。
    """

    # 1. 创建 Conversation ORM 对象
    conversation = Conversation(
        id=create_conversation_id(),
        title=title,
    )

    # 2. 添加到数据库 Session
    session.add(conversation)

    # 3.向数据库发送待执行的 SQL，但不提交事务
    await session.flush()

    # 4. 返回创建的会话对象
    return conversation



async def resolve_conversation_id(
    conversation_id: UUID | None,
) -> UUID:
    """
    处理聊天会话 ID。

    没有 ID：创建新会话。
    有 ID：验证会话存在并复用。
    """

    # 继续已有聊天
    if conversation_id is not None:
        async with AsyncSessionLocal() as session:
            conversation = await session.get(
                Conversation,
                conversation_id,
            )

            if conversation is None:
                raise ValueError("会话不存在")

            return conversation.id

    # 首次聊天，创建数据库会话
    async with AsyncSessionLocal.begin() as session:
        conversation = await create_conversation(
            session=session,
            title="新会话",
        )

        return conversation.id


async def delete_empty_conversation(
    conversation_id: UUID,
) -> bool:
    """仅删除不存在聊天消息的指定会话。"""

    async with AsyncSessionLocal.begin() as session:
        has_messages = (
            select(Message.id)
            .where(Message.conversation_id == Conversation.id)
            .exists()
        )

        stmt = (
            delete(Conversation)
            .where(Conversation.id == conversation_id)
            .where(~has_messages)#只有当数据库中不存在属于该会话的消息时，才允许删除。
            .returning(Conversation.id)
        )

        result = await session.execute(stmt)
        deleted_id = result.scalar_one_or_none()

        return deleted_id is not None





async def acquire_conversation(
    conversation_id: UUID,
) -> UUID | None:
    """原子获取会话处理权，支持过期锁接管。"""

    token = uuid4()

    async with AsyncSessionLocal.begin() as session:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .where(
                or_(
                    Conversation.is_processing.is_(False),
                    Conversation.processing_expires_at
                    <= func.now(),
                )
            )
            .values(
                is_processing=True,
                processing_token=token,
                processing_expires_at=(
                    func.now()
                    + text("INTERVAL '120 seconds'")
                ),
            )
            .returning(Conversation.processing_token)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none()




async def renew_conversation(
    conversation_id: UUID,
    token: UUID,
) -> bool:
    """仅允许仍持有有效处理权的请求续期。"""

    async with AsyncSessionLocal.begin() as session:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.is_processing.is_(True))
            .where(Conversation.processing_token == token)
            .where(
                Conversation.processing_expires_at
                > func.clock_timestamp()
            )
            .values(
                processing_expires_at=(
                    func.clock_timestamp()
                    + text("INTERVAL '120 seconds'")
                )
            )
            .returning(Conversation.id)
        )

        result = await session.execute(stmt)

        renewed_id = result.scalar_one_or_none()

        return renewed_id is not None


async def release_conversation(
    conversation_id: UUID,
    token: UUID,
) -> bool:
    """仅允许当前 Token 持有者释放会话处理权。"""

    async with AsyncSessionLocal.begin() as session:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.is_processing.is_(True))
            .where(Conversation.processing_token == token)
            .values(
                is_processing=False,
                processing_token=None,
                processing_expires_at=None,
            )
            .returning(Conversation.id)
        )

        result = await session.execute(stmt)

        released_id = result.scalar_one_or_none()

        return released_id is not None

