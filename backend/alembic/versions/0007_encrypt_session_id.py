"""Encrypt enable_banking_connections.session_id at rest

The bank session token was stored in plaintext, so anyone with a copy of the
database -- a dump, a backup, or the (previously LAN-exposed) Postgres port --
held usable bank access. Existing values are rewritten as Fernet ciphertext
using BANK_TOKEN_ENCRYPTION_KEY.

The index on the column is dropped: the ciphertext is randomized, so the column
is no longer searchable, and nothing ever looked a connection up by session_id.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from burnrate.crypto import decrypt_secret, encrypt_secret

# revision identifiers, used by Alembic.
revision = "0007_encrypt_session_id"
down_revision = "0006_transaction_excluded"
branch_labels = None
depends_on = None

_FERNET_PREFIX = "gAAAAA"

_SELECT = sa.text(
    "SELECT id, session_id FROM enable_banking_connections WHERE session_id IS NOT NULL"
)
_UPDATE = sa.text("UPDATE enable_banking_connections SET session_id = :value WHERE id = :id")


def upgrade() -> None:
    bind = op.get_bind()
    for row in bind.execute(_SELECT).fetchall():
        if row.session_id.startswith(_FERNET_PREFIX):
            continue  # already encrypted; keep the migration re-runnable
        bind.execute(_UPDATE, {"value": encrypt_secret(row.session_id), "id": row.id})

    op.drop_index(
        "ix_enable_banking_connections_session_id",
        table_name="enable_banking_connections",
    )


def downgrade() -> None:
    bind = op.get_bind()
    for row in bind.execute(_SELECT).fetchall():
        if not row.session_id.startswith(_FERNET_PREFIX):
            continue
        bind.execute(_UPDATE, {"value": decrypt_secret(row.session_id), "id": row.id})

    op.create_index(
        "ix_enable_banking_connections_session_id",
        "enable_banking_connections",
        ["session_id"],
    )
