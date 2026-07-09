"""Add excluded_at to transactions

Lets a transaction be resolved out of the review queue without assigning it a
spending category -- for reimbursements, internal transfers, bank duplicates and
other rows that should not count as a budget line. A non-null timestamp marks the
row excluded (and records when); clearing it returns the row to the unknown queue.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_transaction_excluded"
down_revision = "0005_connection_reauth_alert"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("excluded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_transactions_excluded_at",
        "transactions",
        ["excluded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_excluded_at", table_name="transactions")
    op.drop_column("transactions", "excluded_at")
