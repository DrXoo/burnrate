from __future__ import annotations

from datetime import UTC, date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.db.base import Base
from burnrate.db.models import Account, Budget, CategorizationRule, Category, Transaction
from burnrate.services.categorization_service import (
    CategorizationService,
    CategoryInUseError,
)


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def seed_review_data(db: Session) -> tuple[Transaction, Category]:
    account = Account(
        display_name="Main account",
        currency="EUR",
        included_in_calculations=True,
        latest_balance_amount=Decimal("375.52"),
        latest_balance_currency="EUR",
        last_synced_at=datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc),
    )
    category = Category(name="Food", type="expense", active=True)
    transaction = Transaction(
        account_id=account.id,
        enable_banking_transaction_id="tx-1",
        booking_date=datetime(2026, 6, 15, tzinfo=timezone.utc).date(),
        value_date=datetime(2026, 6, 15, tzinfo=timezone.utc).date(),
        amount=Decimal("-12.50"),
        currency="EUR",
        description="Coffee shop",
        merchant_name="Cafe",
        counterparty_name=None,
        direction="debit",
        status="booked",
        category_id=None,
        matched_rule_id=None,
        raw_payload={"source": "test"},
        imported_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
    )
    db.add_all([account, category])
    db.flush()
    transaction.account_id = account.id
    db.add(transaction)
    db.commit()
    return transaction, category


def test_categorization_service_lists_and_creates_categories() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)

    created = service.create_category(name="Transport", category_type="expense")
    categories = service.list_categories()

    assert created["name"] == "Transport"
    assert created["type"] == "expense"
    assert [item["name"] for item in categories] == [category.name, "Transport"]


def test_categorization_service_lists_uncategorized_transactions() -> None:
    db = make_session()
    transaction, _ = seed_review_data(db)
    service = CategorizationService(db=db)

    response = service.list_uncategorized_transactions(month="2026-06", limit=50, offset=0)

    assert response["total_count"] == 1
    assert response["transactions"][0]["transaction_id"] == str(transaction.id)


def test_categorization_service_assigns_category_to_transaction() -> None:
    db = make_session()
    transaction, category = seed_review_data(db)
    service = CategorizationService(db=db)

    response = service.categorize_transaction(
        transaction_id=str(transaction.id),
        category_id=str(category.id),
    )
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))

    assert response["category_name"] == "Food"
    assert stored is not None
    assert stored.category_id == category.id


def test_categorization_service_can_return_transaction_to_unknown_queue() -> None:
    db = make_session()
    transaction, category = seed_review_data(db)
    service = CategorizationService(db=db)
    service.categorize_transaction(
        transaction_id=str(transaction.id),
        category_id=str(category.id),
    )
    db.commit()

    response = service.uncategorize_transaction(transaction_id=str(transaction.id))
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))

    assert response["category_id"] is None
    assert response["message"] == "Transaction returned to unknown queue"
    assert stored is not None
    assert stored.category_id is None


def test_categorization_service_excludes_transaction_from_queue() -> None:
    db = make_session()
    transaction, _ = seed_review_data(db)
    service = CategorizationService(db=db)

    response = service.exclude_transaction(transaction_id=str(transaction.id))
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))
    queue = service.list_uncategorized_transactions(month="2026-06", limit=50, offset=0)

    assert response["message"] == "Transaction excluded from the budget"
    assert stored is not None
    assert stored.excluded_at is not None
    assert stored.category_id is None
    # Excluded rows drop out of the review/unknown queue.
    assert queue["total_count"] == 0


def test_categorization_service_restores_excluded_transaction() -> None:
    db = make_session()
    transaction, _ = seed_review_data(db)
    service = CategorizationService(db=db)
    service.exclude_transaction(transaction_id=str(transaction.id))
    db.commit()

    response = service.restore_transaction(transaction_id=str(transaction.id))
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))
    queue = service.list_uncategorized_transactions(month="2026-06", limit=50, offset=0)

    assert response["message"] == "Transaction returned to unknown queue"
    assert stored is not None
    assert stored.excluded_at is None
    # Back in the queue, ready to categorize.
    assert queue["total_count"] == 1


def test_categorization_service_uncategorizing_an_ignored_transaction_returns_it_to_the_queue() -> None:
    """The response says the row is back in the queue, so it has to be there.

    Ignored and uncategorized are both "no category", and only ``excluded_at`` tells
    the queue which one it is looking at. Clearing the category alone left the row
    excluded, so the call reported a return to a queue the row never reached.
    """
    db = make_session()
    transaction, _ = seed_review_data(db)
    service = CategorizationService(db=db)
    service.exclude_transaction(transaction_id=str(transaction.id))
    db.commit()

    response = service.uncategorize_transaction(transaction_id=str(transaction.id))
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))
    queue = service.list_uncategorized_transactions(month="2026-06", limit=50, offset=0)

    assert response["message"] == "Transaction returned to unknown queue"
    assert stored is not None
    assert stored.category_id is None
    assert stored.excluded_at is None
    assert queue["total_count"] == 1


def test_categorization_service_categorizing_clears_exclusion() -> None:
    db = make_session()
    transaction, category = seed_review_data(db)
    service = CategorizationService(db=db)
    service.exclude_transaction(transaction_id=str(transaction.id))
    db.commit()

    service.categorize_transaction(
        transaction_id=str(transaction.id),
        category_id=str(category.id),
    )
    db.commit()

    stored = db.scalar(select(Transaction).where(Transaction.id == transaction.id))

    assert stored is not None
    assert stored.category_id == category.id
    # Assigning a real category is mutually exclusive with being excluded.
    assert stored.excluded_at is None


def test_categorization_service_rejects_duplicate_category_name() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)

    try:
        service.create_category(name=category.name, category_type="expense")
    except ValueError as exc:
        assert str(exc) == f"Category '{category.name}' already exists"
    else:
        raise AssertionError("Expected duplicate category creation to fail")


def test_categorization_service_renames_a_category() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)

    renamed = service.rename_category(category_id=str(category.id), name="  Eating   out  ")

    assert renamed["category_id"] == str(category.id)
    # Normalized the same way creation does, so a rename cannot smuggle in a name
    # that creation would have rejected.
    assert renamed["name"] == "Eating out"
    assert renamed["type"] == category.type
    assert db.get(Category, category.id).name == "Eating out"


def test_categorization_service_rejects_renaming_onto_an_existing_name() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)
    service.create_category(name="Transport", category_type="expense")

    try:
        # Lower-cased: the uniqueness check has to be case-insensitive, or the list
        # grows two categories the owner reads as one.
        service.rename_category(category_id=str(category.id), name="transport")
    except ValueError as exc:
        assert str(exc) == "Category 'transport' already exists"
    else:
        raise AssertionError("Expected renaming onto a taken name to fail")

    assert db.get(Category, category.id).name == category.name


def test_categorization_service_can_recase_a_category_without_colliding_with_itself() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)

    # "Food" -> "food" matches the uniqueness query case-insensitively, but the row it
    # matches is the one being renamed, which is not a collision.
    renamed = service.rename_category(category_id=str(category.id), name=category.name.lower())

    assert renamed["name"] == category.name.lower()


def test_categorization_service_rejects_renaming_an_unknown_category() -> None:
    db = make_session()
    seed_review_data(db)
    service = CategorizationService(db=db)
    missing_id = "11111111-1111-1111-1111-111111111111"

    try:
        service.rename_category(category_id=missing_id, name="Anything")
    except ValueError as exc:
        assert str(exc) == f"Category not found for id {missing_id}"
    else:
        raise AssertionError("Expected renaming an unknown category to fail")


def test_categorization_service_rejects_renaming_a_category_to_blank() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)

    try:
        service.rename_category(category_id=str(category.id), name="   ")
    except ValueError as exc:
        assert str(exc) == "Category name must not be empty"
    else:
        raise AssertionError("Expected renaming to blank to fail")

    assert db.get(Category, category.id).name == category.name


# -- Deleting and archiving ---------------------------------------------------
#
# A fixed instant, so "this month" is a decision the test makes and not one the
# calendar makes for it. Archiving turns on whether a budget still reaches the
# current month, which a fixture dated against the real clock would answer
# differently depending on the month the suite runs in.
NOW = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


def archiving_service(db: Session) -> CategorizationService:
    return CategorizationService(db=db, timezone_name="Europe/Madrid", clock=lambda: NOW)


def add_rule(db: Session, category: Category, *, active: bool = True) -> CategorizationRule:
    rule = CategorizationRule(
        name="Gym rule",
        match_field="merchant_name",
        match_operator="contains",
        match_value="gym",
        category_id=category.id,
        priority=100,
        active=active,
    )
    db.add(rule)
    db.commit()
    return rule


def add_budget(db: Session, category: Category, *, active_from: date, active_to: date | None) -> Budget:
    budget = Budget(
        category_id=category.id,
        amount=Decimal("40.00"),
        currency="EUR",
        period_type="monthly",
        active_from=active_from,
        active_to=active_to,
        is_fixed=False,
    )
    db.add(budget)
    db.commit()
    return budget


def test_categorization_service_deletes_a_category_nothing_references() -> None:
    db = make_session()
    _, kept = seed_review_data(db)
    service = CategorizationService(db=db)
    typo = service.create_category(name="Fodo", category_type="expense")
    db.commit()

    service.delete_category(category_id=typo["category_id"])
    db.commit()

    assert [item["name"] for item in service.list_categories()] == [kept.name]


def test_categorization_service_refuses_to_delete_a_category_with_transactions() -> None:
    db = make_session()
    transaction, category = seed_review_data(db)
    service = CategorizationService(db=db)
    service.categorize_transaction(transaction_id=str(transaction.id), category_id=str(category.id))
    db.commit()

    try:
        service.delete_category(category_id=str(category.id))
    except CategoryInUseError as exc:
        assert str(exc) == f"Category '{category.name}' is still used by 1 transaction"
    else:
        raise AssertionError("Expected deleting a category with transactions to fail")

    # Refused means nothing happened, not partly happened.
    assert db.get(Category, category.id) is not None


def test_categorization_service_names_every_blocker_at_once_when_refusing_a_delete() -> None:
    """One refusal has to list everything in the way.

    Reporting the first blocker only turns retiring a category into a guessing game:
    clear the transactions, get told about the budget, clear that, get told about the
    rule."""
    db = make_session()
    transaction, category = seed_review_data(db)
    service = CategorizationService(db=db)
    service.categorize_transaction(transaction_id=str(transaction.id), category_id=str(category.id))
    db.commit()
    add_budget(db, category, active_from=date(2026, 1, 1), active_to=None)
    add_rule(db, category)
    add_rule(db, category)

    try:
        service.delete_category(category_id=str(category.id))
    except CategoryInUseError as exc:
        assert str(exc) == (
            f"Category '{category.name}' is still used by 1 transaction, 1 budget and 2 rules"
        )
    else:
        raise AssertionError("Expected deleting a referenced category to fail")


def test_categorization_service_refuses_to_delete_a_category_with_only_a_budget() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = CategorizationService(db=db)
    add_budget(db, category, active_from=date(2026, 1, 1), active_to=date(2026, 3, 31))

    try:
        service.delete_category(category_id=str(category.id))
    except CategoryInUseError as exc:
        # A budget that only ever covered past months still blocks the delete: those
        # months reported it, and the row is what they reported.
        assert str(exc) == f"Category '{category.name}' is still used by 1 budget"
    else:
        raise AssertionError("Expected a historical budget to block the delete")


def test_categorization_service_refuses_to_delete_an_unknown_category() -> None:
    db = make_session()
    seed_review_data(db)
    service = CategorizationService(db=db)
    missing_id = "11111111-1111-1111-1111-111111111111"

    try:
        service.delete_category(category_id=missing_id)
    except ValueError as exc:
        assert str(exc) == f"Category not found for id {missing_id}"
    else:
        raise AssertionError("Expected deleting an unknown category to fail")


def test_categorization_service_archives_a_category_the_owner_retired() -> None:
    db = make_session()
    transaction, category = seed_review_data(db)
    service = archiving_service(db)
    service.categorize_transaction(transaction_id=str(transaction.id), category_id=str(category.id))
    db.commit()

    archived = service.archive_category(category_id=str(category.id))
    db.commit()

    assert archived["active"] is False
    # The row and its history stay: that is the whole difference from a delete.
    assert db.get(Category, category.id) is not None
    assert db.get(Transaction, transaction.id).category_id == category.id
    # And it is still listed, or there would be no way to bring it back.
    assert [item["name"] for item in service.list_categories()] == [category.name]


def test_archiving_a_category_closes_it_to_new_assignments() -> None:
    """The payoff of archiving: the three guards that already existed start biting.

    Each of them read ``Category.active`` before this and could never fire, because
    nothing could set it."""
    db = make_session()
    transaction, category = seed_review_data(db)
    service = archiving_service(db)
    service.archive_category(category_id=str(category.id))
    db.commit()

    try:
        service.categorize_transaction(
            transaction_id=str(transaction.id), category_id=str(category.id)
        )
    except ValueError as exc:
        assert str(exc) == f"Category '{category.name}' is inactive"
    else:
        raise AssertionError("Expected an archived category to refuse new transactions")


def test_categorization_service_refuses_to_archive_while_a_budget_reaches_this_month() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = archiving_service(db)
    add_budget(db, category, active_from=date(2026, 1, 1), active_to=None)

    try:
        service.archive_category(category_id=str(category.id))
    except CategoryInUseError as exc:
        assert str(exc) == (
            f"Category '{category.name}' cannot be archived yet: it has a budget for this "
            "month or later"
        )
    else:
        raise AssertionError("Expected a running budget to block archiving")

    assert db.get(Category, category.id).active is True


def test_categorization_service_refuses_to_archive_while_a_budget_is_scheduled_ahead() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = archiving_service(db)
    # Starts in December, two months after the fixed clock's October.
    add_budget(db, category, active_from=date(2026, 12, 1), active_to=None)

    try:
        service.archive_category(category_id=str(category.id))
    except CategoryInUseError as exc:
        assert "budget for this month or later" in str(exc)
    else:
        raise AssertionError("Expected a scheduled budget to block archiving")


def test_categorization_service_archives_a_category_whose_budget_already_closed() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = archiving_service(db)
    # Ended in March; October holds nothing for it, so nothing is being hidden.
    add_budget(db, category, active_from=date(2026, 1, 1), active_to=date(2026, 3, 31))

    archived = service.archive_category(category_id=str(category.id))

    assert archived["active"] is False


def test_categorization_service_refuses_to_archive_while_active_rules_target_it() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = archiving_service(db)
    add_rule(db, category)
    add_rule(db, category)

    try:
        service.archive_category(category_id=str(category.id))
    except CategoryInUseError as exc:
        # An active rule would keep filing new spend into a category the owner has
        # hidden, which is the one thing archiving is supposed to stop.
        assert str(exc) == (
            f"Category '{category.name}' cannot be archived yet: 2 active rules still "
            "target it"
        )
    else:
        raise AssertionError("Expected active rules to block archiving")


def test_categorization_service_archives_a_category_whose_rules_are_switched_off() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = archiving_service(db)
    add_rule(db, category, active=False)

    archived = service.archive_category(category_id=str(category.id))

    assert archived["active"] is False


def test_categorization_service_names_both_archive_blockers_at_once() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = archiving_service(db)
    add_budget(db, category, active_from=date(2026, 1, 1), active_to=None)
    add_rule(db, category)

    try:
        service.archive_category(category_id=str(category.id))
    except CategoryInUseError as exc:
        assert str(exc) == (
            f"Category '{category.name}' cannot be archived yet: it has a budget for this "
            "month or later and 1 active rule still targets it"
        )
    else:
        raise AssertionError("Expected both blockers to be reported together")


def test_categorization_service_brings_an_archived_category_back() -> None:
    db = make_session()
    _, category = seed_review_data(db)
    service = archiving_service(db)
    service.archive_category(category_id=str(category.id))
    db.commit()

    restored = service.unarchive_category(category_id=str(category.id))
    db.commit()

    assert restored["active"] is True
    assert db.get(Category, category.id).active is True
