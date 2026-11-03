"""Which of a category's committed spend a figure counts, as the one rule all readers use.

A hold on a Fixed Budget's category counts towards nothing until it books: the
budgeted estimate already stands for the whole commitment, so counting a partial
authorization on top would charge the owner for the same rent twice. Pending spend
on every other category is load-bearing and counts in full -- it is money the owner
has committed. See ``docs/adr/0003-pending-spend-is-load-bearing.md``.

Three places need that rule: the summary's headline figures, its per-budget rows,
and the baselines, which ask the same question of the month on screen and of every
month behind it. The first two shared a spelling; the baselines were written with
their own, which counted holds everywhere -- and the two bases met in Uncomparable
Spend, defined as the headline less the comparable half. A fixed bill held but not
booked made that residual *negative*: the dashboard hid it and the bot published
"-500.00 EUR cannot be compared".

So the rule is stated once here, in the two forms its callers need: a sum over
figures already loaded, and a criterion for a query that has not run yet. They must
agree, which is why they sit together -- the same reason ``budget_windows`` keeps
its SQL predicate beside its pure one.
"""

from __future__ import annotations

from collections.abc import Collection
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, true

from burnrate.db.models import Transaction


def counted_spend(*, booked: Decimal, pending: Decimal, is_fixed: bool) -> Decimal:
    """How much of one category's committed spend a figure counts."""
    if is_fixed:
        return booked
    return (booked + pending).quantize(Decimal("0.01"))


def spend_counts(*, fixed_category_ids: Collection[UUID]) -> ColumnElement[bool]:
    """The committed rows a figure counts: all of them, bar a hold on a fixed bill.

    Expressed as a row filter rather than as a correction applied afterwards, so a
    caller that groups by category and one that sums the lot get the same answer
    without either having to remember the exclusion.

    ``true()`` when nothing is fixed, rather than an ``IN ()`` against an empty set:
    the predicate is always safe to add to a query, so no caller needs a branch.
    """
    if not fixed_category_ids:
        return true()
    return or_(
        func.lower(Transaction.status) == "booked",
        Transaction.category_id.notin_(list(fixed_category_ids)),
    )
