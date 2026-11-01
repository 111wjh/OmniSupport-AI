"""请求指纹、首次会话映射和结果回放；数据库唯一约束处理竞争。"""

import hashlib
import json
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.chat_operation import ChatOperation
from app.models.conversation import Conversation
from app.models.ticket import Ticket
from app.services.conversation_service import create_conversation


class ChatIdempotencyConflictError(Exception):
    """同一发送编号用于不同输入。"""


def fingerprint_chat_request(message: str, conversation_id: UUID | None, image_bytes: bytes | None = None) -> str:
    # 使用原始请求，而非模型生成的标题或图片观察；普通与 SSE 的传输方式不参与指纹。
    payload = {
        "message": message,
        "conversation_id": str(conversation_id) if conversation_id else None,
        "image_sha256": hashlib.sha256(image_bytes).hexdigest() if image_bytes is not None else None,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ticket_key(operation_id: UUID) -> str:
    # 后端专用命名空间，模型和客户端不能指定该工具键。
    return f"chat-operation:{operation_id}"


def _check_fingerprint(operation: ChatOperation, fingerprint: str) -> ChatOperation:
    if operation.request_fingerprint != fingerprint:
        raise ChatIdempotencyConflictError("该发送编号对应的内容不一致，请使用原请求重试，或为新消息生成新编号。")
    return operation


async def prepare_chat_operation(
    customer_id: UUID, client_request_id: UUID, message: str,
    conversation_id: UUID | None, image_bytes: bytes | None = None,
) -> ChatOperation:
    fingerprint = fingerprint_chat_request(message, conversation_id, image_bytes)
    async with AsyncSessionLocal() as session:
        async def find_existing():
            return await session.scalar(select(ChatOperation).where(
                ChatOperation.customer_id == customer_id,
                ChatOperation.client_request_id == client_request_id,
            ))
        existing = await find_existing()
        if existing is not None:
            return _check_fingerprint(existing, fingerprint)
        try:
            if conversation_id is None:
                # 会话和发送记录同事务；并发竞争失败会同时回滚，避免留下孤立会话。
                conversation = await create_conversation(session, customer_id=customer_id)
                resolved_id = conversation.id
            else:
                resolved_id = await session.scalar(select(Conversation.id).where(
                    Conversation.id == conversation_id, Conversation.customer_id == customer_id,
                ))
                if resolved_id is None:
                    raise ValueError("会话不存在")
            operation = ChatOperation(
                customer_id=customer_id, client_request_id=client_request_id,
                request_fingerprint=fingerprint, conversation_id=resolved_id,
            )
            session.add(operation)
            await session.commit()
            return operation
        except IntegrityError as exc:
            await session.rollback()
            if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) != "uq_chat_operations_customer_request":
                raise
            existing = await find_existing()
            if existing is None:
                raise
            return _check_fingerprint(existing, fingerprint)


async def load_chat_operation(operation_id: UUID, customer_id: UUID, conversation_id: UUID) -> ChatOperation:
    async with AsyncSessionLocal() as session:
        operation = await session.scalar(select(ChatOperation).where(
            ChatOperation.id == operation_id, ChatOperation.customer_id == customer_id,
            ChatOperation.conversation_id == conversation_id,
        ))
        if operation is None:
            raise ValueError("发送记录不存在或无权使用")
        return operation


async def remember_image_observation(operation_id: UUID, observation: str) -> str:
    async with AsyncSessionLocal.begin() as session:
        await session.execute(update(ChatOperation).where(
            ChatOperation.id == operation_id, ChatOperation.image_observation.is_(None),
        ).values(image_observation=observation))
        return await session.scalar(select(ChatOperation.image_observation).where(ChatOperation.id == operation_id))


async def find_created_ticket(operation_id: UUID, customer_id: UUID, conversation_id: UUID) -> Ticket | None:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(Ticket).where(
            Ticket.customer_id == customer_id, Ticket.conversation_id == conversation_id,
            Ticket.idempotency_key == ticket_key(operation_id),
        ))


async def complete_chat_operation(
    session: AsyncSession, operation_id: UUID, customer_id: UUID, conversation_id: UUID, reply: str,
) -> None:
    # 调用方先验证会话 fencing token；两条消息与回放结果共用同一事务。
    result = await session.execute(update(ChatOperation).where(
        ChatOperation.id == operation_id, ChatOperation.customer_id == customer_id,
        ChatOperation.conversation_id == conversation_id, ChatOperation.reply.is_(None),
    ).values(reply=reply, completed_at=func.now()))
    if result.rowcount != 1:
        raise RuntimeError("发送结果已完成或发送记录失效")
