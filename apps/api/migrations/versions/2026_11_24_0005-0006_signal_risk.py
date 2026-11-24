"""Risk assessment on every signal, and a database rule that a BUY must carry its plan.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-24

`risk` holds the veto layer's record (plan, size, vetoes, limits). Older rows get `{}`: they
predate the risk engine and are shown as not risk-assessed. New rows are stored with
`risk.assessed = true`. A BUY row must have a plan and a size, or the database refuses it.
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
    op.create_check_constraint(
        "buy_has_plan",
        "signals",
        "action <> 'BUY' OR (risk ? 'plan' AND risk ? 'size' AND risk ->> 'assessed' = 'true')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_signals_buy_has_plan"), "signals", type_="check")
    op.drop_column("signals", "risk")
