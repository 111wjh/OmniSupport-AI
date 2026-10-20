"""add_message_seq_to_messages

Revision ID: 199546555556
Revises: 5df281042a3a
Create Date: 2026-10-19 10:15:34.651489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '199546555556'
down_revision: Union[str, Sequence[str], None] = '5df281042a3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    """为消息表增加递增序号。"""

    op.add_column(
        "messages",
        sa.Column(
            "message_seq",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
    )

    op.create_unique_constraint(
        "uq_messages_message_seq",
        "messages",
        ["message_seq"],
    )


def downgrade() -> None:
    """回滚消息序号字段。"""

    op.drop_constraint(
        "uq_messages_message_seq",
        "messages",
        type_="unique",
    )

    op.drop_column("messages", "message_seq")

