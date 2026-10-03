"""Password hashing, credentials file, signed login tokens and login lockout."""

import hashlib
import hmac
import json
import os
import secrets
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
SECRET_KEY_BYTES = 32
HASH_SCHEME = "scrypt"
CREDENTIALS_FILE_MODE = 0o600

Clock = Callable[[], float]


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    password_hash: str
    # Signs login tokens; a new key on every password change logs out all devices.
    secret_key: str


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p)


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"{HASH_SCHEME}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    scheme, n, r, p, salt, digest = encoded.split("$")
    if scheme != HASH_SCHEME:
        raise ValueError(f"unknown password hash scheme: {scheme}")
    candidate = _scrypt(password, bytes.fromhex(salt), int(n), int(r), int(p))
    return hmac.compare_digest(candidate, bytes.fromhex(digest))


def new_credentials(password: str) -> Credentials:
    return Credentials(
        password_hash=hash_password(password), secret_key=secrets.token_hex(SECRET_KEY_BYTES)
    )


def save_credentials(path: Path, credentials: Credentials) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, CREDENTIALS_FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(credentials.model_dump_json(indent=2))
    # os.open only applies the mode when it creates the file.
    path.chmod(CREDENTIALS_FILE_MODE)


def load_credentials(path: Path) -> Credentials:
    return Credentials.model_validate(json.loads(path.read_text(encoding="utf-8")))


class TokenSigner:
    """Stateless login tokens "<expiry>.<hmac>", so logins survive server restarts."""

    def __init__(self, secret_key: str, lifetime_seconds: float, clock: Clock) -> None:
        self._key = bytes.fromhex(secret_key)
        self._lifetime = lifetime_seconds
        self._clock = clock

    def issue(self) -> str:
        expiry = str(int(self._clock() + self._lifetime))
        return f"{expiry}.{self._sign(expiry)}"

    def is_valid(self, token: str) -> bool:
        expiry, _, signature = token.partition(".")
        if not expiry.isdigit() or not hmac.compare_digest(signature, self._sign(expiry)):
            return False
        return int(expiry) > self._clock()

    def _sign(self, payload: str) -> str:
        return hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()


class LoginGuard:
    """Refuses all logins for a while after too many failures in a row.

    Deliberately global, not per client IP: behind a reverse proxy every client has the
    proxy's address, and a single-user tool prefers lockout over brute-force exposure.
    """

    def __init__(self, max_failures: int, lockout_seconds: float, clock: Clock) -> None:
        self._max_failures = max_failures
        self._lockout_seconds = lockout_seconds
        self._clock = clock
        self._failures = 0
        self._locked_until = 0.0

    def seconds_locked(self) -> float:
        return max(0.0, self._locked_until - self._clock())

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._max_failures:
            self._locked_until = self._clock() + self._lockout_seconds
            self._failures = 0

    def record_success(self) -> None:
        self._failures = 0
