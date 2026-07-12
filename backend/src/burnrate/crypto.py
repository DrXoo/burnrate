"""Symmetric encryption for secrets held at rest (bank session tokens).

The database, its dumps and its backups should never contain a usable bank
token. Values are encrypted with Fernet (AES-CBC + HMAC) using a key supplied
via ``BANK_TOKEN_ENCRYPTION_KEY``.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from burnrate.config import get_settings

logger = logging.getLogger("burnrate.crypto")

# Fernet tokens are urlsafe-base64 of a payload whose first byte is 0x80, which
# always encodes to this prefix. Used to tell ciphertext apart from a value
# written before encryption existed.
_FERNET_PREFIX = "gAAAAA"


@lru_cache(maxsize=1)
def _cipher_for(key: str) -> Fernet:
    return Fernet(key.encode("utf-8"))


def _cipher() -> Fernet:
    key = get_settings().bank_token_encryption_key
    if not key:
        raise RuntimeError(
            "BANK_TOKEN_ENCRYPTION_KEY is not set, so bank tokens cannot be "
            "encrypted. Generate one with: python -m burnrate.generate_auth_secrets"
        )
    return _cipher_for(key)


def generate_key() -> str:
    """Return a fresh Fernet key suitable for BANK_TOKEN_ENCRYPTION_KEY."""
    return Fernet.generate_key().decode("utf-8")


def encrypt_secret(value: str) -> str:
    return _cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    """Decrypt a stored secret.

    Values written before the encryption migration are plaintext; those are
    returned as-is (with a warning) so a partially migrated database stays
    readable. A value that *is* ciphertext but fails to decrypt means the key
    changed, which is a hard error rather than something to paper over.
    """
    if not value.startswith(_FERNET_PREFIX):
        logger.warning(
            "Read an unencrypted bank token; run 'alembic upgrade head' to encrypt stored tokens."
        )
        return value
    try:
        return _cipher().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Could not decrypt a stored bank token. BANK_TOKEN_ENCRYPTION_KEY has "
            "most likely changed; restore the original key, or reconnect the bank."
        ) from exc
