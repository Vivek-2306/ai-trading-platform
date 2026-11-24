"""Kill switch audit log (append-only; the current state is the newest row).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24

The triggers guard against mistakes and bugs. They are not a security boundary: the table's
owner or a superuser can still disable them or drop the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kill_switch_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kill_switch_events")),
    )
    op.execute(
        """
        CREATE FUNCTION forbid_audit_changes() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit tables are append-only: % is not allowed', TG_OP
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER kill_switch_append_only BEFORE UPDATE OR DELETE ON kill_switch_events "
        "FOR EACH ROW EXECUTE FUNCTION forbid_audit_changes()"
    )
    op.execute(
        "CREATE TRIGGER kill_switch_no_truncate BEFORE TRUNCATE ON kill_switch_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION forbid_audit_changes()"
    )


def downgrade() -> None:
    op.drop_table("kill_switch_events")
    op.execute("DROP FUNCTION IF EXISTS forbid_audit_changes()")
