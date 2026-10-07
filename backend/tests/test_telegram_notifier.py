from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate.config import Settings
from burnrate.db.base import Base
from burnrate.db.models import Account, Category, EnableBankingConnection, Transaction
from burnrate.services.sync_service import ConnectionSyncResult, SyncRunResult
from burnrate.telegram.notifier import (
    send_expiry_alerts,
    send_reconnect_alerts,
    send_sync_notification,
)
from conftest import AHEAD_OF_UTC, BEHIND_UTC

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


def empty_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def add_connection(
    session: Session,
    *,
    name: str,
    expires_at: datetime | None,
    active: bool = True,
    alerted_at: datetime | None = None,
) -> EnableBankingConnection:
    connection = EnableBankingConnection(
        aspsp_name=name,
        aspsp_country="ES",
        psu_type="personal",
        session_id=f"sess-{name}",
        session_status="AUTHORIZED",
        expires_at=expires_at,
        expiry_alerted_at=alerted_at,
        active=active,
    )
    session.add(connection)
    session.commit()
    return connection


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


def test_expiry_alert_warns_on_soon_and_expired_and_debounces() -> None:
    session = empty_session()
    soon = add_connection(session, name="ING", expires_at=NOW + timedelta(days=3))
    add_connection(session, name="BBVA", expires_at=NOW - timedelta(days=1))
    # Healthy connection well within its window must not be reported.
    add_connection(session, name="Sabadell", expires_at=NOW + timedelta(days=60))
    client = FakeClient()

    sent = send_expiry_alerts(session=session, client=client, settings=make_settings(), now=NOW)

    assert sent == 2  # both chats notified once
    text = client.sent[0][1]
    assert "ING — access expires in 3 days" in text
    assert "BBVA — access expired" in text
    assert "Sabadell" not in text
    # Debounce: alerted_at is stamped so a second run stays quiet.
    assert soon.expiry_alerted_at is not None
    client.sent.clear()
    again = send_expiry_alerts(session=session, client=client, settings=make_settings(), now=NOW)
    assert again == 0
    assert client.sent == []


def test_expiry_alert_rewarns_after_cooldown() -> None:
    session = empty_session()
    add_connection(
        session,
        name="ING",
        expires_at=NOW + timedelta(days=2),
        alerted_at=NOW - timedelta(days=2),  # last warned two days ago
    )
    client = FakeClient()

    sent = send_expiry_alerts(session=session, client=client, settings=make_settings(), now=NOW)

    assert sent == 2
    assert "ING" in client.sent[0][1]


def test_expiry_alert_skips_inactive_and_unknown_expiry() -> None:
    session = empty_session()
    add_connection(session, name="Old", expires_at=NOW - timedelta(days=1), active=False)
    add_connection(session, name="NoExpiry", expires_at=None)
    client = FakeClient()

    sent = send_expiry_alerts(session=session, client=client, settings=make_settings(), now=NOW)

    assert sent == 0
    assert client.sent == []


def reauth_run_result(*connection_ids: str) -> SyncRunResult:
    return SyncRunResult(
        total_connections=len(connection_ids),
        results=[
            ConnectionSyncResult(
                connection_id=cid,
                aspsp_name="Bank",
                status="skipped",
                needs_reauth=True,
            )
            for cid in connection_ids
        ],
    )


def test_reconnect_alert_notifies_and_debounces() -> None:
    session = empty_session()
    connection = add_connection(session, name="ING", expires_at=None)
    client = FakeClient()

    sent = send_reconnect_alerts(
        run_result=reauth_run_result(str(connection.id)),
        session=session,
        client=client,
        settings=make_settings(),
        now=NOW,
    )

    assert sent == 2  # both chats notified once
    assert {chat_id for chat_id, _ in client.sent} == {111, 222}
    text = client.sent[0][1]
    assert "ING disconnected" in text
    assert "reconnect the account" in text
    # Debounce: reauth_alerted_at is stamped so a second run stays quiet.
    assert connection.reauth_alerted_at == NOW
    client.sent.clear()
    again = send_reconnect_alerts(
        run_result=reauth_run_result(str(connection.id)),
        session=session,
        client=client,
        settings=make_settings(),
        now=NOW,
    )
    assert again == 0
    assert client.sent == []


def test_reconnect_alert_rewarns_after_cooldown() -> None:
    session = empty_session()
    connection = add_connection(session, name="ING", expires_at=None)
    connection.reauth_alerted_at = NOW - timedelta(days=2)  # last warned two days ago
    session.commit()
    client = FakeClient()

    sent = send_reconnect_alerts(
        run_result=reauth_run_result(str(connection.id)),
        session=session,
        client=client,
        settings=make_settings(),
        now=NOW,
    )

    assert sent == 2
    assert "ING" in client.sent[0][1]


def test_reconnect_alert_ignores_healthy_results() -> None:
    session = empty_session()
    connection = add_connection(session, name="ING", expires_at=None)
    client = FakeClient()
    run = SyncRunResult(
        total_connections=1,
        succeeded=1,
        results=[
            ConnectionSyncResult(
                connection_id=str(connection.id),
                aspsp_name="ING",
                status="success",
                transactions_imported=3,
            )
        ],
    )

    sent = send_reconnect_alerts(
        run_result=run, session=session, client=client, settings=make_settings(), now=NOW
    )

    assert sent == 0
    assert client.sent == []
    assert connection.reauth_alerted_at is None


def test_reconnect_alert_skips_when_notifications_disabled() -> None:
    session = empty_session()
    connection = add_connection(session, name="ING", expires_at=None)
    client = FakeClient()

    sent = send_reconnect_alerts(
        run_result=reauth_run_result(str(connection.id)),
        session=session,
        client=client,
        settings=make_settings(TELEGRAM_NOTIFY_ON_SYNC=False),
        now=NOW,
    )

    assert sent == 0
    assert client.sent == []


AHEAD_TZ, AHEAD_INSTANT, _ = AHEAD_OF_UTC
BEHIND_TZ, BEHIND_INSTANT, _ = BEHIND_UTC

# Which month's unknown count the message quotes, as the owner's clock reads it. The
# fixture's two uncategorized transactions are dated July 2026, so each row flips if
# the month comes straight off UTC: the owner is told nothing needs a category when
# two do, or sent chasing a queue that belongs to a month they are not in.
#
# timezone, instant, the count the message quotes, what the owner is living through
SYNC_MONTH_EXAMPLES = [
    (
        AHEAD_TZ,
        AHEAD_INSTANT,
        2,
        "a sync just after their midnight, while UTC is still in June",
    ),
    (
        BEHIND_TZ,
        BEHIND_INSTANT,
        0,
        "a sync on their last evening of June, while UTC has already turned",
    ),
]


@pytest.mark.parametrize(
    ("timezone_name", "instant", "uncategorized_count", "_what_the_owner_is_living_through"),
    SYNC_MONTH_EXAMPLES,
)
def test_sync_notification_counts_the_month_the_owner_is_in(
    timezone_name: str,
    instant: datetime,
    uncategorized_count: int,
    _what_the_owner_is_living_through: str,
) -> None:
    client = FakeClient()

    send_sync_notification(
        run_result=run_result(3),
        session=make_session(),
        client=client,
        settings=make_settings(APP_TIMEZONE=timezone_name),
        now=instant,
    )

    text = client.sent[0][1]
    # The whole message, not just a substring: the behind-UTC row asserts the absence
    # of the second line, and "no such phrase" would also hold for a message that lost
    # it for an unrelated reason, or for an empty body.
    expected = ["🔔 3 new transactions imported."]
    if uncategorized_count:
        expected.append(f"{uncategorized_count} still need a category — send /unknown.")
    assert text.splitlines() == expected
