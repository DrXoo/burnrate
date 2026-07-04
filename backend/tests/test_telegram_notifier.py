from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.config import Settings
from burnrate.db.base import Base
from burnrate.db.models import Account, Category, Transaction
from burnrate.services.sync_service import ConnectionSyncResult, SyncRunResult
from burnrate.telegram.notifier import send_sync_notification

NOW = datetime(2026, 7, 4, tzinfo=UTC)


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    def send_message(self, *, chat_id: int, text: str) -> dict[str, Any]:
        self.sent.append((chat_id, text))
        return {}


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    account = Account(
        display_name="Main",
        currency="EUR",
        included_in_calculations=True,
        included_in_runway=False,
    )
    session.add(account)
    session.flush()

    # Two uncategorized transactions in the current (July) month.
    for day in (2, 3):
        session.add(
            Transaction(
                account_id=account.id,
                booking_date=date(2026, 7, day),
                amount=Decimal("-10.00"),
                currency="EUR",
                description="New charge",
                direction="debit",
                status="booked",
                category_id=None,
                imported_at=NOW,
            )
        )
    session.commit()
    return session


def make_settings(**overrides: Any) -> Settings:
    params: dict[str, Any] = {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_ALLOWED_CHAT_IDS": "111,222",
        "TELEGRAM_NOTIFY_ON_SYNC": True,
    }
    params.update(overrides)
    return Settings(**params)


def run_result(imported: int) -> SyncRunResult:
    return SyncRunResult(
        total_connections=1,
        succeeded=1,
        results=[
            ConnectionSyncResult(
                connection_id="c1",
                aspsp_name="Bank",
                status="success",
                transactions_imported=imported,
            )
        ],
    )


def test_notifies_all_allowed_chats_when_new_transactions() -> None:
    client = FakeClient()

    sent = send_sync_notification(
        run_result=run_result(3),
        session=make_session(),
        client=client,
        settings=make_settings(),
        now=NOW,
    )

    assert sent == 2
    assert {chat_id for chat_id, _ in client.sent} == {111, 222}
    text = client.sent[0][1]
    assert "3 new transactions imported" in text
    assert "2 still need a category — send /unknown." in text


def test_skips_when_no_new_transactions() -> None:
    client = FakeClient()

    sent = send_sync_notification(
        run_result=run_result(0),
        session=make_session(),
        client=client,
        settings=make_settings(),
        now=NOW,
    )

    assert sent == 0
    assert client.sent == []


def test_skips_when_notifications_disabled() -> None:
    client = FakeClient()

    sent = send_sync_notification(
        run_result=run_result(3),
        session=make_session(),
        client=client,
        settings=make_settings(TELEGRAM_NOTIFY_ON_SYNC=False),
        now=NOW,
    )

    assert sent == 0
    assert client.sent == []


def test_skips_when_no_recipients_configured() -> None:
    client = FakeClient()

    sent = send_sync_notification(
        run_result=run_result(3),
        session=make_session(),
        client=client,
        settings=make_settings(TELEGRAM_ALLOWED_CHAT_IDS=""),
        now=NOW,
    )

    assert sent == 0
    assert client.sent == []
