from pathlib import Path

import pytest
from pydantic import ValidationError

from burnrate.config import Settings


def test_enable_banking_private_key_path_takes_precedence(tmp_path: Path) -> None:
    pem_path = tmp_path / "enable-banking.pem"
    pem_path.write_text("file-based-key", encoding="utf-8")

    settings = Settings(
        ENABLE_BANKING_PRIVATE_KEY="inline-key",
        ENABLE_BANKING_PRIVATE_KEY_PATH=str(pem_path),
        DATABASE_URL="sqlite:///ignored.db",
    )

    assert settings.enable_banking_private_key_value == "file-based-key"


def test_rejects_an_unknown_app_timezone() -> None:
    with pytest.raises(ValidationError):
        Settings(APP_TIMEZONE="Europe/Madridd", DATABASE_URL="sqlite:///ignored.db")


def test_accepts_and_normalizes_a_valid_app_timezone() -> None:
    settings = Settings(APP_TIMEZONE="  Europe/Madrid  ", DATABASE_URL="sqlite:///ignored.db")

    assert settings.app_timezone == "Europe/Madrid"
