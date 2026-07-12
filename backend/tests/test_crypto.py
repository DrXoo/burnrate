from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from burnrate import crypto
from burnrate.config import get_settings
from burnrate.crypto import decrypt_secret, encrypt_secret, generate_key
from burnrate.db.base import Base
from burnrate.db.models import EnableBankingConnection

KEY = generate_key()


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setenv("BANK_TOKEN_ENCRYPTION_KEY", KEY)
    get_settings.cache_clear()
    crypto._cipher_for.cache_clear()
    yield
    get_settings.cache_clear()
    crypto._cipher_for.cache_clear()


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_encrypt_round_trips_and_hides_the_value() -> None:
    token = encrypt_secret("bank-session-123")

    assert token != "bank-session-123"
    assert "bank-session-123" not in token
    assert decrypt_secret(token) == "bank-session-123"


def test_ciphertext_is_randomized() -> None:
    # Same input, different ciphertext: the column can never be searched or
    # correlated, which is why the index was dropped.
    first = encrypt_secret("same-value")
    second = encrypt_secret("same-value")

    assert first != second
    assert decrypt_secret(first) == decrypt_secret(second) == "same-value"


def test_plaintext_written_before_the_migration_is_still_readable() -> None:
    assert decrypt_secret("legacy-plaintext-session") == "legacy-plaintext-session"


def test_decrypting_with_a_changed_key_fails_loudly(monkeypatch) -> None:
    token = encrypt_secret("bank-session-123")

    monkeypatch.setenv("BANK_TOKEN_ENCRYPTION_KEY", generate_key())
    get_settings.cache_clear()
    crypto._cipher_for.cache_clear()

    with pytest.raises(RuntimeError, match="BANK_TOKEN_ENCRYPTION_KEY"):
        decrypt_secret(token)


def test_session_id_is_ciphertext_in_the_database_but_plaintext_in_the_app() -> None:
    db = make_session()
    db.add(
        EnableBankingConnection(
            aspsp_name="ING",
            aspsp_country="ES",
            psu_type="personal",
            session_id="super-secret-session",
        )
    )
    db.commit()

    # What actually lands on disk (and therefore in any dump or backup).
    stored = db.execute(text("SELECT session_id FROM enable_banking_connections")).scalar_one()
    assert stored != "super-secret-session"
    assert "super-secret-session" not in stored
    assert stored.startswith("gAAAAA")

    # What the application sees.
    db.expire_all()
    connection = db.query(EnableBankingConnection).one()
    assert connection.session_id == "super-secret-session"
