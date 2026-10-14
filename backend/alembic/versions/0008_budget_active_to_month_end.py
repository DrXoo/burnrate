"""Normalise cancelled budgets to end on a month boundary

Cancelling a budget used to record *yesterday*, which left ``active_to`` on a
day in the middle of a month. A month-granular window counts in full for any
month it touches, so such a row handed the whole budget to the month the owner
cancelled in -- the opposite of what cancelling means. Cancelling now records
the last day of the month *before* the one the owner is in, so the month they
cancel in drops the budget.

This brings rows written under the old rule to the same shape: an ``active_to``
that is not its month's last day becomes the last day of the previous month,
which is the date the new rule would have written for the same cancellation.
Both edges of a budget window are then month boundaries -- ``active_from`` is
always a 1st -- so no figure has to decide what a partial month is worth.

It changes what past months report: the month each affected budget was
cancelled in loses that budget, which is the correction being made.

See ``docs/adr/0005-budget-windows-are-month-granular.md``.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_budget_active_to_month_end"
down_revision = "0007_encrypt_session_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rows already ending on their month's last day are left alone: cancelling on a
    # 1st wrote one under the old rule too, and so did cancelling a budget that had
    # not started yet, whose window is deliberately empty.
    op.execute(
        """
        UPDATE budgets
        SET active_to = (date_trunc('month', active_to) - interval '1 day')::date,
            updated_at = now()
        WHERE active_to IS NOT NULL
          AND active_to <> (date_trunc('month', active_to) + interval '1 month - 1 day')::date
        """
    )


def downgrade() -> None:
    # The cancellation day the old rule recorded is not recoverable from a month end,
    # and guessing one would move each window by an arbitrary amount. The normalised
    # dates are left in place; they are valid under either reading.
    pass
