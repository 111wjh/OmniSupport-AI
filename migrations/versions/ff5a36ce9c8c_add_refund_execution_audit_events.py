
"""add refund execution audit events

Revision ID: ff5a36ce9c8c
Revises: 5eba0a4535f7
Create Date: 2026-10-28 13:54:29.640355
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ff5a36ce9c8c"
down_revision: Union[str, Sequence[str], None] = "5eba0a4535f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建退款执行审计表。"""

    op.create_table(
        "refund_execution_audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("refund_request_id", sa.UUID(), nullable=False),
        sa.Column("refund_execution_id", sa.UUID(), nullable=True),
        sa.Column("executor_staff_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "previous_order_status",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column(
            "new_order_status",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('succeeded', 'failed')",
            name="ck_refund_execution_audit_event_type",
        ),
        sa.CheckConstraint(
            "amount IS NULL OR amount > 0",
            name="ck_refund_execution_audit_amount_positive",
        ),
        sa.ForeignKeyConstraint(
            ["executor_staff_id"],
            ["staff.id"],
        ),
        sa.ForeignKeyConstraint(
            ["refund_execution_id"],
            ["refund_executions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["refund_request_id"],
            ["refund_requests.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "refund_execution_id",
            name="uq_refund_execution_audit_execution",
        ),
    )

    op.create_index(
        op.f("ix_refund_execution_audit_events_executor_staff_id"),
        "refund_execution_audit_events",
        ["executor_staff_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_refund_execution_audit_events_refund_request_id"),
        "refund_execution_audit_events",
        ["refund_request_id"],
        unique=False,
    )

    op.create_index(
        "ix_refund_execution_audit_request_created",
        "refund_execution_audit_events",
        ["refund_request_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """删除退款执行审计表。"""

    op.drop_index(
        "ix_refund_execution_audit_request_created",
        table_name="refund_execution_audit_events",
    )

    op.drop_index(
        op.f("ix_refund_execution_audit_events_refund_request_id"),
        table_name="refund_execution_audit_events",
    )

    op.drop_index(
        op.f("ix_refund_execution_audit_events_executor_staff_id"),
        table_name="refund_execution_audit_events",
    )

    op.drop_table("refund_execution_audit_events")
