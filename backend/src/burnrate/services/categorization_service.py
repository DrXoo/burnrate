from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from burnrate.clock import civil_date
from burnrate.db.budget_windows import budget_month_status
from burnrate.db.effective_date import month_window
from burnrate.db.models import Budget, CategorizationRule, Category, Transaction
from burnrate.services.ledger_service import LedgerService


class CategoryNameTakenError(ValueError):
    """The name is already another category's.

    A ``ValueError`` so every existing caller that catches one still does.
    """


class CategoryInUseError(ValueError):
    """Something still points at the category, so it cannot be removed or hidden.

    Carried as its own type rather than recognised by its message: the API turns it
    into a 409, and matching on wording makes the status depend on the phrasing.
    """


def _join_clauses(clauses: list[str]) -> str:
    """``[a, b, c] -> "a, b and c"``, for refusals the owner reads."""
    if len(clauses) == 1:
        return clauses[0]
    return f"{', '.join(clauses[:-1])} and {clauses[-1]}"


def _pluralize(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


class CategorizationService:
    def __init__(
        self,
        *,
        db: Session,
        timezone_name: str = "UTC",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.ledger_service = LedgerService(db=db)
        # Archiving turns on whether a budget still reaches the current month, so this
        # service needs the owner's calendar day. Injectable for the reason in
        # ``burnrate.clock``.
        self._timezone_name = timezone_name
        self._clock = clock or (lambda: datetime.now(UTC))

    def _civil_month_window(self) -> tuple[date, date]:
        today = civil_date(timezone_name=self._timezone_name, instant=self._clock())
        return month_window(f"{today.year:04d}-{today.month:02d}")

    def list_categories(self) -> list[dict[str, Any]]:
        categories = self.db.scalars(select(Category).order_by(Category.type.asc(), Category.name.asc())).all()
        return [
            {
                "category_id": str(category.id),
                "name": category.name,
                "type": category.type,
                "active": category.active,
            }
            for category in categories
        ]

    def create_category(self, *, name: str, category_type: str) -> dict[str, Any]:
        normalized_name = self._normalize_name(name)
        self._ensure_name_is_free(name=normalized_name)

        category = Category(name=normalized_name, type=category_type, active=True)
        self.db.add(category)
        self.db.flush()
        return {
            "category_id": str(category.id),
            "name": category.name,
            "type": category.type,
            "active": category.active,
        }

    def rename_category(self, *, category_id: str, name: str) -> dict[str, Any]:
        """Give an existing category a new name.

        The name is the only label the owner ever sees for a category -- budget rows,
        rules and the dashboard all read it -- so renaming here renames it everywhere
        rather than giving any one surface its own copy.
        """
        category = self._require_category(category_id)
        normalized_name = self._normalize_name(name)
        self._ensure_name_is_free(name=normalized_name, excluding=category.id)
        category.name = normalized_name
        self.db.flush()

        return {
            "category_id": str(category.id),
            "name": category.name,
            "type": category.type,
            "active": category.active,
        }

    def delete_category(self, *, category_id: str) -> None:
        """Remove a category outright, which only an unreferenced one allows.

        A category that anything points at is refused rather than cascaded: its
        budgets are what past months reported, and dropping them would change figures
        those months already published. Retiring a used category is
        ``archive_category``.
        """
        category = self._require_category(category_id)

        clauses = [
            _pluralize(count, noun)
            for count, noun in (
                (self._count_transactions(category.id), "transaction"),
                (self._count_budgets(category.id), "budget"),
                (self._count_rules(category.id), "rule"),
            )
            if count
        ]
        if clauses:
            raise CategoryInUseError(
                f"Category '{category.name}' is still used by {_join_clauses(clauses)}"
            )

        self.db.delete(category)
        self.db.flush()

    def archive_category(self, *, category_id: str) -> dict[str, Any]:
        """Hide a category from new assignments while keeping everything it recorded.

        Refused while anything would still file new spend into it, because a hidden
        category that keeps collecting is the one outcome archiving exists to prevent.
        Each blocker is the owner's to clear explicitly -- cancelling a budget and
        switching off a rule are both visible, undoable acts, and doing either
        silently here would hide them.
        """
        category = self._require_category(category_id)

        clauses = []
        if self._has_budget_reaching_this_month(category.id):
            clauses.append("it has a budget for this month or later")
        active_rules = self._count_rules(category.id, active_only=True)
        if active_rules:
            targets = "targets" if active_rules == 1 else "target"
            clauses.append(f"{_pluralize(active_rules, 'active rule')} still {targets} it")
        if clauses:
            raise CategoryInUseError(
                f"Category '{category.name}' cannot be archived yet: {_join_clauses(clauses)}"
            )

        category.active = False
        self.db.flush()
        return self._serialize(category)

    def unarchive_category(self, *, category_id: str) -> dict[str, Any]:
        """Bring an archived category back into the pickers."""
        category = self._require_category(category_id)
        category.active = True
        self.db.flush()
        return self._serialize(category)

    def _count_transactions(self, category_id: UUID) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.category_id == category_id)
        )

    def _count_budgets(self, category_id: UUID) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Budget).where(Budget.category_id == category_id)
        )

    def _count_rules(self, category_id: UUID, *, active_only: bool = False) -> int:
        query = select(func.count()).select_from(CategorizationRule).where(
            CategorizationRule.category_id == category_id
        )
        if active_only:
            query = query.where(CategorizationRule.active.is_(True))
        return self.db.scalar(query)

    def _has_budget_reaching_this_month(self, category_id: UUID) -> bool:
        """Whether any of the category's budgets still counts this month or later.

        Asked through ``budget_month_status`` rather than a predicate of its own: the
        rule for which months a budget window covers is stated once, and a third
        spelling of it here is how the two that existed before came to disagree.
        A window that closed before this month is history, and history does not block
        archiving.
        """
        month_start, month_end = self._civil_month_window()
        budgets = self.db.scalars(select(Budget).where(Budget.category_id == category_id)).all()
        return any(
            budget_month_status(
                active_from=budget.active_from,
                active_to=budget.active_to,
                month_start=month_start,
                month_end=month_end,
            )
            != "inactive"
            for budget in budgets
        )

    def _require_category(self, category_id: str) -> Category:
        category = self.db.get(Category, self._parse_uuid(category_id, "Category id"))
        if category is None:
            raise ValueError(f"Category not found for id {category_id}")
        return category

    def _serialize(self, category: Category) -> dict[str, Any]:
        return {
            "category_id": str(category.id),
            "name": category.name,
            "type": category.type,
            "active": category.active,
        }

    def list_uncategorized_transactions(
        self,
        *,
        account_id: str | None = None,
        month: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self.ledger_service.list_transactions(
            account_id=account_id,
            month=month,
            status=status,
            categorized=False,
            limit=limit,
            offset=offset,
        )

    def categorize_transaction(self, *, transaction_id: str, category_id: str) -> dict[str, Any]:
        transaction = self.db.get(Transaction, self._parse_uuid(transaction_id, "Transaction id"))
        if transaction is None:
            raise ValueError(f"Transaction not found for id {transaction_id}")

        category = self.db.get(Category, self._parse_uuid(category_id, "Category id"))
        if category is None:
            raise ValueError(f"Category not found for id {category_id}")
        if not category.active:
            raise ValueError(f"Category '{category.name}' is inactive")

        transaction.category_id = category.id
        transaction.matched_rule_id = None
        # Assigning a real category resolves the row as categorized, so it can no
        # longer also be marked excluded -- keep the two dispositions mutually exclusive.
        transaction.excluded_at = None

        return {
            "transaction_id": str(transaction.id),
            "category_id": str(category.id),
            "category_name": category.name,
            "message": None,
        }

    def uncategorize_transaction(self, *, transaction_id: str) -> dict[str, Any]:
        transaction = self.db.get(Transaction, self._parse_uuid(transaction_id, "Transaction id"))
        if transaction is None:
            raise ValueError(f"Transaction not found for id {transaction_id}")

        transaction.category_id = None
        transaction.matched_rule_id = None
        # The queue is "no category *and* not excluded", so clearing the category is
        # only half of a return to it. Without this an Ignored row answered with
        # "returned to unknown queue" and stayed out of that queue.
        transaction.excluded_at = None

        return {
            "transaction_id": str(transaction.id),
            "category_id": None,
            "category_name": None,
            "message": "Transaction returned to unknown queue",
        }

    def exclude_transaction(self, *, transaction_id: str) -> dict[str, Any]:
        """Resolve a transaction out of the review queue without a category.

        Clears any category so it stops counting toward spend/income, and stamps
        ``excluded_at`` so it drops out of the unknown queue instead of nagging.
        """
        transaction = self.db.get(Transaction, self._parse_uuid(transaction_id, "Transaction id"))
        if transaction is None:
            raise ValueError(f"Transaction not found for id {transaction_id}")

        transaction.category_id = None
        transaction.matched_rule_id = None
        transaction.excluded_at = datetime.now(UTC)

        return {
            "transaction_id": str(transaction.id),
            "category_id": None,
            "category_name": None,
            "message": "Transaction excluded from the budget",
        }

    def restore_transaction(self, *, transaction_id: str) -> dict[str, Any]:
        """Undo an exclusion, returning the transaction to the unknown queue."""
        transaction = self.db.get(Transaction, self._parse_uuid(transaction_id, "Transaction id"))
        if transaction is None:
            raise ValueError(f"Transaction not found for id {transaction_id}")

        transaction.excluded_at = None

        return {
            "transaction_id": str(transaction.id),
            "category_id": None,
            "category_name": None,
            "message": "Transaction returned to unknown queue",
        }

    def _ensure_name_is_free(self, *, name: str, excluding: UUID | None = None) -> None:
        """Reject a name another category already holds, ignoring case.

        ``excluding`` is the row being renamed: it matches its own name, and that is
        not a collision, which is what lets a category be re-cased in place.
        """
        query = select(Category).where(func.lower(Category.name) == name.lower())
        if excluding is not None:
            query = query.where(Category.id != excluding)
        if self.db.scalar(query) is not None:
            raise CategoryNameTakenError(f"Category '{name}' already exists")

    def _parse_uuid(self, value: str, label: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid UUID") from exc

    def _normalize_name(self, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("Category name must not be empty")
        return normalized
