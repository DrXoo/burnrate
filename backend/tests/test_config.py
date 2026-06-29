from pathlib import Path

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
