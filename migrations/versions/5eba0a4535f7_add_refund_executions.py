"""add refund executions

Revision ID: 5eba0a4535f7
Revises: e8d7e8c07740
Create Date: 2026-10-28 10:24:09.643092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5eba0a4535f7'
down_revision: Union[str, Sequence[str], None] = 'e8d7e8c07740'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建退款执行记录表。"""

    op.create_table(
        "refund_executions",

        sa.Column("id", sa.UUID(), nullable=False),

        sa.Column(
            "refund_request_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "order_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),

        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_refund_executions_status_valid",
        ),

        sa.CheckConstraint(
            "amount > 0",
            name="ck_refund_executions_amount_positive",
        ),

        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
        ),

        sa.ForeignKeyConstraint(
            ["refund_request_id"],
            ["refund_requests.id"],
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "refund_request_id",
            name="uq_refund_executions_request",
        ),
    )

    op.create_index(
        op.f("ix_refund_executions_order_id"),
        "refund_executions",
        ["order_id"],
        unique=False,
    )


def downgrade() -> None:
    """回滚退款执行表。"""

    op.drop_index(
        op.f("ix_refund_executions_order_id"),
        table_name="refund_executions",
    )

    op.drop_table("refund_executions")
