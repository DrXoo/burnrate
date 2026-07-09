"""Track when a reconnect alert was sent for a bank connection

Stores when the last "reconnect needed" warning was pushed (reauth_alerted_at)
so the worker notifies once — instead of on every sync tick — when a bank
session is closed or rejects account access with a 401.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_connection_reauth_alert"
down_revision = "0004_drop_included_in_runway"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "enable_banking_connections",
        sa.Column("reauth_alerted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("enable_banking_connections", "reauth_alerted_at")
