from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from burnrate.clock import civil_date
from burnrate.db.budget_windows import budget_month_status, open_window_hits
from burnrate.db.effective_date import month_window
from burnrate.db.models import Budget, Category


class BudgetService:
    def __init__(
        self,
        *,
        db: Session,
        timezone_name: str = "UTC",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self._timezone_name = timezone_name
        self._clock = clock or (lambda: datetime.now(UTC))

    def _civil_today(self) -> date:
        """The owner's calendar day, which decides every budget's status.

        The clock is injectable for the reason given in ``burnrate.clock``.
        """
        return civil_date(timezone_name=self._timezone_name, instant=self._clock())

    def _civil_month_window(self) -> tuple[date, date]:
        """The window of the month the owner is in, for when no month was asked for."""
        today = self._civil_today()
        return month_window(f"{today.year:04d}-{today.month:02d}")

    def _month_window(self, month: str | None) -> tuple[date, date]:
        """The window of the month asked for, falling back to the owner's own.

        The single seam for that fallback. Every operation that reports a budget's
        status answers for the month on screen, and the three that mutate used to
        read the owner's clock instead -- so a cancel issued from September wrote
        October's window.
        """
        return month_window(month) if month else self._civil_month_window()

    def _load_budget_with_category(self, budget_id: str) -> tuple[Budget, Category]:
        """The budget and the category it belongs to, or a not-found error.

        The four lines every mutating operation opened with, written once so the
        month rule above has one place to be read from rather than three.
        """
        budget = self.db.get(Budget, self._parse_uuid(budget_id, "Budget id"))
        if budget is None:
            raise ValueError(f"Budget not found for id {budget_id}")
        category = self.db.get(Category, budget.category_id)
        assert category is not None
        return budget, category

    def _serialize_for_month(
        self,
        *,
        budget: Budget,
        category: Category,
        month: str | None,
    ) -> dict[str, Any]:
        month_start, month_end = self._month_window(month)
        return self._serialize_budget(
            budget=budget,
            category=category,
            month_start=month_start,
            month_end=month_end,
            siblings=self._budgets_for_category(budget.category_id),
        )

    def list_budgets(self, *, month: str | None = None) -> list[dict[str, Any]]:
        """Every budget row, with each one's status read against the month on screen.

        ``month`` is the month being viewed, defaulting to the one the owner is in.
        It decides the status rather than the owner's day, so the rows agree with the
        totals the summary derives for that same month -- see ``budget_windows``.
        """
        rows = self.db.execute(
            select(Budget, Category)
            .join(Category, Category.id == Budget.category_id)
            .order_by(Category.name.asc(), Budget.active_from.desc(), Budget.created_at.desc())
        ).all()
        month_start, month_end = self._month_window(month)

        # Whether a row can be reopened is asked against the category's other rows,
        # and every row is already here -- this query takes no filter. Grouping them
        # keeps the listing to one statement however much history a category carries;
        # asked one row at a time, the cost grew with the owner's edit log rather than
        # with the month on screen.
        by_category: dict[UUID, list[Budget]] = {}
        for budget, _ in rows:
            by_category.setdefault(budget.category_id, []).append(budget)

        return [
            self._serialize_budget(
                budget=budget,
                category=category,
                month_start=month_start,
                month_end=month_end,
                siblings=by_category[budget.category_id],
            )
            for budget, category in rows
        ]

    def create_budget(
        self,
        *,
        category_id: str,
        amount: Decimal,
        currency: str,
        active_from: date,
        is_fixed: bool = False,
        month: str | None = None,
    ) -> dict[str, Any]:
        category = self._resolve_budget_category(category_id)
        normalized_currency = self._normalize_currency(currency)
        normalized_amount = self._normalize_amount(amount)
        self._validate_month_start(active_from)

        previous_budget = self._find_open_budget_before_date(
            category_id=category.id,
            active_from=active_from,
        )
        if previous_budget is not None:
            previous_budget.active_to = active_from - timedelta(days=1)

        if self._first_overlap(
            active_from=active_from,
            candidates=self._budgets_for_category(category.id),
        ) is not None:
            raise ValueError("Budget periods must not overlap for the same category")

        budget = Budget(
            category_id=category.id,
            amount=normalized_amount,
            currency=normalized_currency,
            period_type="monthly",
            active_from=active_from,
            active_to=None,
            is_fixed=is_fixed,
        )
        self.db.add(budget)
        self.db.flush()

        return self._serialize_for_month(budget=budget, category=category, month=month)

    def update_budget(
        self,
        *,
        budget_id: str,
        amount: Decimal,
        currency: str,
        is_fixed: bool | None = None,
        month: str | None = None,
    ) -> dict[str, Any]:
        budget, category = self._load_budget_with_category(budget_id)

        budget.amount = self._normalize_amount(amount)
        budget.currency = self._normalize_currency(currency)
        if is_fixed is not None:
            budget.is_fixed = is_fixed

        return self._serialize_for_month(budget=budget, category=category, month=month)

    def deactivate_budget(self, *, budget_id: str, month: str | None = None) -> dict[str, Any]:
        """Cancel a budget from the month being viewed on.

        ``month`` is that month, defaulting to the one the owner is in. It has to be
        the month on screen: cancelling is a click on a row the owner is looking at,
        and resolving it from the server's clock instead wrote a window for a month
        they were not in.
        """
        budget, category = self._load_budget_with_category(budget_id)

        month_start, _ = self._month_window(month)
        # The last day of the month before the one being cancelled from. Cancelling
        # says the commitment is gone, the rest of that month included -- so the month
        # it is cancelled in must not hold the budget, and a month-granular window
        # counts in full for any month it touches at all, which leaves ending before
        # the month as the only way to drop it.
        #
        # It also keeps both edges on month boundaries: ``active_from`` is always a 1st
        # and ``active_to`` is always a month end, so neither can land mid-month and
        # no figure has to decide what a partial month is worth.
        #
        # A budget that never ran -- one starting that month or later -- lands with an
        # ``active_to`` before its own ``active_from``: an empty window, covering no
        # month at all. The same line handles it, so there is no second case.
        budget.active_to = month_start - timedelta(days=1)
        return self._serialize_for_month(budget=budget, category=category, month=month)

    def reactivate_budget(self, *, budget_id: str, month: str | None = None) -> dict[str, Any]:
        """Undo a cancellation: the window opens again and rolls forward.

        Cancelling never deleted anything, so this restores the same row rather than
        recreating it -- the months it already covered keep their amount, and nothing
        downstream sees a new budget appear in a month it has already reported on.
        """
        budget, category = self._load_budget_with_category(budget_id)
        blocker = self._reactivation_blocker(
            budget, category, self._budgets_for_category(budget.category_id)
        )
        if blocker is not None:
            raise ValueError(blocker)

        budget.active_to = None

        return self._serialize_for_month(budget=budget, category=category, month=month)

    def _serialize_budget(
        self,
        *,
        budget: Budget,
        category: Category,
        month_start: date,
        month_end: date,
        siblings: Iterable[Budget],
    ) -> dict[str, Any]:
        status = budget_month_status(
            active_from=budget.active_from,
            active_to=budget.active_to,
            month_start=month_start,
            month_end=month_end,
        )
        return {
            "budget_id": str(budget.id),
            "category_id": str(budget.category_id),
            "category_name": category.name,
            "category_type": category.type,
            "amount": f"{budget.amount:.2f}",
            "currency": budget.currency,
            "period_type": budget.period_type,
            "active_from": budget.active_from,
            "active_to": budget.active_to,
            "is_fixed": budget.is_fixed,
            "active": status == "active",
            "status": status,
            # Whether reopening this row would be accepted, answered by the same
            # function the endpoint refuses with. An open window has nothing to
            # reopen, so it is never offered.
            "can_reactivate": (
                budget.active_to is not None
                and self._reactivation_blocker(budget, category, siblings) is None
            ),
        }

    def _resolve_budget_category(self, category_id: str) -> Category:
        category = self.db.get(Category, self._parse_uuid(category_id, "Category id"))
        if category is None:
            raise ValueError(f"Category not found for id {category_id}")
        if not category.active:
            raise ValueError(f"Category '{category.name}' is inactive")
        if category.type != "expense":
            raise ValueError("Budgets are only supported for expense categories")
        return category

    def _find_open_budget_before_date(self, *, category_id: UUID, active_from: date) -> Budget | None:
        budgets = self.db.scalars(
            select(Budget)
            .where(Budget.category_id == category_id)
            .order_by(Budget.active_from.desc(), Budget.created_at.desc())
        ).all()
        for budget in budgets:
            if budget.active_to is None and budget.active_from < active_from:
                return budget
        return None

    def _first_overlap(
        self,
        *,
        active_from: date,
        candidates: Iterable[Budget],
        excluding: UUID | None = None,
    ) -> Budget | None:
        """The first of ``candidates`` that an open window from ``active_from`` would hit.

        One predicate for every opening. Creating a window, reopening a cancelled one
        and reporting whether a row *could* be reopened ask the same question, and
        asking it several ways is how they came to disagree: reactivation looked for a
        *later* budget, which a replacement starting the same month is not, so
        reopening produced two rows covering the same month and the summary summed
        both.

        Asked as "has this other window already closed before mine starts", which
        holds whichever side starts first. The guard it replaces could not see a
        still-open window starting *earlier* than the one being reopened -- a pair the
        service's own flows do not produce today, which is precisely why the rule
        should hold by construction rather than by reasoning across three methods.

        Every caller opens an unbounded window, so there is no end to compare against
        and none is taken: a bounded one would need a second clause, and writing that
        clause before a caller needs it is how the guard this replaces ended up
        carrying a condition that could never be false.

        Takes the rows rather than fetching them, which is what lets ``list_budgets``
        answer for every row from the ones it has already loaded. An empty window
        covers no month, so it is skipped -- through the same rule
        ``budget_month_status`` reads such a row by.
        """
        return next(
            (
                other
                for other in candidates
                if other.id != excluding
                and open_window_hits(
                    active_from=active_from,
                    other_from=other.active_from,
                    other_to=other.active_to,
                )
            ),
            None,
        )

    def _budgets_for_category(self, category_id: UUID) -> list[Budget]:
        """Every budget row for the category, for a caller that has none in hand.

        The mutating paths need the database's current answer, so they read it here.
        ``list_budgets`` already holds every row and groups them instead.
        """
        return list(
            self.db.scalars(
                select(Budget)
                .where(Budget.category_id == category_id)
                .order_by(Budget.active_from.asc(), Budget.created_at.asc())
            ).all()
        )

    def _reactivation_blocker(
        self,
        budget: Budget,
        category: Category,
        candidates: Iterable[Budget],
    ) -> str | None:
        """Why reopening this window would be refused, or ``None`` when it would not.

        Read by the endpoint that refuses and by the list that reports whether to
        offer the button at all, so the two cannot disagree. Being already open is
        not a blocker here: reopening an open window is a no-op the endpoint has
        always accepted, and the list decides separately not to offer it.

        ``candidates`` are the category's other budgets. The endpoint reads them from
        the database; the list passes the ones it has already loaded, which is what
        keeps it to a single query however much history the category carries.

        The conflicting budget is named rather than merely reported: the owner's way
        out is to deal with that other budget, and a category can hold several, so
        "periods must not overlap" on its own would not say which one is in the way.

        An archived category blocks too. A reopened budget there would count towards
        the month while nothing can be filed against it -- a budget that can only
        ever be underspent.
        """
        if not category.active:
            return f"Category '{category.name}' is inactive"

        conflict = self._first_overlap(
            active_from=budget.active_from,
            candidates=candidates,
            excluding=budget.id,
        )
        if conflict is not None:
            return (
                f"'{category.name}' has another budget starting {conflict.active_from}, "
                "so this one cannot be reactivated"
            )
        return None

    def _normalize_currency(self, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a 3-letter code")
        return normalized

    def _normalize_amount(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Budget amount must be greater than zero")
        return value.quantize(Decimal("0.01"))

    def _validate_month_start(self, value: date) -> None:
        if value.day != 1:
            raise ValueError("Budget active_from must be the first day of a month")

    def _parse_uuid(self, value: str, label: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid UUID") from exc
