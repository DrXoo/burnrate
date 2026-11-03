"""Retype the owner's savings-draw category from income to transfer

Money the owner moves in from another of their own accounts is not income. It is
a transfer, and ``GLOSSARY.md`` has always said Net Cash Flow excludes transfers
on both sides -- but the category carrying those credits was typed ``income``, so
every figure built on income counted them.

The live consequence, measured before this ran: October 2026 reported a net cash
flow of -354.88 while the owner's real loss for the month was -8195.88. The
difference, 7841.00, was five credits from their own savings. The reported figure
was not wrong by a rounding: it was measuring how much the *current account*
drained and calling it what the owner kept. Three months before it read the same
way, by 2000.00, 2000.00 and 1200.00.

The correction is a retype rather than a code change, because the product's rule
was already right: ``_month_income`` and ``_get_monthly_income`` both select on
``Category.type == "income"``, and a transfer category reaches neither side of
the net. Only the datum was wrong.

**It is by name, and that is the honest shape of it.** No rule distinguishes a
credit from the owner's own savings from a credit from an employer -- the
counterparty is the owner either way, and ``counterparty_name`` is NULL in 98% of
the rows this bank supplies. So this names the one category that holds them.
A second such category is retyped the same way, by its own migration, until the
product grows a way to change a category's type; it deliberately has none, so
that correcting a type stays a decision someone makes with their eyes open rather
than a control to click past (see
``docs/adr/0010-a-savings-draw-is-a-transfer.md``).

It changes what every past month reports: income falls, net cash flow falls by
the same amount, and the savings rate falls with it. That is the correction being
made, not a side effect of it. Spending is untouched -- a transfer was never on
that side.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_from_savings_is_a_transfer"
down_revision = "0008_budget_active_to_month_end"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded on the current type as well as the name, so running it against a
    # database where the category is already a transfer -- or does not exist, as a
    # fresh one will not -- is a no-op rather than an error.
    op.execute(
        """
        UPDATE categories
        SET type = 'transfer',
            updated_at = now()
        WHERE name = 'From Savings'
          AND type = 'income'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE categories
        SET type = 'income',
            updated_at = now()
        WHERE name = 'From Savings'
          AND type = 'transfer'
        """
    )
