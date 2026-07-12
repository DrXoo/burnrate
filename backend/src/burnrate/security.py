from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError, VerificationError

_password_hasher = PasswordHasher()

_JWT_ALGORITHM = "HS256"
_SESSION_SUBJECT = "owner"


def hash_password(password: str) -> str:
    """Return an Argon2 hash of ``password`` suitable for AUTH_PASSWORD_HASH."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify ``password`` against a stored Argon2 hash without leaking timing.

    Returns False for any mismatch or malformed hash rather than raising, so
    callers can treat every failure identically.
    """
    if not password_hash:
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError, Argon2Error):
        return False


def create_session_token(*, secret_key: str, max_age_seconds: int) -> str:
    """Issue a signed session token that expires after ``max_age_seconds``."""
    now = int(time.time())
    payload = {
        "sub": _SESSION_SUBJECT,
        "iat": now,
        "exp": now + max_age_seconds,
    }
    return jwt.encode(payload, secret_key, algorithm=_JWT_ALGORITHM)


def verify_session_token(*, secret_key: str, token: str) -> str | None:
    """Return the token subject if the signature and expiry are valid, else None."""
    if not secret_key or not token:
        return None
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None


@dataclass
class _AttemptState:
    count: int
    window_start: float
    locked_until: float


class LoginRateLimiter:
    """In-memory failed-login throttle keyed by client identity.

    A single-process, single-user guard: after ``max_attempts`` failures inside
    one lockout window the key is blocked for ``lockout_seconds``. A successful
    login clears the counter. Good enough for one owner behind one uvicorn
    worker; swap for a shared store if the deployment ever scales out.
    """

    def __init__(self, *, max_attempts: int, lockout_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._lockout_seconds = lockout_seconds
        self._by_key: dict[str, _AttemptState] = {}
        self._lock = threading.Lock()

    def seconds_until_unlocked(self, key: str) -> float:
        """Return remaining lockout seconds for ``key`` (0 if not locked)."""
        now = time.time()
        with self._lock:
            state = self._by_key.get(key)
            if state is None:
                return 0.0
            return max(0.0, state.locked_until - now)

    def record_failure(self, key: str) -> None:
        now = time.time()
        with self._lock:
            state = self._by_key.get(key)
            if state is None or now - state.window_start > self._lockout_seconds:
                state = _AttemptState(count=0, window_start=now, locked_until=0.0)
            state.count += 1
            if state.count >= self._max_attempts:
                state.locked_until = now + self._lockout_seconds
            self._by_key[key] = state

    def reset(self, key: str) -> None:
        with self._lock:
            self._by_key.pop(key, None)


@dataclass
class _WindowState:
    count: int
    window_start: float


class RateLimiter:
    """In-memory fixed-window rate limiter keyed by an arbitrary string.

    Allows up to ``max_requests`` within each ``window_seconds`` window per key.
    Single-process only (one uvicorn worker); it caps runaway loops and protects
    the upstream bank API from being hammered, not a distributed adversary.
    """

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._by_key: dict[str, _WindowState] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> float:
        """Register a request. Return 0 if allowed, else seconds until the window resets."""
        now = time.time()
        with self._lock:
            state = self._by_key.get(key)
            if state is None or now - state.window_start >= self._window_seconds:
                self._by_key[key] = _WindowState(count=1, window_start=now)
                return 0.0
            if state.count >= self._max_requests:
                return state.window_start + self._window_seconds - now
            state.count += 1
            return 0.0
