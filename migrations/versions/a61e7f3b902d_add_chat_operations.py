"""add chat operations

Revision ID: a61e7f3b902d
Revises: c8c1fafea0b1
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a61e7f3b902d"
down_revision = "c8c1fafea0b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_observation", sa.Text(), nullable=True),
        sa.Column("reply", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(reply IS NULL AND completed_at IS NULL) OR (reply IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_chat_operations_completion_paired",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "client_request_id", name="uq_chat_operations_customer_request"),
    )
    op.create_index("ix_chat_operations_conversation_id", "chat_operations", ["conversation_id"])


def downgrade():
    op.drop_index("ix_chat_operations_conversation_id", table_name="chat_operations")
    op.drop_table("chat_operations")
