from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from burnrate.clock import civil_date
from burnrate.config import Settings
from burnrate.db.models import EnableBankingConnection
from burnrate.integrations.telegram.client import TelegramClient
from burnrate.services.connection_expiry import (
    EXPIRY_EXPIRED,
    EXPIRY_EXPIRING_SOON,
    as_utc,
    expiry_status,
)
from burnrate.services.ledger_service import LedgerService
from burnrate.services.sync_service import SyncRunResult
from burnrate.telegram.formatters import (
    format_expiry_alert,
    format_reconnect_alert,
    format_sync_notification,
)

logger = logging.getLogger("burnrate.telegram_notifier")

# Don't re-warn about the same lapsing connection more than once a day.
_ALERT_COOLDOWN = timedelta(days=1)


def send_sync_notification(
    *,
    run_result: SyncRunResult,
    session: Session,
    client: TelegramClient,
    settings: Settings,
    now: datetime | None = None,
) -> int:
    """Push a Telegram message when a sync pass imported new transactions.

    Sending is a stateless outbound call to Telegram's API, so this runs from the
    worker without any coupling to the bot process. No send can raise: a single
    failed send is logged and skipped so notification problems can't disturb the
    sync run. Returns how many chats were notified.

    ``now`` must be an aware datetime if given -- it dates the month whose unknown
    count the message quotes, and ``civil_date`` rejects a naive instant rather
    than guessing UTC for it. The worker passes nothing and gets the current
    instant; the parameter exists so tests can fix the day. This is the one
    precondition in this module that is not merely best-effort, so it is stated
    rather than defended against: silently reading a naive instant as UTC is the
    bug the guard exists to prevent, and swallowing the error here would move a
    misconfiguration into a wrong month in the message.
    """
    if not settings.telegram_notify_on_sync:
        return 0

    chat_ids = settings.telegram_allowed_chat_id_set
    if not settings.telegram_bot_token or not chat_ids:
        return 0

    new_count = sum(result.transactions_imported for result in run_result.results)
    if new_count <= 0:
        return 0

    month = civil_date(timezone_name=settings.app_timezone, instant=now).strftime("%Y-%m")
    uncategorized_count = LedgerService(db=session).get_uncategorized_transaction_count(month=month)
    text = format_sync_notification(new_count=new_count, uncategorized_count=uncategorized_count)

    return _broadcast(client=client, chat_ids=chat_ids, text=text, kind="sync notification")


def send_expiry_alerts(
    *,
    session: Session,
    client: TelegramClient,
    settings: Settings,
    now: datetime | None = None,
) -> int:
    """Warn on Telegram about connections whose consent is lapsing or has lapsed.

    Debounced per connection via ``expiry_alerted_at`` so a nearing-expiry bank is
    not re-reported every sync. Marks alerted connections and expects the caller to
    commit. Never raises. Returns how many chats were notified.
    """
    if not settings.telegram_notify_on_sync:
        return 0

    chat_ids = settings.telegram_allowed_chat_id_set
    if not settings.telegram_bot_token or not chat_ids:
        return 0

    now = now or datetime.now(UTC)
    warning_days = settings.connection_expiry_warning_days

    connections = session.scalars(
        select(EnableBankingConnection).where(
            EnableBankingConnection.active.is_(True),
            EnableBankingConnection.expires_at.is_not(None),
        )
    ).all()

    due: list[EnableBankingConnection] = []
    items: list[dict[str, object]] = []
    for connection in connections:
        status, days = expiry_status(connection.expires_at, now=now, warning_days=warning_days)
        if status not in (EXPIRY_EXPIRING_SOON, EXPIRY_EXPIRED):
            continue
        last_alerted = as_utc(connection.expiry_alerted_at)
        if last_alerted is not None and last_alerted > now - _ALERT_COOLDOWN:
            continue
        due.append(connection)
        items.append(
            {
                "aspsp_name": connection.aspsp_name,
                "expired": status == EXPIRY_EXPIRED,
                "days": days if days is not None else 0,
            }
        )

    if not due:
        return 0

    text = format_expiry_alert(items)
    sent = _broadcast(client=client, chat_ids=chat_ids, text=text, kind="expiry alert")
    if sent:
        for connection in due:
            connection.expiry_alerted_at = now
    return sent


def send_reconnect_alerts(
    *,
    run_result: SyncRunResult,
    session: Session,
    client: TelegramClient,
    settings: Settings,
    now: datetime | None = None,
) -> int:
    """Alert on Telegram when a sync pass found a connection needing re-authorization.

    Fired for the connections a sync just flagged as ``needs_reauth`` — a closed/
    expired session or a 401 rejection from the bank — so the user learns to
    reconnect immediately instead of noticing missing transactions days later.

    Debounced per connection via ``reauth_alerted_at`` so a bank that keeps
    rejecting on every tick is only reported once. A reconnect creates a fresh
    connection row, so the debounce resets naturally once access is restored.
    Marks alerted connections and expects the caller to commit. Never raises.
    Returns how many chats were notified.
    """
    if not settings.telegram_notify_on_sync:
        return 0

    chat_ids = settings.telegram_allowed_chat_id_set
    if not settings.telegram_bot_token or not chat_ids:
        return 0

    now = now or datetime.now(UTC)

    due: list[EnableBankingConnection] = []
    names: list[str] = []
    seen: set[str] = set()
    for result in run_result.results:
        if not result.needs_reauth or result.connection_id in seen:
            continue
        seen.add(result.connection_id)
        connection = session.get(EnableBankingConnection, UUID(result.connection_id))
        if connection is None:
            continue
        last_alerted = as_utc(connection.reauth_alerted_at)
        if last_alerted is not None and last_alerted > now - _ALERT_COOLDOWN:
            continue
        due.append(connection)
        names.append(connection.aspsp_name)

    if not due:
        return 0

    text = format_reconnect_alert(names)
    sent = _broadcast(client=client, chat_ids=chat_ids, text=text, kind="reconnect alert")
    if sent:
        for connection in due:
            connection.reauth_alerted_at = now
    return sent


def _broadcast(*, client: TelegramClient, chat_ids: set[int], text: str, kind: str) -> int:
    sent = 0
    for chat_id in chat_ids:
        try:
            client.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception:
            logger.exception("Failed to send %s to chat_id=%s", kind, chat_id)
    return sent
