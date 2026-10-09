from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from burnrate import telegram_bot
from burnrate.integrations.telegram.client import TelegramAPIError


class RecordingClient:
    def __init__(self, batches: list[list[dict[str, Any]]]) -> None:
        self._batches = list(batches)
        self.sent: list[tuple[int, str]] = []

    def get_updates(self, *, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        return self._batches.pop(0) if self._batches else []

    def send_message(self, *, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class StubRouter:
    def handle(self, text: str) -> str:
        return f"handled:{text}"


def message_update(update_id: int, *, chat_id: int, text: str) -> dict[str, Any]:
    return {"update_id": update_id, "message": {"text": text, "chat": {"id": chat_id}}}


def test_process_update_replies_to_authorized_chat() -> None:
    client = RecordingClient([])
    update = message_update(5, chat_id=42, text="/summary")

    offset = telegram_bot.process_update(
        update, client=client, router=StubRouter(), allowed_chat_ids={42}
    )

    assert offset == 6
    assert client.sent == [(42, "handled:/summary")]


def test_process_update_ignores_unauthorized_chat() -> None:
    client = RecordingClient([])
    update = message_update(5, chat_id=99, text="/summary")

    offset = telegram_bot.process_update(
        update, client=client, router=StubRouter(), allowed_chat_ids={42}
    )

    assert offset == 6
    assert client.sent == []


def test_process_update_skips_non_message_update() -> None:
    client = RecordingClient([])

    offset = telegram_bot.process_update(
        {"update_id": 7}, client=client, router=StubRouter(), allowed_chat_ids={42}
    )

    assert offset == 8
    assert client.sent == []


def test_process_update_handles_edited_message() -> None:
    client = RecordingClient([])
    update = {"update_id": 9, "edited_message": {"text": "/help", "chat": {"id": 42}}}

    offset = telegram_bot.process_update(
        update, client=client, router=StubRouter(), allowed_chat_ids={42}
    )

    assert offset == 10
    assert client.sent == [(42, "handled:/help")]


def test_poll_once_advances_offset_across_batch() -> None:
    updates = [
        message_update(10, chat_id=42, text="/summary"),
        message_update(11, chat_id=42, text="/unknown"),
    ]
    client = RecordingClient([updates])

    offset = telegram_bot.poll_once(
        client=client,
        router=StubRouter(),
        allowed_chat_ids={42},
        offset=None,
        poll_timeout=1,
    )

    assert offset == 12
    assert len(client.sent) == 2


def test_run_polling_backs_off_on_http_error() -> None:
    class FailingClient:
        def get_updates(self, *, offset: int | None, timeout: int) -> list[dict[str, Any]]:
            raise httpx.ConnectError("boom")

        def send_message(self, *, chat_id: int, text: str) -> None:  # pragma: no cover
            raise AssertionError("should not send")

    iterations = {"count": 0}

    def stop() -> bool:
        iterations["count"] += 1
        return iterations["count"] > 2

    sleeps: list[float] = []

    telegram_bot.run_polling(
        client=FailingClient(),
        router=StubRouter(),
        allowed_chat_ids={42},
        poll_timeout=1,
        stop=stop,
        sleep=sleeps.append,
    )

    assert sleeps == [telegram_bot.ERROR_BACKOFF_SECONDS, telegram_bot.ERROR_BACKOFF_SECONDS]


def test_run_polling_backs_off_on_telegram_api_error() -> None:
    """A rejection from Telegram must not end the process.

    This is the failure that killed the bot in production: a 429 on getUpdates
    is a TelegramAPIError, not an httpx error, so it escaped the loop's only
    except clause and propagated out of main().
    """

    class RejectingClient:
        def get_updates(self, *, offset: int | None, timeout: int) -> list[dict[str, Any]]:
            raise TelegramAPIError(status_code=429, detail={"description": "Too Many Requests"})

        def send_message(self, *, chat_id: int, text: str) -> None:  # pragma: no cover
            raise AssertionError("should not send")

    iterations = {"count": 0}

    def stop() -> bool:
        iterations["count"] += 1
        return iterations["count"] > 2

    sleeps: list[float] = []

    telegram_bot.run_polling(
        client=RejectingClient(),
        router=StubRouter(),
        allowed_chat_ids={42},
        poll_timeout=1,
        stop=stop,
        sleep=sleeps.append,
    )

    assert sleeps == [telegram_bot.ERROR_BACKOFF_SECONDS, telegram_bot.ERROR_BACKOFF_SECONDS]


def test_run_polling_waits_the_retry_after_telegram_asks_for() -> None:
    detail = {
        "error_code": 429,
        "description": "Too Many Requests: retry after 17",
        "parameters": {"retry_after": 17},
    }

    class ThrottledClient:
        def get_updates(self, *, offset: int | None, timeout: int) -> list[dict[str, Any]]:
            raise TelegramAPIError(status_code=429, detail=detail)

        def send_message(self, *, chat_id: int, text: str) -> None:  # pragma: no cover
            raise AssertionError("should not send")

    iterations = {"count": 0}

    def stop() -> bool:
        iterations["count"] += 1
        return iterations["count"] > 1

    sleeps: list[float] = []

    telegram_bot.run_polling(
        client=ThrottledClient(),
        router=StubRouter(),
        allowed_chat_ids={42},
        poll_timeout=1,
        stop=stop,
        sleep=sleeps.append,
    )

    assert sleeps == [17.0]


def test_run_polling_logs_what_telegram_rejected(caplog: pytest.LogCaptureFixture) -> None:
    """The 429 that killed the bot logged no retry_after, leaving us blind."""

    class RejectingClient:
        def get_updates(self, *, offset: int | None, timeout: int) -> list[dict[str, Any]]:
            raise TelegramAPIError(status_code=429, detail={"description": "Too Many Requests"})

        def send_message(self, *, chat_id: int, text: str) -> None:  # pragma: no cover
            raise AssertionError("should not send")

    iterations = {"count": 0}

    def stop() -> bool:
        iterations["count"] += 1
        return iterations["count"] > 1

    with caplog.at_level(logging.WARNING, logger="burnrate.telegram_bot"):
        telegram_bot.run_polling(
            client=RejectingClient(),
            router=StubRouter(),
            allowed_chat_ids={42},
            poll_timeout=1,
            stop=stop,
            sleep=lambda _: None,
        )

    logged = caplog.text
    assert "429" in logged
    assert "Too Many Requests" in logged


def test_retry_after_seconds_reads_telegram_parameters() -> None:
    assert telegram_bot.retry_after_seconds({"parameters": {"retry_after": 12}}) == 12.0


def test_retry_after_seconds_ignores_details_without_one() -> None:
    assert telegram_bot.retry_after_seconds({"description": "Bad Request"}) is None
    assert telegram_bot.retry_after_seconds("plain text body") is None
    assert telegram_bot.retry_after_seconds(None) is None
    assert telegram_bot.retry_after_seconds({"parameters": {"retry_after": "soon"}}) is None
    assert telegram_bot.retry_after_seconds({"parameters": {"retry_after": 0}}) is None
