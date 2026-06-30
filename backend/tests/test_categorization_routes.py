from __future__ import annotations

from burnrate.api.routes.categorization import (
    categorize_transaction,
    create_category,
    list_categories,
    list_uncategorized_transactions,
    uncategorize_transaction,
)
from burnrate.api.schemas.categorization import CategorizeTransactionRequest, CreateCategoryRequest
from burnrate.main import create_app


class FakeCategorizationService:
    def list_categories(self):
        return [
            {
                "category_id": "cat-1",
                "name": "Food",
                "type": "expense",
                "active": True,
            }
        ]

    def create_category(self, *, name: str, category_type: str):
        return {
            "category_id": "cat-2",
            "name": name,
            "type": category_type,
            "active": True,
        }

    def list_uncategorized_transactions(self, **_: object):
        return {
            "transactions": [
                {
                    "transaction_id": "tx-1",
                    "account_id": "acc-1",
                    "account_display_name": "Main account",
                    "booking_date": "2026-06-15",
                    "value_date": "2026-06-15",
                    "amount": "-12.50",
                    "currency": "EUR",
                    "description": "Coffee shop",
                    "merchant_name": "Cafe",
                    "counterparty_name": None,
                    "direction": "debit",
                    "status": "booked",
                    "category_id": None,
                    "category_name": None,
                    "imported_at": "2026-06-15T09:00:00+00:00",
                }
            ],
            "total_count": 1,
            "limit": 100,
            "offset": 0,
        }

    def categorize_transaction(self, *, transaction_id: str, category_id: str):
        return {
            "transaction_id": transaction_id,
            "category_id": category_id,
            "category_name": "Food",
            "message": None,
        }

    def uncategorize_transaction(self, *, transaction_id: str):
        return {
            "transaction_id": transaction_id,
            "category_id": None,
            "category_name": None,
            "message": "Transaction returned to unknown queue",
        }


def test_categorization_routes_use_service_dependency() -> None:
    service = FakeCategorizationService()

    categories_response = list_categories(service=service)
    created_response = create_category(
        CreateCategoryRequest(name="Transport", type="expense"),
        service=service,
    )
    unknown_response = list_uncategorized_transactions(
        account_id=None,
        month="2026-06",
        status_filter="booked",
        limit=100,
        offset=0,
        service=service,
    )
    categorize_response = categorize_transaction(
        transaction_id="tx-1",
        request=CategorizeTransactionRequest(category_id="cat-1"),
        service=service,
    )
    uncategorize_response = uncategorize_transaction(
        transaction_id="tx-1",
        service=service,
    )

    assert categories_response.categories[0].name == "Food"
    assert created_response.name == "Transport"
    assert unknown_response.transactions[0].description == "Coffee shop"
    assert categorize_response.category_name == "Food"
    assert uncategorize_response.category_id is None


def test_app_exposes_phase_3_categorization_paths() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"].keys())

    assert "/api/v1/categories" in paths
    assert "/api/v1/transactions/uncategorized" in paths
    assert "/api/v1/transactions/{transaction_id}/categorize" in paths
    assert "/api/v1/transactions/{transaction_id}/uncategorize" in paths
