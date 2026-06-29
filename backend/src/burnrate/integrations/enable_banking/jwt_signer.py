from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt


class EnableBankingJWTSigner:
    def __init__(
        self,
        *,
        app_id: str,
        private_key: str,
        issuer: str = "enablebanking.com",
        audience: str = "api.enablebanking.com",
    ) -> None:
        self.app_id = app_id
        self.private_key = private_key.replace("\\n", "\n")
        self.issuer = issuer
        self.audience = audience

    def generate(self, *, now: datetime | None = None, ttl_seconds: int = 3600) -> str:
        issued_at = now or datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(seconds=min(ttl_seconds, 86400))
        payload = {
            "iss": self.issuer,
            "aud": self.audience,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.app_id},
        )

