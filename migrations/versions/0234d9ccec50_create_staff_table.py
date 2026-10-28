"""create staff table

Revision ID: 0234d9ccec50
Revises: 9c1cdee483d1
Create Date: 2026-10-26 21:05:01.035192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0234d9ccec50'
down_revision: Union[str, Sequence[str], None] = '9c1cdee483d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    """创建独立的员工账号表。"""

    op.create_table(
        "staff",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column(
            "role",
            sa.String(length=30),
            server_default="customer_support",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'customer_support', 'refund_reviewer')",
            name="ck_staff_role_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_staff_email"),
        "staff",
        ["email"],
        unique=True,
    )


def downgrade() -> None:
    """回滚员工账号表，不影响 LangGraph Checkpointer。"""

    op.drop_index(
        op.f("ix_staff_email"),
        table_name="staff",
    )
    op.drop_table("staff")

