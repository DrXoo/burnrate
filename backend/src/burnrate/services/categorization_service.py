from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from burnrate.db.models import Category, Transaction
from burnrate.services.ledger_service import LedgerService


class CategorizationService:
    def __init__(self, *, db: Session) -> None:
        self.db = db
        self.ledger_service = LedgerService(db=db)

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
        existing = self.db.scalar(select(Category).where(func.lower(Category.name) == normalized_name.lower()))
        if existing is not None:
            raise ValueError(f"Category '{normalized_name}' already exists")

        category = Category(name=normalized_name, type=category_type, active=True)
        self.db.add(category)
        self.db.flush()
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

        return {
            "transaction_id": str(transaction.id),
            "category_id": None,
            "category_name": None,
            "message": "Transaction returned to unknown queue",
        }

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
