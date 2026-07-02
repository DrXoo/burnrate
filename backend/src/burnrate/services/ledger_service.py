from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from burnrate.db.models import (
    Account,
    CategorizationRule,
    Category,
    EnableBankingAccountMapping,
    EnableBankingConnection,
    Transaction,
)


@dataclass
class TransactionFilters:
    account_id: UUID | None = None
    month_start: date | None = None
    month_end: date | None = None
    status: str | None = None
    categorized: bool | None = None


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
        included_in_runway: bool,
    ) -> dict[str, Any]:
        account = self.db.get(Account, self._parse_uuid(account_id, "Account id"))
        if account is None:
            raise ValueError(f"Account not found for id {account_id}")

        if not included_in_calculations:
            included_in_runway = False
        elif included_in_runway:
            included_in_calculations = True

        account.included_in_calculations = included_in_calculations
        account.included_in_runway = included_in_runway
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
        month: str | None = None,
        status: str | None = None,
        categorized: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters = self._build_filters(
            account_id=account_id,
            month=month,
            status=status,
            categorized=categorized,
        )
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)

        base_query = self._transactions_query(filters=filters)
        total_count = self.db.scalar(select(func.count()).select_from(base_query.subquery())) or 0

        effective_date = func.coalesce(Transaction.booking_date, Transaction.value_date)
        rows = self.db.execute(
            base_query
            .order_by(effective_date.is_(None), effective_date.desc(), Transaction.created_at.desc())
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
            month=month,
            status=status,
            categorized=False,
        )
        count_query = select(func.count()).select_from(self._transactions_query(filters=filters).subquery())
        return self.db.scalar(count_query) or 0

    def _build_filters(
        self,
        *,
        account_id: str | None,
        month: str | None,
        status: str | None,
        categorized: bool | None,
    ) -> TransactionFilters:
        try:
            parsed_account_id = UUID(account_id) if account_id else None
        except ValueError as exc:
            raise ValueError("Account id must be a valid UUID") from exc
        month_start, month_end = self._parse_month(month) if month else (None, None)
        return TransactionFilters(
            account_id=parsed_account_id,
            month_start=month_start,
            month_end=month_end,
            status=status.strip().lower() if status else None,
            categorized=categorized,
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
        effective_date = func.coalesce(Transaction.booking_date, Transaction.value_date)
        if filters.month_start is not None:
            query = query.where(effective_date >= filters.month_start)
        if filters.month_end is not None:
            query = query.where(effective_date < filters.month_end)
        if filters.status is not None:
            query = query.where(func.lower(Transaction.status) == filters.status)
        if filters.categorized is True:
            query = query.where(Transaction.category_id.is_not(None))
        if filters.categorized is False:
            query = query.where(Transaction.category_id.is_(None))

        return query

    def _parse_month(self, value: str) -> tuple[date, date]:
        try:
            year_text, month_text = value.split("-", maxsplit=1)
            month_start = date(int(year_text), int(month_text), 1)
        except (TypeError, ValueError) as exc:
            raise ValueError("Month must use YYYY-MM format") from exc

        if month_start.month == 12:
            return month_start, date(month_start.year + 1, 1, 1)
        return month_start, date(month_start.year, month_start.month + 1, 1)

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
            "included_in_runway": account.included_in_runway,
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
