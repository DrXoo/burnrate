from __future__ import annotations

import os
from datetime import UTC, datetime

from burnrate.config import get_settings
from burnrate.crypto import generate_key

# enable_banking_connections.session_id is encrypted at rest, so a key must exist
# before any Settings instance is resolved -- otherwise every test that builds a
# connection fails closed. Tests that assert on a specific key override this.
os.environ.setdefault("BANK_TOKEN_ENCRYPTION_KEY", generate_key())
get_settings.cache_clear()


# The month-end boundary, as one definition the whole suite shares.
#
# Every civil date in the product is right or wrong at exactly one moment: the hours
# of each month-end where UTC and the owner's zone sit in different months. These are
# the two instants that reach it, one zone ahead of UTC and one behind, so a test can
# name the direction instead of restating the arithmetic. They are deliberately the
# same pair everywhere -- a figure that only breaks in one direction is the failure
# mode these exist to catch, and that is only visible if both are the same boundary.
#
# ``AHEAD_OF_UTC``: 01:00 on 1 July in Madrid (UTC+2), while UTC still reads 30 June.
# ``BEHIND_UTC``:   16:00 on 30 June in Honolulu (UTC-10), while UTC has reached 1 July.
#
# Both land on the June/July boundary so a fixture seeded in either month can be
# asserted from either side of it. See ``burnrate.clock``.
AHEAD_OF_UTC = ("Europe/Madrid", datetime(2026, 6, 30, 23, 0, tzinfo=UTC), "2026-07")
BEHIND_UTC = ("Pacific/Honolulu", datetime(2026, 7, 1, 2, 0, tzinfo=UTC), "2026-06")
