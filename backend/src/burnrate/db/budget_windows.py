"""Which budgets a month holds, as the one rule both readers of that question use.

A budget's ``[active_from, active_to]`` window is month-granular and counts in full
for any month it touches at all -- see
``docs/adr/0005-budget-windows-are-month-granular.md``. Two places need that rule:
the summary, which sums the amounts a month holds, and the budget list, which says
whether a row applies to the month on screen. They were a SQL predicate and a
``today`` comparison written independently, and they disagreed: a rent budget
cancelled in October still counted towards September's total while the list called
it inactive in every month, because the list asked about the owner's day and the
total asked about the month.

So the rule is stated once here, in the two forms its callers need -- a criterion
for the query and a predicate for a row already loaded. They must agree, which is
why they sit together: ``budget_covers_month`` is ``budget_month_status(...) ==
"active"`` expressed in SQL.

Both read the window half-open at the end, ``[month_start, month_end)``, matching
``month_window``. ``active_to`` is inclusive -- it is the last day the budget
covered -- so it is compared against ``month_start``, never against ``month_end``.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import ColumnElement, and_, or_

from burnrate.db.models import Budget


def window_is_empty(*, active_from: date, active_to: date | None) -> bool:
    """Whether a window covers no month at all.

    Cancelling a budget that had not started yet records ``active_to`` as the day
    before ``active_from``. Such a row is inactive in every month, so it is also
    overlapped by nothing -- which is what lets a budget cancelled before it ran be
    replaced for the very month it was going to start in.

    Stated here beside the status rule because both readers need the same answer:
    ``budget_month_status`` to report inactive, and the overlap guard to let the
    replacement through.
    """
    return active_to is not None and active_to < active_from


def open_window_hits(*, active_from: date, other_from: date, other_to: date | None) -> bool:
    """Whether an open window starting on ``active_from`` overlaps another window.

    Three readers ask it: creating a window, reopening a cancelled one, and the list,
    which reports whether a cancelled row could be reopened at all. One spelling,
    because a guard that refuses and a button that offers have to agree -- two
    spellings is how the owner came to be handed a restore button that always failed.

    The other window's start never enters the comparison: an open window has no end
    to fall short of, so all that matters is whether the other has already closed
    before it begins. It is still needed to recognise an empty window, which covers
    no month and so is hit by nothing.
    """
    if window_is_empty(active_from=other_from, active_to=other_to):
        return False
    return other_to is None or other_to >= active_from


def budget_covers_month(*, month_start: date, month_end: date) -> ColumnElement[bool]:
    """The budget rows a month holds: those whose window touches it at all."""
    return and_(
        Budget.active_from < month_end,
        or_(Budget.active_to.is_(None), Budget.active_to >= month_start),
    )


def budget_month_status(
    *,
    active_from: date,
    active_to: date | None,
    month_start: date,
    month_end: date,
) -> str:
    """Where a budget's window sits relative to a month: active, scheduled or inactive.

    ``active`` means the budget counts in this month, which is the question the
    summary's total and the budget list both ask -- not "is it running right now".
    A budget cancelled mid-month is therefore still active for that month, because
    it genuinely covered it and the month's figures count it; the row's own
    ``active_to`` is what says it has since ended.

    An empty window is checked first and is inactive everywhere: cancelling a budget
    that had not started yet records ``active_to`` as the day before ``active_from``,
    which covers no month at all.
    """
    if window_is_empty(active_from=active_from, active_to=active_to):
        return "inactive"
    if active_from >= month_end:
        return "scheduled"
    if active_to is not None and active_to < month_start:
        return "inactive"
    return "active"
