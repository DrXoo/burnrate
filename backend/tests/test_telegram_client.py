from __future__ import annotations

import logging

import httpx
import pytest

from burnrate.config import Settings
from burnrate.integrations.telegram.client import TelegramAPIError, TelegramClient


def make_settings() -> Settings:
    return Settings(
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_API_BASE_URL="https://api.telegram.org",
        DATABASE_URL="sqlite+pysqlite:///:memory:",
    )


def test_get_updates_uses_bot_token_and_offset() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 1}]})

    client = TelegramClient(settings=make_settings(), transport=httpx.MockTransport(handler))

    result = client.get_updates(offset=10, timeout=30)

    assert result == [{"update_id": 1}]
    assert "/bottest-token/getUpdates" in captured["url"]
    assert "offset=10" in captured["url"]
    assert "timeout=30" in captured["url"]


def test_send_message_posts_chat_id_and_text() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["content"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    client = TelegramClient(settings=make_settings(), transport=httpx.MockTransport(handler))

    client.send_message(chat_id=42, text="hello")

    assert "/bottest-token/sendMessage" in captured["url"]
    assert '"chat_id":42' in captured["content"]
    assert '"hello"' in captured["content"]


def test_error_response_raises_telegram_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    client = TelegramClient(settings=make_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(TelegramAPIError) as exc_info:
        client.send_message(chat_id=1, text="x")

    assert exc_info.value.status_code == 401


def test_a_refusal_names_telegrams_own_description(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A Telegram 400 explains itself, and that explanation was being thrown away.

    On 2026-11-04 at 21:00 a sync notification was refused with 400 and never
    arrived: ING had imported a transaction and nothing told the owner. All the logs
    held was ``TelegramAPIError (400)`` -- the status, which is the one part of a
    Telegram error that carries no information, since every refusal of a well-formed
    request is a 400. The ``description`` is the diagnosis.

    Logged here rather than only in the notifier, which catches these to keep a
    notification failure from disturbing a sync, and so is the layer least able to
    say what went wrong.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: can't parse entities: Character '-' is reserved",
            },
        )

    client = TelegramClient(settings=make_settings(), transport=httpx.MockTransport(handler))

    with caplog.at_level(logging.WARNING, logger="burnrate.integrations.telegram.client"):
        with pytest.raises(TelegramAPIError):
            client.send_message(chat_id=1, text="x")

    logged = caplog.text
    assert "can't parse entities" in logged
    assert "/sendMessage" in logged
    assert "400" in logged
    # The bot token lives in the base path, and a log line naming the request must not
    # be the thing that spreads it further than httpx already does.
    assert "test-token" not in logged


def test_a_refusal_does_not_log_the_message_that_caused_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Telegram echoes nothing back, and this keeps it that way from our side.

    The asymmetry with the Enable Banking client is deliberate. There, the body's
    ``message`` can name an account, so only classification keys are logged. Here the
    `description` *is* the classification -- but the text that was rejected is the
    owner's own financial detail, and it is in this client's hands rather than the
    response's. It is never put in a log line.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "Bad Request: message is too long"})

    client = TelegramClient(settings=make_settings(), transport=httpx.MockTransport(handler))

    with caplog.at_level(logging.WARNING, logger="burnrate.integrations.telegram.client"):
        with pytest.raises(TelegramAPIError):
            client.send_message(chat_id=1, text="Mercadona -42.17 EUR")

    assert "Mercadona" not in caplog.text
    assert "42.17" not in caplog.text


def test_a_refusal_with_no_description_is_still_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A proxy answering with HTML must not break the reporting of the failure."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>Bad Gateway</html>")

    client = TelegramClient(settings=make_settings(), transport=httpx.MockTransport(handler))

    with caplog.at_level(logging.WARNING, logger="burnrate.integrations.telegram.client"):
        with pytest.raises(TelegramAPIError):
            client.send_message(chat_id=1, text="x")

    assert "502" in caplog.text
    assert "/sendMessage" in caplog.text
    assert "Bad Gateway" not in caplog.text
