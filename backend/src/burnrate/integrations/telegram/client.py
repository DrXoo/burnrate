from __future__ import annotations

import logging
from typing import Any

import httpx

from burnrate.config import Settings

logger = logging.getLogger(__name__)


class TelegramAPIError(Exception):
    def __init__(self, *, status_code: int, detail: Any) -> None:
        super().__init__(f"Telegram API error ({status_code})")
        self.status_code = status_code
        self.detail = detail


class TelegramClient:
    """Thin synchronous wrapper over the Telegram Bot HTTP API.

    Only the two calls the read-only bot needs are exposed: long-polling for
    updates and sending a plain-text reply. Message text is sent without a
    ``parse_mode`` so category names or descriptions can never break Telegram's
    markdown parser.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self._base_path = f"/bot{settings.telegram_bot_token}"

    def get_updates(self, *, offset: int | None = None, timeout: int = 30) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        # Read timeout must outlast the long-poll window so the request does not
        # abort before Telegram returns.
        payload = self._request(
            "GET",
            "/getUpdates",
            params=params,
            read_timeout=timeout + 10,
        )
        return payload.get("result", [])

    def send_message(self, *, chat_id: int, text: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )

    @staticmethod
    def _log_refusal(path: str, status_code: int, detail: Any) -> None:
        """Say what Telegram refused with, because the status says nothing.

        Every refusal of a well-formed request is a ``400``, so the status is the one
        part of a Telegram error that carries no information -- and it was all the logs
        held. On 2026-11-04 a sync notification was refused and never arrived: ING had
        imported a transaction and nothing told the owner why the message was missing.
        ``description`` is Telegram's own diagnosis and usually names the fix.

        Reported here rather than left to the caller. ``telegram.notifier`` catches
        these so a notification failure cannot disturb a sync, which makes it the layer
        least able to explain one.

        **The rejected text is not logged, and the bot token cannot be.** The text is
        the owner's own financial detail and it is this client's to withhold; the token
        lives in the base path, so naming only the method keeps it out. Neither
        restriction applies to ``description``, which describes the request's shape.
        """
        described = detail.get("description") if isinstance(detail, dict) else None
        logger.warning(
            "Telegram refused %s with status %s%s",
            path,
            status_code,
            f": {described}" if isinstance(described, str) else "",
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        read_timeout: float | None = None,
    ) -> dict[str, Any]:
        with httpx.Client(
            base_url=f"{self.settings.telegram_api_base_url}{self._base_path}",
            timeout=read_timeout or 30.0,
            transport=self.transport,
        ) as client:
            response = client.request(method, path, params=params, json=json)

        if response.is_error:
            try:
                detail: Any = response.json()
            except ValueError:
                detail = response.text
            self._log_refusal(path, response.status_code, detail)
            raise TelegramAPIError(status_code=response.status_code, detail=detail)

        return response.json()
