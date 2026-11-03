from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from burnrate.db.budget_windows import budget_covers_month
from burnrate.db.dispositions import awaiting_categorization, not_ignored
from burnrate.db.effective_date import effective_date, month_window, within_month
from burnrate.db.models import (
    Account,
    Budget,
    CategorizationRule,
    Category,
    EnableBankingAccountMapping,
    EnableBankingConnection,
    Transaction,
)


@dataclass
class TransactionFilters:
    account_id: UUID | None = None
    category_id: UUID | None = None
    # The half-open window as one value, so a half-specified month cannot be
    # expressed. Two independent bounds let a caller set only the start and get an
    # unfiltered query over all history instead of an error.
    month: tuple[date, date] | None = None
    status: str | None = None
    categorized: bool | None = None
    # Whether the month holds a budget for the row's category: the Budgeted /
    # Unbudgeted Spend split of ``GLOSSARY.md``, as a row filter. It says nothing
    # without a month, and ``_build_filters`` is what refuses that pair.
    budgeted: bool | None = None


class LedgerService:
    def __init__(self, *, db: Session) -> None:
        self.db = db

    def list_accounts(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Account, EnableBankingAccountMapping, EnableBankingConnection)
            .outerjoin(
                EnableBankingAccountMapping,
                EnableBankingAccountMapping.account_id == Account.id,
            )
            .outerjoin(
                EnableBankingConnection,
                EnableBankingConnection.id == EnableBankingAccountMapping.enable_banking_connection_id,
            )
            .order_by(Account.display_name.asc(), Account.created_at.asc())
        ).all()

        return [
            self._serialize_account(
                account=account,
                mapping=mapping,
                connection=connection,
            )
            for account, mapping, connection in rows
        ]

    def update_account(
        self,
        *,
        account_id: str,
        included_in_calculations: bool,
    ) -> dict[str, Any]:
        account = self.db.get(Account, self._parse_uuid(account_id, "Account id"))
        if account is None:
            raise ValueError(f"Account not found for id {account_id}")

        account.included_in_calculations = included_in_calculations
        self.db.flush()

        row = self.db.execute(
            select(Account, EnableBankingAccountMapping, EnableBankingConnection)
            .outerjoin(
                EnableBankingAccountMapping,
                EnableBankingAccountMapping.account_id == Account.id,
            )
            .outerjoin(
                EnableBankingConnection,
                EnableBankingConnection.id == EnableBankingAccountMapping.enable_banking_connection_id,
            )
            .where(Account.id == account.id)
        ).one()

        stored_account, mapping, connection = row
        return self._serialize_account(
            account=stored_account,
            mapping=mapping,
            connection=connection,
        )

    def list_transactions(
        self,
        *,
        account_id: str | None = None,
        category_id: str | None = None,
        month: str | None = None,
        status: str | None = None,
        categorized: bool | None = None,
        budgeted: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters = self._build_filters(
            account_id=account_id,
            category_id=category_id,
            month=month,
            status=status,
            categorized=categorized,
            budgeted=budgeted,
        )
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)

        base_query = self._transactions_query(filters=filters)
        total_count = self.db.scalar(select(func.count()).select_from(base_query.subquery())) or 0

        rows = self.db.execute(
            base_query
            .order_by(effective_date().desc(), Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return {
            "transactions": [
                {
                    "transaction_id": str(transaction.id),
                    "account_id": str(transaction.account_id),
                    "account_display_name": account_display_name,
                    "booking_date": transaction.booking_date.isoformat() if transaction.booking_date else None,
                    "value_date": transaction.value_date.isoformat() if transaction.value_date else None,
                    "amount": self._serialize_decimal(transaction.amount) or "0.00",
                    "currency": transaction.currency,
                    "description": transaction.description,
                    "merchant_name": transaction.merchant_name,
                    "counterparty_name": transaction.counterparty_name,
                    "direction": transaction.direction,
                    "status": transaction.status,
                    "category_id": str(transaction.category_id) if transaction.category_id else None,
                    "category_name": category_name,
                    "matched_rule_id": str(transaction.matched_rule_id) if transaction.matched_rule_id else None,
                    "matched_rule_name": matched_rule_name,
                    "excluded": transaction.excluded_at is not None,
                    "imported_at": transaction.imported_at.isoformat(),
                }
                for transaction, account_display_name, category_name, matched_rule_name in rows
            ],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    def get_uncategorized_transaction_count(
        self,
        *,
        account_id: str | None = None,
        month: str | None = None,
        status: str | None = None,
    ) -> int:
        filters = self._build_filters(
            account_id=account_id,
            category_id=None,
            month=month,
            status=status,
            categorized=False,
            budgeted=None,
        )
        count_query = select(func.count()).select_from(self._transactions_query(filters=filters).subquery())
        return self.db.scalar(count_query) or 0

    def _build_filters(
        self,
        *,
        account_id: str | None,
        category_id: str | None,
        month: str | None,
        status: str | None,
        categorized: bool | None,
        budgeted: bool | None,
    ) -> TransactionFilters:
        if budgeted is not None and month is None:
            # A budget covers months, so over all of history the filter has no answer
            # to give: "no budget" would have to mean "in no month at all", which is a
            # different question from the one a month-scoped view asks.
            raise ValueError("Month is required to filter by budget")
        try:
            parsed_account_id = UUID(account_id) if account_id else None
        except ValueError as exc:
            raise ValueError("Account id must be a valid UUID") from exc
        try:
            parsed_category_id = UUID(category_id) if category_id else None
        except ValueError as exc:
            raise ValueError("Category id must be a valid UUID") from exc
        return TransactionFilters(
            account_id=parsed_account_id,
            category_id=parsed_category_id,
            month=month_window(month) if month else None,
            status=status.strip().lower() if status else None,
            categorized=categorized,
            budgeted=budgeted,
        )

    def _transactions_query(self, *, filters: TransactionFilters) -> Select[Any]:
        query = (
            select(Transaction, Account.display_name, Category.name, CategorizationRule.name)
            .join(Account, Account.id == Transaction.account_id)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .outerjoin(CategorizationRule, CategorizationRule.id == Transaction.matched_rule_id)
        )

        if filters.account_id is not None:
            query = query.where(Transaction.account_id == filters.account_id)
        if filters.category_id is not None:
            query = query.where(Transaction.category_id == filters.category_id)
        if filters.month is not None:
            month_start, month_end = filters.month
            query = query.where(within_month(month_start=month_start, month_end=month_end))
        if filters.status is not None:
            query = query.where(func.lower(Transaction.status) == filters.status)
        if filters.categorized is True:
            query = query.where(Transaction.category_id.is_not(None))
        if filters.categorized is False:
            # The review/unknown queue is "needs attention": uncategorized AND not
            # already resolved by exclusion. Excluded rows still show in the full
            # ledger (categorized is None) so they can be restored.
            query = query.where(awaiting_categorization())
        if filters.budgeted is not None and filters.month is not None:
            # The month is always set here -- ``_build_filters`` refuses the pair
            # otherwise -- and reading it from the window is what keeps this branch
            # free of a second month convention.
            month_start, month_end = filters.month
            covered = self._category_budgeted_in(month_start=month_start, month_end=month_end)
            query = query.where(
                # Budgeted and Unbudgeted Spend are both defined over spending that
                # landed in an expense category, so the filter splits that set rather
                # than every row: an income category is covered by no budget and never
                # will be, and an uncategorized charge belongs to the review queue,
                # which has a filter of its own. Ignored rows are stated rather than
                # inherited from this join, for the reason ``db.dispositions`` gives.
                #
                # Account inclusion is deliberately *not* read, as no other filter on
                # this page reads it: the list describes the ledger, while only the
                # figures are account-scoped. So spend in an account left out of the
                # calculations is listed here and is absent from the dashboard's
                # unbudgeted total.
                Category.type == "expense",
                not_ignored(),
                covered if filters.budgeted else ~covered,
            )

        return query

    def _category_budgeted_in(self, *, month_start: date, month_end: date) -> ColumnElement[bool]:
        """Whether a month holds a budget for the category the row sits in.

        Correlated on the row's own category rather than joined, so a category with
        two budget rows covering one month -- which a database predating the overlap
        guard can still hold -- yields one row here instead of duplicating the
        transaction in the listing.

        Which budgets a month holds is ``budget_covers_month``'s answer, not a second
        reading of ``active_from``/``active_to`` spelled here: the owner would not
        accept a row the dashboard counts as budgeted spend appearing in a list of
        what has no budget.
        """
        return (
            select(Budget.id)
            .where(
                Budget.category_id == Transaction.category_id,
                budget_covers_month(month_start=month_start, month_end=month_end),
            )
            .exists()
        )

    def _serialize_account(
        self,
        *,
        account: Account,
        mapping: EnableBankingAccountMapping | None,
        connection: EnableBankingConnection | None,
    ) -> dict[str, Any]:
        return {
            "account_id": str(account.id),
            "display_name": account.display_name,
            "currency": account.currency,
            "latest_balance_amount": self._serialize_decimal(account.latest_balance_amount),
            "latest_balance_currency": account.latest_balance_currency,
            "included_in_calculations": account.included_in_calculations,
            "last_synced_at": account.last_synced_at.isoformat() if account.last_synced_at else None,
            "source_connection_id": str(mapping.enable_banking_connection_id) if mapping else None,
            "source_aspsp_name": connection.aspsp_name if connection else None,
            "source_aspsp_country": connection.aspsp_country if connection else None,
            "external_account_id": mapping.external_account_id if mapping else None,
        }

    def _parse_uuid(self, value: str, label: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid UUID") from exc

    def _serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value, ".2f")
