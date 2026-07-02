from __future__ import annotations

from typing import Any

import httpx

from burnrate import telegram_bot


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
