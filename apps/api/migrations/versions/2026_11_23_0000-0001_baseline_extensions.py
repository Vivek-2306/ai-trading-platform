"""Baseline: enable the TimescaleDB and pgvector extensions.

Revision ID: 0001
Revises:
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Time-series tables for candles and ticks (hypertables, compression, roll-ups).
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    # Vector similarity search over news and filing embeddings.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # No CASCADE on purpose: once hypertables or vector columns exist, these fail instead
    # of silently deleting data.
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS timescaledb")
