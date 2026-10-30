from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ticket import TicketStatus
from app.core.auth import get_current_staff, require_staff_roles
from app.db.session import get_db
from app.models.staff import Staff, StaffRole
from app.models.ticket_message import TicketMessageSender
from app.services.ticket_message_service import (
    TicketReplyNotAllowedError,
    add_ticket_message,
    list_ticket_messages
)
from app.schemas.ticket import (
    TicketListResponse,
    TicketMessageCreateRequest,
    TicketMessageResponse,
    TicketResponse,
    TicketMessageListResponse
)
from app.services.ticket_service import (
    TicketClaimConflictError,
    TicketCloseNotAllowedError,
    TicketNotFoundError,
    claim_ticket,
    close_ticket,
    get_assigned_ticket,
    list_assigned_tickets,
    list_open_tickets,
)

router = APIRouter(
    prefix="/api/v1/staff/tickets",
    tags=["Staff Tickets"],
    dependencies=[
        Depends(
            require_staff_roles(
                StaffRole.CUSTOMER_SUPPORT,
            )
        ),
    ],
)


@router.get(
    "/queue",
    response_model=TicketListResponse,
)
async def list_ticket_queue(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketListResponse:
    """供客服或管理员查看待领取工单队列。"""

    items, total = await list_open_tickets(
        session=session,
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

@router.post(
    "/{ticket_id}/claim",
    response_model=TicketResponse,
)
async def claim_ticket_for_me(
    ticket_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_staff: Annotated[
        Staff,
        Depends(get_current_staff),
    ],
) -> TicketResponse:
    """由当前登录员工领取工单。"""

    try:
        ticket = await claim_ticket(
            session=session,
            ticket_id=ticket_id,
            staff_id=current_staff.id,
        )

    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except TicketClaimConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return TicketResponse.model_validate(ticket)


@router.get(
    "/mine",
    response_model=TicketListResponse,
)
async def list_my_assigned_tickets(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_staff: Annotated[
        Staff,
        Depends(get_current_staff),
    ],
    status: TicketStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketListResponse:
    """查询当前员工领取的工单。"""

    items, total = await list_assigned_tickets(
        session=session,
        staff_id=current_staff.id,
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
async def get_my_assigned_ticket(
    ticket_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_staff: Annotated[
        Staff,
        Depends(get_current_staff),
    ],
) -> TicketResponse:
    """查询分配给当前员工的工单详情。"""

    ticket = await get_assigned_ticket(
        session=session,
        ticket_id=ticket_id,
        staff_id=current_staff.id,
    )

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="工单不存在或未分配给当前员工",
        )

    return TicketResponse.model_validate(ticket)


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageResponse,
    status_code=201,
)
async def add_staff_ticket_message(
    ticket_id: UUID,
    data: TicketMessageCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_staff: Annotated[
        Staff,
        Depends(get_current_staff),
    ],
) -> TicketMessageResponse:
    """由当前处理员工回复工单。"""

    try:
        message = await add_ticket_message(
            session=session,
            ticket_id=ticket_id,
            actor_type=TicketMessageSender.STAFF,
            actor_id=current_staff.id,
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
async def list_staff_ticket_messages(
    ticket_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_staff: Annotated[
        Staff,
        Depends(get_current_staff),
    ],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketMessageListResponse:
    """由当前处理员工查看沟通记录。"""

    try:
        items, total = await list_ticket_messages(
            session=session,
            ticket_id=ticket_id,
            actor_type=TicketMessageSender.STAFF,
            actor_id=current_staff.id,
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


@router.post(
    "/{ticket_id}/close",
    response_model=TicketResponse,
)
async def close_my_assigned_ticket(
    ticket_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_staff: Annotated[
        Staff,
        Depends(get_current_staff),
    ],
) -> TicketResponse:
    """由当前处理员工关闭工单。"""

    try:
        ticket = await close_ticket(
            session=session,
            ticket_id=ticket_id,
            staff_id=current_staff.id,
        )

    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except TicketCloseNotAllowedError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return TicketResponse.model_validate(ticket)