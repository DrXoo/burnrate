from __future__ import annotations

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
