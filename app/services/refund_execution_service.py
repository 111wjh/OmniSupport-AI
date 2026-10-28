from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.refund_request import RefundRequest
from app.models.refund_execution import RefundExecution
from app.services.refund_service import REFUND_ELIGIBLE_ORDER_STATUSES
from app.models.refund_execution_audit_event import (
    RefundExecutionAuditEvent,
)

class RefundExecutionError(Exception):
    """退款执行业务异常。"""


async def execute_simulated_refund(
    session: AsyncSession,
    refund_request_id: UUID,
    executor_staff_id: UUID,
) -> RefundExecution:
    """执行模拟全额退款，保证数据库操作的原子性。"""
    refund_request: RefundRequest | None = None
    previous_order_status: str | None = None
    refund_amount: Decimal | None = None
    committed = False

    try:
        # 1. 锁定退款申请
        stmt = (
            select(RefundRequest)
            .where(RefundRequest.id == refund_request_id)
            .with_for_update()
        )

        refund_request = await session.scalar(stmt)

        if refund_request is None:
            raise RefundExecutionError("退款申请不存在")

        # 2. 只有审核通过才能执行退款
        if refund_request.status != "approved":
            raise RefundExecutionError("退款申请尚未审核通过")

        # 3. 检查是否已经执行过退款
        existing = await session.scalar(
            select(RefundExecution).where(
                RefundExecution.refund_request_id
                == refund_request_id
            )
        )

        if existing is not None:
            if existing.status == "succeeded":
                await session.commit()
                await session.refresh(existing)
                return existing

            raise RefundExecutionError(
                "已有未成功的退款执行记录，需要人工检查"
            )

        # 4. 锁定订单
        order = await session.scalar(
            select(Order)
            .where(Order.id == refund_request.order_id)
            .with_for_update()
        )

        if order is None:
            raise RefundExecutionError("关联订单不存在")

        previous_order_status = order.status
        refund_amount = order.total_amount

        if order.status not in REFUND_ELIGIBLE_ORDER_STATUSES:
            raise RefundExecutionError("当前订单状态不能退款")

        if order.total_amount <= Decimal("0.00"):
            raise RefundExecutionError("退款金额必须大于零")

        
        # 5. 创建模拟退款成功记录
        execution = RefundExecution(
            refund_request_id=refund_request.id,
            order_id=order.id,
            amount=order.total_amount,
            status="succeeded",
            executed_at=datetime.now(timezone.utc),
        )

        session.add(execution)

        # 先写入执行记录，确保生成 execution.id
        await session.flush()

        # 6. 更新订单状态
        order.status = "refunded"

        # 7. 创建成功审计事件
        audit_event = RefundExecutionAuditEvent(
            refund_request_id=refund_request.id,
            refund_execution_id=execution.id,
            executor_staff_id=executor_staff_id,
            event_type="succeeded",
            amount=execution.amount,
            previous_order_status=previous_order_status,
            new_order_status=order.status,
            detail="模拟退款执行成功",
        )

        session.add(audit_event)

        # 8. 退款记录、订单状态和成功审计统一提交
        await session.commit()
        committed = True

        await session.refresh(execution)

        return execution


    
    except Exception as exc:
        # 回滚未成功提交的退款业务事务
        await session.rollback()

        # 只有已找到退款申请且业务事务未成功提交时，
        # 才尝试记录失败审计事件
        if refund_request is not None and not committed:
            detail = (
                str(exc)
                if isinstance(exc, RefundExecutionError)
                else "退款执行发生内部错误"
            )

            try:
                failure_event = RefundExecutionAuditEvent(
                    refund_request_id=refund_request_id,
                    refund_execution_id=None,
                    executor_staff_id=executor_staff_id,
                    event_type="failed",
                    amount=refund_amount,
                    previous_order_status=previous_order_status,
                    new_order_status=previous_order_status,
                    detail=detail,
                )

                session.add(failure_event)
                await session.commit()

            except Exception:
                # 审计写入失败时回滚审计事务，
                # 保留并重新抛出原始业务异常
                await session.rollback()

        raise

async def get_customer_refund_execution(
    session: AsyncSession,
    refund_request_id: UUID,
    customer_id: UUID,
) -> RefundExecution | None:
    """查询指定客户自己的退款执行记录。"""

    stmt = (
        select(RefundExecution)
        .join(
            RefundRequest,
            RefundRequest.id
            == RefundExecution.refund_request_id,
        )
        .where(
            RefundExecution.refund_request_id
            == refund_request_id,
            RefundRequest.customer_id == customer_id,
        )
    )

    return await session.scalar(stmt)

