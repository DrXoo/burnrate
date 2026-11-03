"""Backup and restore, exercised against the running stack.

The only test in this project that needs a service. Everything else runs on in-memory
SQLite, and that is the right default -- but what this protects is a *belief about
recovery*, and a faked ``pg_dump`` cannot hold one. A test double that agrees with the
scripts would pass while the dumps were truncated, which is the failure mode the whole
phase exists to refuse.

So it runs the real scripts against a scratch database created inside the Postgres
container that is already there, and it skips when the stack is not up, so the suite
stays green on a machine with no Docker.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup.sh"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "restore.sh"
SCRATCH_DATABASE = "burnrate_restore_check"

pytestmark = pytest.mark.integration


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _stack_is_up() -> bool:
    try:
        running = _compose("ps", "-q", "postgres", check=False)
    except FileNotFoundError:
        return False
    if running.returncode != 0 or not running.stdout.strip():
        return False
    ready = _compose("exec", "-T", "postgres", "pg_isready", check=False)
    return ready.returncode == 0


def _live_database() -> str:
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        if line.startswith("POSTGRES_DB="):
            return line.split("=", 1)[1].strip()
    raise AssertionError("POSTGRES_DB is not set in .env")


def _psql(database: str, sql: str) -> str:
    user = os.environ.get("POSTGRES_USER") or _env_value("POSTGRES_USER")
    result = _compose(
        "exec", "-T", "postgres", "psql", "-U", user, "-d", database, "-t", "-A", "-c", sql
    )
    return result.stdout.strip()


def _env_value(key: str) -> str:
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    raise AssertionError(f"{key} is not set in .env")


def _drop_scratch_database() -> None:
    _psql("postgres", f'DROP DATABASE IF EXISTS "{SCRATCH_DATABASE}" WITH (FORCE)')


def _parse_manifest(manifest: Path) -> tuple[dict[str, str], dict[str, int]]:
    header: dict[str, str] = {}
    rows: dict[str, int] = {}
    in_rows = False
    for line in manifest.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line == "[rows]":
            in_rows = True
            continue
        key, _, value = line.partition("=")
        if in_rows:
            rows[key] = int(value)
        else:
            header[key] = value
    return header, rows


@pytest.fixture(autouse=True)
def _requires_stack() -> None:
    if not _stack_is_up():
        pytest.skip("the Docker stack is not running, so backup and restore cannot be exercised")


@pytest.fixture
def scratch_database() -> None:
    _drop_scratch_database()
    yield
    _drop_scratch_database()


def test_a_backup_set_holds_the_database_and_both_secrets(tmp_path: Path) -> None:
    """A dump alone does not restore a working product, so a set is three artefacts."""
    subprocess.run(
        [str(BACKUP_SCRIPT)],
        cwd=REPO_ROOT,
        env={**os.environ, "BURNRATE_BACKUP_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        check=True,
    )

    sets = sorted(p for p in tmp_path.iterdir() if p.is_dir())
    assert len(sets) == 1, "one run writes one backup set"
    backup_set = sets[0]

    assert (backup_set / "burnrate.dump").stat().st_size > 0
    assert (backup_set / "env").read_text().startswith("POSTGRES_DB=")
    assert "PRIVATE KEY" in (backup_set / "enable-banking.pem").read_text()

    header, rows = _parse_manifest(backup_set / "manifest.txt")
    assert header["database"] == _live_database()
    assert header["alembic_revision"]
    assert rows["transactions"] > 0


def test_a_restore_reproduces_every_row_the_manifest_counted(
    tmp_path: Path, scratch_database: None
) -> None:
    """The restore is the deliverable. An untested backup is a belief."""
    subprocess.run(
        [str(BACKUP_SCRIPT)],
        cwd=REPO_ROOT,
        env={**os.environ, "BURNRATE_BACKUP_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        check=True,
    )
    backup_set = next(p for p in tmp_path.iterdir() if p.is_dir())
    header, expected_rows = _parse_manifest(backup_set / "manifest.txt")

    subprocess.run(
        [str(RESTORE_SCRIPT), str(backup_set), "--database", SCRATCH_DATABASE],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    restored_revision = _psql(SCRATCH_DATABASE, "select version_num from alembic_version")
    assert restored_revision == header["alembic_revision"]

    for table, count in expected_rows.items():
        restored = int(_psql(SCRATCH_DATABASE, f'select count(*) from "{table}"'))
        assert restored == count, f"{table} lost rows in the round trip"


def test_the_restore_script_refuses_the_live_database_without_being_told(
    tmp_path: Path,
) -> None:
    """The recovery tool must not itself be a way to lose the data."""
    subprocess.run(
        [str(BACKUP_SCRIPT)],
        cwd=REPO_ROOT,
        env={**os.environ, "BURNRATE_BACKUP_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        check=True,
    )
    backup_set = next(p for p in tmp_path.iterdir() if p.is_dir())

    refused = subprocess.run(
        [str(RESTORE_SCRIPT), str(backup_set), "--database", _live_database()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert refused.returncode != 0
    assert "--allow-live" in (refused.stderr + refused.stdout)


def test_retention_prunes_the_oldest_sets_and_keeps_the_newest(tmp_path: Path) -> None:
    """A host that fills up stops backing up silently."""
    for _ in range(3):
        subprocess.run(
            [str(BACKUP_SCRIPT)],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "BURNRATE_BACKUP_DIR": str(tmp_path),
                "BURNRATE_BACKUP_RETENTION": "2",
            },
            capture_output=True,
            text=True,
            check=True,
        )

    sets = sorted(p.name for p in tmp_path.iterdir() if p.is_dir())
    assert len(sets) == 2, "retention of 2 keeps two sets"
