"""Add is_fixed flag to budgets

Marks a budget as a fixed/scheduled lump payment (rent, utilities) so the
summary projection treats it as a step (paid or estimated) instead of
extrapolating a daily spend rate.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_budget_is_fixed"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column(
            "is_fixed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("budgets", "is_fixed")
