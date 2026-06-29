from datetime import datetime, timezone

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from burnrate.integrations.enable_banking.jwt_signer import EnableBankingJWTSigner


def test_enable_banking_jwt_signer_generates_rs256_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    signer = EnableBankingJWTSigner(
        app_id="app-123",
        private_key=private_key_pem,
    )

    token = signer.generate(now=datetime(2026, 1, 1, tzinfo=timezone.utc), ttl_seconds=3600)

    assert jwt.get_unverified_header(token)["kid"] == "app-123"
    claims = jwt.decode(
        token,
        public_key_pem,
        algorithms=["RS256"],
        audience="api.enablebanking.com",
        issuer="enablebanking.com",
        options={"verify_exp": False},
    )
    assert claims["iss"] == "enablebanking.com"
    assert claims["aud"] == "api.enablebanking.com"
