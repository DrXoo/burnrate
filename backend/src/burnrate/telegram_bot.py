from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from burnrate.config import Settings, get_settings
from burnrate.db.session import SessionLocal
from burnrate.integrations.telegram.client import TelegramAPIError, TelegramClient
from burnrate.logging_config import configure_logging
from burnrate.telegram.router import TelegramCommandRouter

logger = logging.getLogger("burnrate.telegram_bot")

ERROR_BACKOFF_SECONDS = 5.0


def retry_after_seconds(detail: Any) -> float | None:
    """Read the cooldown Telegram asked for out of a rejected response body.

    A 429 carries ``{"parameters": {"retry_after": N}}``. Anything else -- a
    plain-text body, a rejection that names no cooldown, a non-numeric or
    non-positive value -- yields ``None`` so the caller falls back to its own
    backoff rather than trusting a number it cannot read.
    """
    if not isinstance(detail, dict):
        return None
    parameters = detail.get("parameters")
    if not isinstance(parameters, dict):
        return None
    retry_after = parameters.get("retry_after")
    if isinstance(retry_after, bool) or not isinstance(retry_after, (int, float)):
        return None
    return float(retry_after) if retry_after > 0 else None


def process_update(
    update: dict[str, Any],
    *,
    client: TelegramClient,
    router: TelegramCommandRouter,
    allowed_chat_ids: set[int],
) -> int:
    """Handle a single update and return the offset to acknowledge it.

    Unauthorized or non-text updates are acknowledged (so they are not
    re-delivered) but produce no reply. The returned value is always
    ``update_id + 1`` so the caller can advance the long-poll offset.
    """
    next_offset = update["update_id"] + 1
    message = update.get("message") or update.get("edited_message")
    if not message:
        return next_offset

    text = message.get("text")
    chat_id = message.get("chat", {}).get("id")
    if text is None or chat_id is None:
        return next_offset

    if chat_id not in allowed_chat_ids:
        logger.warning("Ignoring message from unauthorized chat_id=%s", chat_id)
        return next_offset

    reply = router.handle(text)
    client.send_message(chat_id=chat_id, text=reply)
    return next_offset


def poll_once(
    *,
    client: TelegramClient,
    router: TelegramCommandRouter,
    allowed_chat_ids: set[int],
    offset: int | None,
    poll_timeout: int,
) -> int | None:
    """Fetch a batch of updates and process them, returning the new offset."""
    updates = client.get_updates(offset=offset, timeout=poll_timeout)
    for update in updates:
        try:
            offset = process_update(
                update,
                client=client,
                router=router,
                allowed_chat_ids=allowed_chat_ids,
            )
        except Exception:
            # A single failing update (e.g. sendMessage error) must not stall
            # the loop; skip past it so it is not re-delivered forever.
            logger.exception("Failed to process update %s", update.get("update_id"))
            offset = update["update_id"] + 1
    return offset


def run_polling(
    *,
    client: TelegramClient,
    router: TelegramCommandRouter,
    allowed_chat_ids: set[int],
    poll_timeout: int,
    stop: Callable[[], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    offset: int | None = None
    while not (stop and stop()):
        try:
            offset = poll_once(
                client=client,
                router=router,
                allowed_chat_ids=allowed_chat_ids,
                offset=offset,
                poll_timeout=poll_timeout,
            )
        except TelegramAPIError as error:
            # Telegram answered and refused: a 429 flood limit, a 409 from a
            # second poller, a 5xx on their side. Every one of those is
            # transient, but none is an httpx error, so before this clause
            # existed a single 429 on getUpdates propagated out of main() and
            # ended the process -- which is exactly how the bot died in
            # production after fifteen hours of healthy polling. The detail is
            # logged because the crash that taught us this recorded no
            # retry_after, leaving nothing to diagnose.
            logger.warning(
                "Telegram rejected getUpdates (%s): %s, backing off",
                error.status_code,
                error.detail,
            )
            sleep(retry_after_seconds(error.detail) or ERROR_BACKOFF_SECONDS)
        except httpx.HTTPError:
            logger.exception("Telegram polling request failed, backing off")
            sleep(ERROR_BACKOFF_SECONDS)


def main(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set; telegram bot will not start")
        return

    allowed_chat_ids = settings.telegram_allowed_chat_id_set
    if not allowed_chat_ids:
        logger.warning(
            "TELEGRAM_ALLOWED_CHAT_IDS is empty; all messages will be ignored. "
            "Message the bot and check the logs to discover your chat id."
        )

    client = TelegramClient(settings=settings)
    router = TelegramCommandRouter(
        session_factory=SessionLocal,
        timezone_name=settings.app_timezone,
    )
    logger.info("Starting telegram bot (authorized chats: %s)", len(allowed_chat_ids))
    try:
        run_polling(
            client=client,
            router=router,
            allowed_chat_ids=allowed_chat_ids,
            poll_timeout=settings.telegram_poll_timeout_seconds,
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Telegram bot shutting down")


if __name__ == "__main__":
    main()
