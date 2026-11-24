"""Signals table, append-only (the database rejects UPDATE, DELETE and TRUNCATE).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=4), nullable=False),
        sa.Column("candle_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "action IN ('BUY', 'SELL', 'HOLD', 'NO_TRADE')", name=op.f("ck_signals_action_known")
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_signals_confidence_in_range")
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_signals_instrument_id_instruments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signals")),
        sa.UniqueConstraint(
            "instrument_id", "timeframe", "candle_ts", "rule_version", name="uq_signals_candle"
        ),
    )
    op.create_index(op.f("ix_signals_instrument_id"), "signals", ["instrument_id"])
    op.create_index(op.f("ix_signals_candle_ts"), "signals", ["candle_ts"])

    # Append-only: any attempt to change or remove history fails loudly.
    op.execute(
        """
        CREATE FUNCTION forbid_signal_changes() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'signals are append-only: % is not allowed', TG_OP
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER signals_append_only BEFORE UPDATE OR DELETE ON signals "
        "FOR EACH ROW EXECUTE FUNCTION forbid_signal_changes()"
    )
    op.execute(
        "CREATE TRIGGER signals_no_truncate BEFORE TRUNCATE ON signals "
        "FOR EACH STATEMENT EXECUTE FUNCTION forbid_signal_changes()"
    )


def downgrade() -> None:
    # Dropping the table is a deliberate schema change (a rollback), not a data edit.
    op.drop_table("signals")
    op.execute("DROP FUNCTION IF EXISTS forbid_signal_changes()")
