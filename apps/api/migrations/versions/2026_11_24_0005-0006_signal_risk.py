"""Risk assessment on every signal, and a database rule that a BUY must carry its plan.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-24

`risk` holds the veto layer's record (plan, size, vetoes, limits). Older rows get `{}`: they
predate the risk engine and are shown as not risk-assessed. New rows are stored with
`risk.assessed = true`. A BUY row must have a plan and a size, or the database refuses it.

The conditions are wrapped in COALESCE on purpose: a CHECK passes when its result is NULL, and
`jsonb_typeof(NULL)` is NULL, which would let a BUY with no plan through.

The rule is added NOT VALID: it is enforced for every new row, but does not re-check old rows
(signals are append-only, so an old BUY without a plan could never be fixed, and the migration
would otherwise fail on any database that already produced one).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column(
            "risk",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        "ALTER TABLE signals ADD CONSTRAINT ck_signals_buy_has_plan CHECK ("
        "action <> 'BUY' OR ("
        "COALESCE(jsonb_typeof(risk -> 'plan') = 'object', false) "
        "AND COALESCE(jsonb_typeof(risk -> 'size') = 'object', false) "
        "AND COALESCE(risk ->> 'assessed' = 'true', false))) NOT VALID"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_signals_buy_has_plan"), "signals", type_="check")
    op.drop_column("signals", "risk")
