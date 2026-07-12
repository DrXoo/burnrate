from __future__ import annotations

import os

from burnrate.config import get_settings
from burnrate.crypto import generate_key

# enable_banking_connections.session_id is encrypted at rest, so a key must exist
# before any Settings instance is resolved -- otherwise every test that builds a
# connection fails closed. Tests that assert on a specific key override this.
os.environ.setdefault("BANK_TOKEN_ENCRYPTION_KEY", generate_key())
get_settings.cache_clear()
