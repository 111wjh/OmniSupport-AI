from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_customer
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.conversation import (
    ConversationSummary,
    ConversationListResponse,
    MessageResponse,
    ConversationMessagesResponse,
)
from app.services.conversation_service import (
    list_customer_conversations,
    resolve_conversation_id,
)
from app.services.message_service import (
    list_customer_conversation_messages,
)

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["Conversations"],
)


@router.get("", response_model=ConversationListResponse)
async def list_my_conversations(
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConversationListResponse:
    """分页查询当前登录客户自己的会话。"""

    items, total = await list_customer_conversations(
        session=session,
        customer_id=current_customer.id,
        limit=limit,
        offset=offset,
    )

    return ConversationListResponse(
        items=[
            ConversationSummary.model_validate(item)
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.get(
    "/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
)
async def list_my_conversation_messages(
    conversation_id: UUID,
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConversationMessagesResponse:
    """分页读取当前客户有权访问的会话消息。"""

    # 1. 复用已有逻辑，验证会话存在且属于当前客户
    try:
        await resolve_conversation_id(
            conversation_id=conversation_id,
            customer_id=current_customer.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="会话不存在",
        ) from exc

    # 2. 查询当前页消息
    items, total = await list_customer_conversation_messages(
        session=session,
        conversation_id=conversation_id,
        customer_id=current_customer.id,
        limit=limit,
        offset=offset,
    )

    # 3. 转换成响应格式
    return ConversationMessagesResponse(
        conversation_id=conversation_id,
        items=[
            MessageResponse.model_validate(item)
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )