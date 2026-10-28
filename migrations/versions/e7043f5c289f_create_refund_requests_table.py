
"""create refund requests table

Revision ID: e7043f5c289f
Revises: 0234d9ccec50
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7043f5c289f"
down_revision: Union[str, Sequence[str], None] = "0234d9ccec50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建退款申请表，不修改 Checkpointer 相关表。"""

    op.create_table(
        "refund_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("reviewer_staff_id", sa.UUID(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_refund_requests_status_valid",
        ),
        sa.CheckConstraint(
            """
            (
                status = 'pending'
                AND reviewer_staff_id IS NULL
                AND reviewed_at IS NULL
            )
            OR
            (
                status IN ('approved', 'rejected')
                AND reviewer_staff_id IS NOT NULL
                AND reviewed_at IS NOT NULL
            )
            """,
            name="ck_refund_requests_review_fields_valid",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_refund_requests_reason_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_staff_id"],
            ["staff.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_refund_requests_customer_id",
        "refund_requests",
        ["customer_id"],
        unique=False,
    )

    op.create_index(
        "ix_refund_requests_order_id",
        "refund_requests",
        ["order_id"],
        unique=False,
    )

    op.create_index(
        "ix_refund_requests_status",
        "refund_requests",
        ["status"],
        unique=False,
    )

    # 同一订单最多只能有一个待审核或已批准的退款申请
    op.create_index(
        "uq_refund_requests_order_active",
        "refund_requests",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending', 'approved')"
        ),
    )


def downgrade() -> None:
    """回滚时只删除退款申请表。"""

    op.drop_table("refund_requests")
