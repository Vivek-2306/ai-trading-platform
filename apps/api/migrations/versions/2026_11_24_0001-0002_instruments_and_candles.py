"""Instruments and candles (candles is a TimescaleDB hypertable).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("asset_class", sa.String(length=16), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instruments")),
        sa.UniqueConstraint("venue", "symbol", name="uq_instruments_venue_symbol"),
    )
    op.create_table(
        "candles",
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=4), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(28, 10), nullable=False),
        sa.Column("high", sa.Numeric(28, 10), nullable=False),
        sa.Column("low", sa.Numeric(28, 10), nullable=False),
        sa.Column("close", sa.Numeric(28, 10), nullable=False),
        sa.Column("volume", sa.Numeric(28, 10), nullable=False),
        sa.CheckConstraint("high >= low", name=op.f("ck_candles_high_gte_low")),
        sa.CheckConstraint("volume >= 0", name=op.f("ck_candles_volume_non_negative")),
        sa.CheckConstraint(
            "timeframe IN ('1m', '5m', '1h', '1d')", name=op.f("ck_candles_timeframe_known")
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_candles_instrument_id_instruments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("instrument_id", "timeframe", "ts", name=op.f("pk_candles")),
    )
    # Time-partitioned storage: 30-day chunks keep 1m data manageable.
    op.execute(
        "SELECT create_hypertable('candles', 'ts', chunk_time_interval => INTERVAL '30 days')"
    )


def downgrade() -> None:
    op.drop_table("candles")
    op.drop_table("instruments")
