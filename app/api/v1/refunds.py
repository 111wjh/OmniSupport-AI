
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    get_current_customer,
    require_staff_roles,
)
from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.refund import (
    RefundCreateRequest,
    RefundReviewRequest,
    RefundResponse,
    RefundListResponse,
    StaffRefundListResponse,
    RefundExecutionResponse,
)
from app.services.refund_service import (
    RefundAlreadyExistsError,
    RefundNotAllowedError,
    RefundOrderNotFoundError,
    RefundAlreadyReviewedError,
    RefundRequestNotFoundError,
    review_refund_request,
    list_customer_refund_requests,
    list_pending_refund_requests,
    create_refund_request,
)
from app.services.refund_execution_service import (
    RefundExecutionError,
    execute_simulated_refund,
    get_customer_refund_execution,
)
from app.models.staff import Staff, StaffRole
router = APIRouter(
    prefix="/api/v1/refunds",
    tags=["Refunds"],
)


@router.post(
    "",
    response_model=RefundResponse,
    status_code=201,
)
async def submit_refund(
    data: RefundCreateRequest,
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
) -> RefundResponse:
    """提交当前登录客户的退款申请。"""

    try:
        refund_request = await create_refund_request(
            session=session,
            customer_id=current_customer.id,
            data=data,
        )

    except RefundOrderNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="订单不存在或无权申请退款",
        ) from exc

    except RefundNotAllowedError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except RefundAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return RefundResponse.model_validate(
        refund_request
    )


@router.post(
    "/{refund_request_id}/review",
    response_model=RefundResponse,
)
async def review_refund(
    refund_request_id: UUID,
    data: RefundReviewRequest,
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_staff: Annotated[
        Staff,
        Depends(
            require_staff_roles(
                StaffRole.REFUND_REVIEWER,
            )
        ),
    ],
) -> RefundResponse:
    """由有权限的员工审核退款申请。"""

    try:
        refund_request = await review_refund_request(
            session=session,
            refund_request_id=refund_request_id,
            reviewer_staff_id=current_staff.id,
            data=data,
        )

    except RefundRequestNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="退款申请不存在",
        ) from exc

    except RefundAlreadyReviewedError as exc:
        raise HTTPException(
            status_code=409,
            detail="该退款申请已处理，不能重复审核",
        ) from exc

    except RefundNotAllowedError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return RefundResponse.model_validate(
        refund_request
    )



@router.get(
    "",
    response_model=RefundListResponse,
)
async def list_my_refunds(
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
) -> RefundListResponse:
    """分页查询当前登录客户自己的退款申请。"""

    items, total = await list_customer_refund_requests(
        session=session,
        customer_id=current_customer.id,
        limit=limit,
        offset=offset,
    )

    return RefundListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )



@router.get(
    "/pending",
    response_model=StaffRefundListResponse,
)
async def list_pending_refunds(
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_staff: Annotated[
        Staff,
        Depends(
            require_staff_roles(
                StaffRole.REFUND_REVIEWER,
            )
        ),
    ],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> StaffRefundListResponse:
    """查询员工有权处理的待审核退款申请。"""

    items, total = await list_pending_refund_requests(
        session=session,
        limit=limit,
        offset=offset,
    )

    return StaffRefundListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{refund_request_id}/execute",
    response_model=RefundExecutionResponse,
)
async def execute_refund(
    refund_request_id: UUID,
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_staff: Annotated[
        Staff,
        Depends(
            require_staff_roles(
                StaffRole.REFUND_REVIEWER,
            )
        ),
    ],
) -> RefundExecutionResponse:
    """由有权限的员工执行模拟退款。"""

    try:
        execution = await execute_simulated_refund(
            session=session,
            refund_request_id=refund_request_id,
            executor_staff_id=current_staff.id,
        )

    except RefundExecutionError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return RefundExecutionResponse.model_validate(
        execution
    )


@router.get(
    "/{refund_request_id}/execution",
    response_model=RefundExecutionResponse,
)
async def get_refund_execution(
    refund_request_id: UUID,
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_customer: Annotated[
        Customer,
        Depends(get_current_customer),
    ],
) -> RefundExecutionResponse:
    """客户查询自己退款申请的执行结果。"""

    execution = await get_customer_refund_execution(
        session=session,
        refund_request_id=refund_request_id,
        customer_id=current_customer.id,
    )

    if execution is None:
        raise HTTPException(
            status_code=404,
            detail="退款执行记录不存在",
        )

    return RefundExecutionResponse.model_validate(
        execution
    )