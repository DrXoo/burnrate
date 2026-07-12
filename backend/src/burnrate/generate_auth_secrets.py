"""Generate credentials for BurnRate's app-level login.

Run inside the backend environment:

    python -m burnrate.generate_auth_secrets

It prompts for a password (never echoed) and prints the two environment
variables to paste into your ``.env``: an Argon2 hash of the password and a
random signing key for session cookies.
"""

from __future__ import annotations

import getpass
import secrets
import sys

from burnrate.security import hash_password

_MIN_PASSWORD_LENGTH = 10


def main() -> int:
    password = getpass.getpass("Choose a BurnRate password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    if len(password) < _MIN_PASSWORD_LENGTH:
        print(f"Use at least {_MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1

    password_hash = hash_password(password)
    secret_key = secrets.token_urlsafe(48)

    print()
    print("# Paste these into your .env (keep them secret):")
    print(f"AUTH_PASSWORD_HASH={password_hash}")
    print(f"AUTH_SECRET_KEY={secret_key}")
    print()
    print("# IMPORTANT: docker compose interpolates '$' in .env files, which")
    print("# corrupts the Argon2 hash. When this .env is loaded by docker compose,")
    print("# double every '$' in the hash. Compose-ready line:")
    print(f"AUTH_PASSWORD_HASH={password_hash.replace('$', '$$')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
