from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from burnrate.services.ledger_service import LedgerService
from burnrate.services.summary_service import SummaryService
from burnrate.telegram.formatters import (
    HELP_TEXT,
    UNKNOWN_COMMAND_TEXT,
    format_budgets,
    format_summary,
    format_unknown,
)

logger = logging.getLogger(__name__)

UNKNOWN_QUEUE_LIMIT = 10


class TelegramCommandRouter:
    """Translate a chat message into a reply by calling the existing services.

    The router owns no financial logic: it opens a read-only session, delegates
    to the application services, and formats their output for Telegram.
    """

    def __init__(self, *, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def handle(self, text: str) -> str:
        command, argument = self._parse(text)
        handler = {
            "/start": self._help,
            "/help": self._help,
            "/summary": self._summary,
            "/budgets": self._budgets,
            "/unknown": self._unknown,
        }.get(command)

        if handler is None:
            return UNKNOWN_COMMAND_TEXT

        with self._session_factory() as session:
            try:
                return handler(session, argument)
            except ValueError as exc:
                return f"⚠️ {exc}"
            except Exception:
                logger.exception("Telegram command %s failed", command)
                return "⚠️ Something went wrong handling that command. Please try again."

    def _parse(self, text: str) -> tuple[str, str | None]:
        parts = text.strip().split()
        if not parts:
            return "", None
        # Strip any @BotName mention Telegram appends in group chats.
        command = parts[0].split("@", maxsplit=1)[0].lower()
        argument = parts[1] if len(parts) > 1 else None
        return command, argument

    def _help(self, session: Session, argument: str | None) -> str:
        return HELP_TEXT

    def _summary(self, session: Session, argument: str | None) -> str:
        payload = SummaryService(db=session).get_summary(month=argument)
        return format_summary(payload)

    def _budgets(self, session: Session, argument: str | None) -> str:
        payload = SummaryService(db=session).get_summary(month=argument)
        return format_budgets(payload)

    def _unknown(self, session: Session, argument: str | None) -> str:
        result = LedgerService(db=session).list_transactions(
            categorized=False,
            limit=UNKNOWN_QUEUE_LIMIT,
        )
        return format_unknown(result)
