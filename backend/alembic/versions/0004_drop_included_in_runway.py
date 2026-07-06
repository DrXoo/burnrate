"""Drop the account runway reserve flag

The runway feature (reserve balance divided by projected overspend) was removed
because a small overspend produced an unactionable multi-century horizon. The
per-account ``included_in_runway`` reserve toggle only fed that feature, so the
column and its index go with it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_drop_included_in_runway"
down_revision = "0003_connection_expiry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_accounts_included_in_runway", table_name="accounts")
    op.drop_column("accounts", "included_in_runway")


def downgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "included_in_runway",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_accounts_included_in_runway", "accounts", ["included_in_runway"])
