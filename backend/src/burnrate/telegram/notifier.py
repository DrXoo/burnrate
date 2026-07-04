from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from burnrate.config import Settings
from burnrate.integrations.telegram.client import TelegramClient
from burnrate.services.ledger_service import LedgerService
from burnrate.services.sync_service import SyncRunResult
from burnrate.telegram.formatters import format_sync_notification

logger = logging.getLogger("burnrate.telegram_notifier")


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
    worker without any coupling to the bot process. It never raises: a single
    failed send is logged and skipped so notification problems can't disturb the
    sync run. Returns how many chats were notified.
    """
    if not settings.telegram_notify_on_sync:
        return 0

    chat_ids = settings.telegram_allowed_chat_id_set
    if not settings.telegram_bot_token or not chat_ids:
        return 0

    new_count = sum(result.transactions_imported for result in run_result.results)
    if new_count <= 0:
        return 0

    month = (now or datetime.now(UTC)).strftime("%Y-%m")
    uncategorized_count = LedgerService(db=session).get_uncategorized_transaction_count(month=month)
    text = format_sync_notification(new_count=new_count, uncategorized_count=uncategorized_count)

    sent = 0
    for chat_id in chat_ids:
        try:
            client.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception:
            logger.exception("Failed to send sync notification to chat_id=%s", chat_id)
    return sent
