"""make refund audit events append only

Revision ID: e8d7e8c07740
Revises: e33768147e6d
Create Date: 2026-10-27 22:43:38.418171

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8d7e8c07740'
down_revision: Union[str, Sequence[str], None] = 'e33768147e6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    """禁止修改或删除退款审计历史记录。"""

    op.execute("""
        CREATE OR REPLACE FUNCTION
        prevent_refund_audit_events_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'refund_audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_refund_audit_events_append_only
        BEFORE UPDATE OR DELETE
        ON refund_audit_events
        FOR EACH ROW
        EXECUTE FUNCTION
            prevent_refund_audit_events_mutation();
    """)


def downgrade() -> None:
    """移除退款审计表的只追加保护。"""

    op.execute("""
        DROP TRIGGER IF EXISTS
        trg_refund_audit_events_append_only
        ON refund_audit_events;
    """)

    op.execute("""
        DROP FUNCTION IF EXISTS
        prevent_refund_audit_events_mutation();
    """)
