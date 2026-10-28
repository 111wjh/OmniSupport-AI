
from uuid import UUID
from typing import Any

from app.models.customer import Customer
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.refund_request import RefundRequest
from app.schemas.refund import (
    RefundCreateRequest,
    RefundReviewRequest,
)
from datetime import datetime, timezone
from app.models.refund_audit_event import RefundAuditEvent

# 第一版允许申请退款的订单状态
REFUND_ELIGIBLE_ORDER_STATUSES = {
    "paid",
    "shipped",
    "completed",
}

ACTIVE_REFUND_STATUSES = {
    "pending",
    "approved",
}


class RefundOrderNotFoundError(Exception):
    """订单不存在，或不属于当前客户。"""


class RefundNotAllowedError(Exception):
    """当前订单状态不允许申请退款。"""


class RefundAlreadyExistsError(Exception):
    """订单已经存在有效的退款申请。"""


async def create_refund_request(
    session: AsyncSession,
    customer_id: UUID,
    data: RefundCreateRequest,
) -> RefundRequest:
    """为当前客户创建退款申请。"""

    # 1. 查询当前客户的订单，并锁定订单记录。
    # 同一订单的并发申请会依次处理。
    stmt = (
        select(Order)
        .where(
            Order.order_number == data.order_number,
            Order.customer_id == customer_id,
        )
        .with_for_update()
    )

    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    # 不区分订单不存在和不属于当前客户，避免泄露订单信息
    if order is None:
        raise RefundOrderNotFoundError(
            "订单不存在或无权申请退款"
        )

    # 2. 检查订单状态
    if order.status not in REFUND_ELIGIBLE_ORDER_STATUSES:
        raise RefundNotAllowedError(
            "当前订单状态不允许申请退款"
        )

    # 3. 检查是否已有待审核或已批准的申请
    existing_stmt = (
        select(RefundRequest.id)
        .where(
            RefundRequest.order_id == order.id,
            RefundRequest.status.in_(
                ACTIVE_REFUND_STATUSES
            ),
        )
        .limit(1)
    )

    existing_result = await session.execute(existing_stmt)

    if existing_result.scalar_one_or_none() is not None:
        raise RefundAlreadyExistsError(
            "该订单已存在有效的退款申请"
        )

    # 4. 创建待人工审核的申请
    refund_request = RefundRequest(
        order_id=order.id,
        customer_id=customer_id,
        reason=data.reason,
        status="pending",
    )

    session.add(refund_request)

    # 5. 提交事务；数据库唯一索引负责最终防重
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()

        # 只将目标唯一索引冲突转换为重复申请错误
        diagnostic = getattr(exc.orig, "diag", None)
        constraint_name = getattr(
            diagnostic,
            "constraint_name",
            None,
        )

        if constraint_name == "uq_refund_requests_order_active":
            raise RefundAlreadyExistsError(
                "该订单已存在有效的退款申请"
            ) from exc

        # 其他数据库完整性错误不能伪装成重复申请
        raise

    # 6. 刷新数据库生成的字段
    await session.refresh(refund_request)

    return refund_request


class RefundRequestNotFoundError(Exception):
    """退款申请不存在。"""


class RefundAlreadyReviewedError(Exception):
    """退款申请已被审核，不能重复处理。"""


async def review_refund_request(
    session: AsyncSession,
    refund_request_id: UUID,
    reviewer_staff_id: UUID,
    data: RefundReviewRequest,
) -> RefundRequest:
    """由经过授权的员工审核退款申请。"""

    # 1. 锁定申请记录，防止并发审核
    stmt = (
        select(RefundRequest)
        .where(RefundRequest.id == refund_request_id)
        .with_for_update()
    )

    result = await session.execute(stmt)
    refund_request = result.scalar_one_or_none()

    if refund_request is None:
        await session.rollback()
        raise RefundRequestNotFoundError(
            "退款申请不存在"
        )

    # 2. 只允许审核待处理的申请
    if refund_request.status != "pending":
        await session.rollback()
        raise RefundAlreadyReviewedError(
            "该退款申请已处理，不能重复审核"
        )
    
    # 3. 批准退款前，重新锁定并检查订单状态
    if data.decision == "approved":
        order_stmt = (
            select(Order)
            .where(Order.id == refund_request.order_id)
            .with_for_update()
        )

        order_result = await session.execute(order_stmt)
        order = order_result.scalar_one_or_none()

        if order is None:
            await session.rollback()
            raise RefundNotAllowedError(
                "关联订单不存在，无法批准退款"
            )

        if order.status not in REFUND_ELIGIBLE_ORDER_STATUSES:
            await session.rollback()
            raise RefundNotAllowedError(
                "订单状态已变化，当前不能批准退款"
            )

    
    # 3. 保存审核前的状态
    previous_status = refund_request.status
    new_status = data.decision

    # 4. 更新退款申请的当前状态
    refund_request.status = new_status
    refund_request.reviewer_staff_id = reviewer_staff_id
    refund_request.review_comment = data.review_comment
    refund_request.reviewed_at = datetime.now(timezone.utc)

    # 5. 创建独立的审核审计事件
    audit_event = RefundAuditEvent(
        refund_request_id=refund_request.id,
        reviewer_staff_id=reviewer_staff_id,
        previous_status=previous_status,
        new_status=new_status,
        review_comment=data.review_comment,
    )

    session.add(audit_event)


    # 4. 提交审核结果
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    # 5. 获取提交后的数据库记录
    await session.refresh(refund_request)

    return refund_request



async def list_customer_refund_requests(
    session: AsyncSession,
    customer_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[RefundRequest], int]:
    """分页查询指定客户自己的退款申请。"""

    # 1. 统一限定当前客户的申请范围
    customer_filter = (
        RefundRequest.customer_id == customer_id
    )

    # 2. 查询符合条件的申请总数
    count_stmt = (
        select(func.count())
        .select_from(RefundRequest)
        .where(customer_filter)
    )

    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # 3. 查询当前页的数据
    stmt = (
        select(RefundRequest)
        .where(customer_filter)
        .order_by(
            RefundRequest.requested_at.desc(),
            RefundRequest.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    # 4. 返回当前页数据和符合条件的总数
    return items, total



async def list_pending_refund_requests(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """分页查询员工待审核的退款申请。"""

    # 1. 统计待审核申请总数
    count_stmt = (
        select(func.count(RefundRequest.id))
        .where(RefundRequest.status == "pending")
    )

    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # 2. 查询申请、订单和客户信息
    stmt = (
        select(
            RefundRequest.id.label("id"),
            RefundRequest.order_id.label("order_id"),
            Order.order_number.label("order_number"),
            Order.status.label("order_status"),
            Order.total_amount.label("order_total_amount"),
            RefundRequest.customer_id.label("customer_id"),
            Customer.email.label("customer_email"),
            Customer.display_name.label(
                "customer_display_name"
            ),
            RefundRequest.reason.label("reason"),
            RefundRequest.status.label("status"),
            RefundRequest.requested_at.label(
                "requested_at"
            ),
        )
        .join(
            Order,
            RefundRequest.order_id == Order.id,
        )
        .join(
            Customer,
            RefundRequest.customer_id == Customer.id,
        )
        .where(RefundRequest.status == "pending")
        # 优先处理提交时间较早的申请
        .order_by(
            RefundRequest.requested_at.asc(),
            RefundRequest.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)

    # 3. 将查询结果转换为字典列表
    items = [
        dict(row)
        for row in result.mappings().all()
    ]

    return items, total

