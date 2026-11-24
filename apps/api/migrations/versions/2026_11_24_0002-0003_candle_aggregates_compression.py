"""Continuous aggregates (1m -> 5m -> 1h) and compression for candles.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24

The aggregates read only the 1-minute rows. Each bucket carries `candles`, the number of
1-minute candles it contains, so a consumer can tell a complete bucket from a partial one.
They include not-yet-materialized data (real-time), so queries never lag behind the stream.
Old materialized buckets are kept even after raw 1m rows are deleted by the retention job,
because the refresh policies only look at recent windows.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Compression: segment by series so one instrument/timeframe's rows sit together.
    op.execute(
        "ALTER TABLE candles SET ("
        "timescaledb.compress, "
        "timescaledb.compress_segmentby = 'instrument_id, timeframe', "
        "timescaledb.compress_orderby = 'ts DESC')"
    )
    op.execute("SELECT add_compression_policy('candles', INTERVAL '7 days')")

    # Creating a continuous aggregate cannot run inside a transaction.
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE MATERIALIZED VIEW candles_5m_agg
            WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
            SELECT instrument_id,
                   time_bucket(INTERVAL '5 minutes', ts) AS bucket,
                   first(open, ts) AS open,
                   max(high) AS high,
                   min(low) AS low,
                   last(close, ts) AS close,
                   sum(volume) AS volume,
                   count(*) AS candles
            FROM candles
            WHERE timeframe = '1m'
            GROUP BY instrument_id, time_bucket(INTERVAL '5 minutes', ts)
            WITH NO DATA
            """
        )
        op.execute(
            """
            CREATE MATERIALIZED VIEW candles_1h_agg
            WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
            SELECT instrument_id,
                   time_bucket(INTERVAL '1 hour', bucket) AS bucket,
                   first(open, bucket) AS open,
                   max(high) AS high,
                   min(low) AS low,
                   last(close, bucket) AS close,
                   sum(volume) AS volume,
                   sum(candles) AS candles
            FROM candles_5m_agg
            GROUP BY instrument_id, time_bucket(INTERVAL '1 hour', bucket)
            WITH NO DATA
            """
        )
        op.execute(
            "SELECT add_continuous_aggregate_policy('candles_5m_agg', "
            "start_offset => INTERVAL '2 days', end_offset => INTERVAL '5 minutes', "
            "schedule_interval => INTERVAL '5 minutes')"
        )
        op.execute(
            "SELECT add_continuous_aggregate_policy('candles_1h_agg', "
            "start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 hour', "
            "schedule_interval => INTERVAL '1 hour')"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        # Stop the refresh jobs first so a running job cannot collide with the drop.
        op.execute("SELECT remove_continuous_aggregate_policy('candles_1h_agg', if_exists => true)")
        op.execute("SELECT remove_continuous_aggregate_policy('candles_5m_agg', if_exists => true)")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS candles_1h_agg")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS candles_5m_agg")
    op.execute("SELECT remove_compression_policy('candles', if_exists => true)")
    op.execute("SELECT decompress_chunk(chunk, true) FROM show_chunks('candles') AS chunk")
    op.execute("ALTER TABLE candles SET (timescaledb.compress = false)")
