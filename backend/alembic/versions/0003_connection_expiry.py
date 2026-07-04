"""Add consent-expiry tracking to bank connections

Stores when a connection's PSD2 access lapses (expires_at) and when the last
expiry warning was sent (expiry_alerted_at), so the worker can warn proactively
before a connection silently stops syncing.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_connection_expiry"
down_revision = "0002_budget_is_fixed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "enable_banking_connections",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "enable_banking_connections",
        sa.Column("expiry_alerted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("enable_banking_connections", "expiry_alerted_at")
    op.drop_column("enable_banking_connections", "expires_at")
