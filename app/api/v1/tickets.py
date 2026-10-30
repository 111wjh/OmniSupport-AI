from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.ticket import TicketStatus
from app.core.auth import get_current_customer
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.ticket import (
    TicketCreateRequest,
    TicketListResponse,
    TicketMessageCreateRequest,
    TicketMessageResponse,
    TicketResponse,
    TicketMessageListResponse
)
from app.services.ticket_service import (
    TicketNotFoundError,
    TicketRelatedResourceNotFoundError,
    create_customer_ticket,
    get_customer_ticket,
    list_customer_tickets,
)
from app.models.ticket_message import TicketMessageSender
from app.services.ticket_message_service import (
    TicketReplyNotAllowedError,
    add_ticket_message,
    list_ticket_messages
)

router = APIRouter(
    prefix="/api/v1/tickets",
    tags=["Tickets"],
)


@router.post(
    "",
    response_model=TicketResponse,
    status_code=201,
)
async def create_ticket(
    data: TicketCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
) -> TicketResponse:
    """为当前登录客户创建人工服务工单。"""

    try:
        ticket = await create_customer_ticket(
            session=session,
            customer_id=current_customer.id,
            data=data,
        )

    except TicketRelatedResourceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return TicketResponse.model_validate(ticket)


@router.get("", response_model=TicketListResponse)
async def list_my_tickets(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
    status: TicketStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketListResponse:
    """分页查询当前客户的工单，可按状态筛选。"""

    items, total = await list_customer_tickets(
        session=session,
        customer_id=current_customer.id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return TicketListResponse(
        items=[
            TicketResponse.model_validate(item)
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
)
async def get_my_ticket(
    ticket_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
) -> TicketResponse:
    """查询当前客户有权查看的工单详情。"""

    ticket = await get_customer_ticket(
        session=session,
        ticket_id=ticket_id,
        customer_id=current_customer.id,
    )

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="工单不存在或无权查看",
        )

    return TicketResponse.model_validate(ticket)



@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageResponse,
    status_code=201,
)
async def add_my_ticket_message(
    ticket_id: UUID,
    data: TicketMessageCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
) -> TicketMessageResponse:
    """由工单所属客户补充说明。"""

    try:
        message = await add_ticket_message(
            session=session,
            ticket_id=ticket_id,
            actor_type=TicketMessageSender.CUSTOMER,
            actor_id=current_customer.id,
            data=data,
        )

    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except TicketReplyNotAllowedError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return TicketMessageResponse.model_validate(message)

@router.get(
    "/{ticket_id}/messages",
    response_model=TicketMessageListResponse,
)
async def list_my_ticket_messages(
    ticket_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketMessageListResponse:
    """由工单所属客户查看沟通记录。"""

    try:
        items, total = await list_ticket_messages(
            session=session,
            ticket_id=ticket_id,
            actor_type=TicketMessageSender.CUSTOMER,
            actor_id=current_customer.id,
            limit=limit,
            offset=offset,
        )

    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return TicketMessageListResponse(
        ticket_id=ticket_id,
        items=[
            TicketMessageResponse.model_validate(item)
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )