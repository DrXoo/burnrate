from __future__ import annotations

from fastapi import HTTPException, status

from burnrate.api.routes.categorization import (
    archive_category,
    categorize_transaction,
    create_category,
    delete_category,
    exclude_transaction,
    list_categories,
    list_uncategorized_transactions,
    rename_category,
    restore_transaction,
    unarchive_category,
    uncategorize_transaction,
)
from burnrate.api.schemas.categorization import (
    CategorizeTransactionRequest,
    CreateCategoryRequest,
    RenameCategoryRequest,
)
from burnrate.services.categorization_service import (
    CategoryInUseError,
    CategoryNameTakenError,
)
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

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def delete_category(self, *, category_id: str):
        if category_id == "cat-used":
            raise CategoryInUseError("Category 'Gym' is still used by 2 budgets")
        if category_id != "cat-1":
            raise ValueError(f"Category not found for id {category_id}")
        self.calls.append(("delete", category_id))

    def archive_category(self, *, category_id: str):
        if category_id == "cat-used":
            raise CategoryInUseError(
                "Category 'Gym' cannot be archived yet: it has a budget for this month or later"
            )
        if category_id != "cat-1":
            raise ValueError(f"Category not found for id {category_id}")
        self.calls.append(("archive", category_id))
        return {"category_id": category_id, "name": "Food", "type": "expense", "active": False}

    def unarchive_category(self, *, category_id: str):
        if category_id != "cat-1":
            raise ValueError(f"Category not found for id {category_id}")
        self.calls.append(("unarchive", category_id))
        return {"category_id": category_id, "name": "Food", "type": "expense", "active": True}

    def rename_category(self, *, category_id: str, name: str):
        if category_id != "cat-1":
            raise ValueError(f"Category not found for id {category_id}")
        if name.lower() == "taken":
            # The type the real service raises. A plain ValueError here would agree
            # with a route that recognised the conflict by its wording instead.
            raise CategoryNameTakenError(f"Category '{name}' already exists")
        return {
            "category_id": category_id,
            "name": name,
            "type": "expense",
            "active": True,
        }

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

    def exclude_transaction(self, *, transaction_id: str):
        return {
            "transaction_id": transaction_id,
            "category_id": None,
            "category_name": None,
            "message": "Transaction excluded from the budget",
        }

    def restore_transaction(self, *, transaction_id: str):
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
    renamed_response = rename_category(
        category_id="cat-1",
        request=RenameCategoryRequest(name="Eating out"),
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
    exclude_response = exclude_transaction(
        transaction_id="tx-1",
        service=service,
    )
    restore_response = restore_transaction(
        transaction_id="tx-1",
        service=service,
    )

    assert categories_response.categories[0].name == "Food"
    assert created_response.name == "Transport"
    assert renamed_response.category_id == "cat-1"
    assert renamed_response.name == "Eating out"
    assert unknown_response.transactions[0].description == "Coffee shop"
    assert categorize_response.category_name == "Food"
    assert uncategorize_response.category_id is None
    assert exclude_response.message == "Transaction excluded from the budget"
    assert restore_response.message == "Transaction returned to unknown queue"


def test_app_exposes_phase_3_categorization_paths() -> None:
    app = create_app()
    operations = app.openapi()["paths"]
    paths = set(operations.keys())

    assert "/api/v1/categories" in paths
    # The method, not just the path: a rename mounted as POST would answer at the
    # same path and still be the wrong verb for an edit in place.
    assert "patch" in operations["/api/v1/categories/{category_id}"]
    assert "delete" in operations["/api/v1/categories/{category_id}"]
    assert "/api/v1/categories/{category_id}/archive" in paths
    assert "/api/v1/categories/{category_id}/unarchive" in paths
    assert "/api/v1/transactions/uncategorized" in paths
    assert "/api/v1/transactions/{transaction_id}/categorize" in paths
    assert "/api/v1/transactions/{transaction_id}/uncategorize" in paths
    assert "/api/v1/transactions/{transaction_id}/exclude" in paths
    assert "/api/v1/transactions/{transaction_id}/restore" in paths


def test_renaming_an_unknown_category_is_reported_as_404() -> None:
    try:
        rename_category(
            category_id="cat-404",
            request=RenameCategoryRequest(name="Anything"),
            service=FakeCategorizationService(),
        )
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_404_NOT_FOUND
    else:
        raise AssertionError("expected a missing category to be reported as 404")


def test_renaming_onto_a_taken_name_is_reported_as_409() -> None:
    """A name clash is the owner picking a name that is already in use, not a
    malformed request -- 409 lets the web UI tell the two apart."""
    try:
        rename_category(
            category_id="cat-1",
            request=RenameCategoryRequest(name="Taken"),
            service=FakeCategorizationService(),
        )
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_409_CONFLICT
        assert exc.detail == "Category 'Taken' already exists"
    else:
        raise AssertionError("expected a taken name to be reported as 409")


def test_archiving_and_unarchiving_report_the_category_state() -> None:
    service = FakeCategorizationService()

    archived = archive_category(category_id="cat-1", service=service)
    restored = unarchive_category(category_id="cat-1", service=service)

    assert archived.active is False
    assert restored.active is True
    assert service.calls == [("archive", "cat-1"), ("unarchive", "cat-1")]


def test_deleting_a_category_reaches_the_service() -> None:
    service = FakeCategorizationService()

    delete_category(category_id="cat-1", service=service)

    assert service.calls == [("delete", "cat-1")]


def test_deleting_a_category_still_in_use_is_reported_as_409() -> None:
    """The reason is the body, because it is the only thing that tells the owner what
    to clear before trying again."""
    try:
        delete_category(category_id="cat-used", service=FakeCategorizationService())
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_409_CONFLICT
        assert exc.detail == "Category 'Gym' is still used by 2 budgets"
    else:
        raise AssertionError("expected a referenced category to be reported as 409")


def test_archiving_a_blocked_category_is_reported_as_409() -> None:
    try:
        archive_category(category_id="cat-used", service=FakeCategorizationService())
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_409_CONFLICT
        assert "budget for this month or later" in exc.detail
    else:
        raise AssertionError("expected a blocked archive to be reported as 409")


def test_deleting_an_unknown_category_is_reported_as_404() -> None:
    try:
        delete_category(category_id="cat-404", service=FakeCategorizationService())
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_404_NOT_FOUND
    else:
        raise AssertionError("expected a missing category to be reported as 404")


def test_deleting_a_category_answers_with_no_content() -> None:
    app = create_app()
    operations = app.openapi()["paths"]["/api/v1/categories/{category_id}"]["delete"]

    # Nothing useful to report on success, and a 200 with an empty body invites a
    # client to look for one.
    assert "204" in operations["responses"]


def test_categorization_service_is_built_with_the_owners_timezone() -> None:
    """Archiving turns on whether a budget still reaches the current month, so this
    service resolves "this month" -- and in UTC it would resolve the wrong one for
    part of every month-end. The wiring is what decides that, not the service."""
    from burnrate.api.dependencies import get_categorization_service
    from burnrate.config import Settings

    settings = Settings(APP_TIMEZONE="Europe/Madrid", DATABASE_URL="sqlite:///ignored.db")

    service = get_categorization_service(db=None, settings=settings)

    assert service._timezone_name == "Europe/Madrid"


def test_creating_a_category_with_a_taken_name_is_reported_as_409() -> None:
    """The same exception from the same shared check, so the same status.

    Create answered 400 and rename 409 for one `CategoryNameTakenError`, which left a
    client branching on status handling one and not the other.
    """

    class TakenNameService:
        def create_category(self, *, name: str, category_type: str):
            raise CategoryNameTakenError(f"Category '{name}' already exists")

    try:
        create_category(
            CreateCategoryRequest(name="Food", type="expense"),
            service=TakenNameService(),
        )
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_409_CONFLICT
        assert exc.detail == "Category 'Food' already exists"
    else:
        raise AssertionError("expected a taken name to be reported as 409 on create too")
