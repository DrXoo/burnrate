from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import httpx

from burnrate.config import Settings
from burnrate.integrations.enable_banking.jwt_signer import EnableBankingJWTSigner

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class EnableBankingAPIError(Exception):
    def __init__(self, *, status_code: int, detail: Any) -> None:
        super().__init__(f"Enable Banking API error ({status_code})")
        self.status_code = status_code
        self.detail = detail


class EnableBankingClient:
    def __init__(
        self,
        *,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.sleep = sleep
        self.signer = EnableBankingJWTSigner(
            app_id=settings.enable_banking_app_id,
            private_key=settings.enable_banking_private_key_value,
        )

    def list_aspsps(self, *, country: str) -> list[dict[str, Any]]:
        payload = self._request("GET", "/aspsps", params={"country": country.upper()})
        return payload.get("aspsps", [])

    def start_authorization(
        self,
        *,
        aspsp_name: str,
        aspsp_country: str,
        state: str,
        redirect_url: str,
        psu_type: str,
        valid_until: datetime,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/auth",
            json={
                "access": {"valid_until": valid_until.isoformat()},
                "aspsp": {"name": aspsp_name, "country": aspsp_country.upper()},
                "state": state,
                "redirect_url": redirect_url,
                "psu_type": psu_type,
            },
        )

    def create_session(self, *, code: str) -> dict[str, Any]:
        return self._request("POST", "/sessions", json={"code": code})

    def get_session(self, *, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}")

    def get_account_balances(self, *, account_id: str) -> dict[str, Any]:
        return self._request("GET", f"/accounts/{account_id}/balances")

    def get_account_transactions(
        self,
        *,
        account_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
        continuation_key: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if date_from is not None:
            params["date_from"] = date_from.isoformat()
        if date_to is not None:
            params["date_to"] = date_to.isoformat()
        if continuation_key:
            params["continuation_key"] = continuation_key
        return self._request("GET", f"/accounts/{account_id}/transactions", params=params)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                return self._perform_request(method, path, params=params, json=json)
            except (httpx.TransportError, EnableBankingAPIError) as exc:
                if attempt >= self.settings.enable_banking_max_retries or not self._is_retryable(exc):
                    raise
                delay = self.settings.enable_banking_retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "Enable Banking request %s %s failed (%s), retrying in %.2fs (attempt %s/%s)",
                    method,
                    path,
                    exc,
                    delay,
                    attempt + 1,
                    self.settings.enable_banking_max_retries,
                )
                self.sleep(delay)
                attempt += 1

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, httpx.TransportError):
            return True
        if isinstance(exc, EnableBankingAPIError):
            return exc.status_code in RETRYABLE_STATUS_CODES
        return False

    def _perform_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = self.signer.generate()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"

        with httpx.Client(
            base_url=self.settings.enable_banking_api_base_url,
            timeout=self.settings.enable_banking_timeout_seconds,
            headers=headers,
            transport=self.transport,
        ) as client:
            response = client.request(method, path, params=params, json=json)

        if response.is_error:
            try:
                detail: Any = response.json()
            except ValueError:
                detail = response.text
            raise EnableBankingAPIError(status_code=response.status_code, detail=detail)

        return response.json()
