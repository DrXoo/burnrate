from __future__ import annotations

from typing import Any

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from burnrate.crypto import decrypt_secret, encrypt_secret


class EncryptedText(TypeDecorator[str]):
    """A Text column that is transparently encrypted at rest.

    The application reads and writes plain strings; the database (and every dump
    or backup taken from it) only ever holds ciphertext.

    The ciphertext is randomized, so a column of this type is not searchable:
    never index it or filter on its value.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt_secret(value)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return decrypt_secret(value)
