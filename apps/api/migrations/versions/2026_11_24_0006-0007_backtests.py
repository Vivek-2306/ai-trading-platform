"""Backtest runs (append-only) and the out-of-sample locks (set once, never changed).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-24

`oos_locks.config_hash` may be set exactly once (NULL -> a value). After that, and for any
other change or delete, the database refuses. Like the other audit tables, the triggers guard
against mistakes; they are not a security boundary against the table's owner.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=4), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("segment", sa.String(length=16), nullable=False),
        sa.Column("config", _jsonb(), nullable=False),
        sa.Column("config_hash", sa.String(length=16), nullable=False),
        sa.Column("range_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("range_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("data_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("code_version", sa.String(length=40), nullable=False),
        sa.Column("metrics", _jsonb(), nullable=False),
        sa.Column("benchmark", _jsonb(), nullable=False),
        sa.Column("trades", _jsonb(), nullable=False),
        sa.Column("equity", _jsonb(), nullable=False),
        sa.Column("details", _jsonb(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_backtest_runs_instrument_id_instruments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backtest_runs")),
    )
    op.create_index(op.f("ix_backtest_runs_instrument_id"), "backtest_runs", ["instrument_id"])
    op.execute(
        "CREATE TRIGGER backtest_runs_append_only BEFORE UPDATE OR DELETE ON backtest_runs "
        "FOR EACH ROW EXECUTE FUNCTION forbid_audit_changes()"
    )
    op.execute(
        "CREATE TRIGGER backtest_runs_no_truncate BEFORE TRUNCATE ON backtest_runs "
        "FOR EACH STATEMENT EXECUTE FUNCTION forbid_audit_changes()"
    )

    op.create_table(
        "oos_locks",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=4), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("oos_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("config_hash", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("symbol", "timeframe", "strategy", name="pk_oos_locks"),
    )
    op.execute(
        """
        CREATE FUNCTION oos_lock_guard() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'out-of-sample locks are append-only: DELETE is not allowed'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF OLD.config_hash IS NOT NULL
               OR NEW.oos_start <> OLD.oos_start
               OR NEW.symbol <> OLD.symbol OR NEW.timeframe <> OLD.timeframe
               OR NEW.strategy <> OLD.strategy THEN
                RAISE EXCEPTION 'out-of-sample locks are append-only: this change is not allowed'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER oos_locks_guard BEFORE UPDATE OR DELETE ON oos_locks "
        "FOR EACH ROW EXECUTE FUNCTION oos_lock_guard()"
    )
    op.execute(
        "CREATE TRIGGER oos_locks_no_truncate BEFORE TRUNCATE ON oos_locks "
        "FOR EACH STATEMENT EXECUTE FUNCTION forbid_audit_changes()"
    )


def downgrade() -> None:
    op.drop_table("oos_locks")
    op.execute("DROP FUNCTION IF EXISTS oos_lock_guard()")
    op.drop_table("backtest_runs")
