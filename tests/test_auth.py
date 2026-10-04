import stat
from pathlib import Path

from agent_orc.auth import (
    LoginGuard,
    TokenSigner,
    hash_password,
    load_credentials,
    new_credentials,
    save_credentials,
    verify_password,
)
from tests.conftest import FakeClock

SECRET = "ab" * 32


def test_password_roundtrip() -> None:
    encoded = hash_password("geheim")
    assert verify_password("geheim", encoded)
    assert not verify_password("falsch", encoded)


def test_hashes_are_salted() -> None:
    assert hash_password("geheim") != hash_password("geheim")


def test_credentials_file_is_private(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "credentials.json"
    credentials = new_credentials("geheim")
    save_credentials(path, credentials)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_credentials(path) == credentials


def test_existing_credentials_file_becomes_private(tmp_path: Path) -> None:
    path = tmp_path / "credentials.json"
    path.write_text("{}")
    path.chmod(0o644)
    save_credentials(path, new_credentials("geheim"))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_token_valid_until_expiry(clock: FakeClock) -> None:
    signer = TokenSigner(SECRET, lifetime_seconds=100, clock=clock)
    token = signer.issue()
    assert signer.is_valid(token)
    clock.advance(101)
    assert not signer.is_valid(token)


def test_token_tampering_is_detected(clock: FakeClock) -> None:
    signer = TokenSigner(SECRET, lifetime_seconds=100, clock=clock)
    expiry, signature = signer.issue().split(".")
    assert not signer.is_valid(f"{int(expiry) + 10_000}.{signature}")
    assert not signer.is_valid("garbage")
    assert not signer.is_valid("")


def test_token_from_other_key_is_rejected(clock: FakeClock) -> None:
    token = TokenSigner("cd" * 32, lifetime_seconds=100, clock=clock).issue()
    assert not TokenSigner(SECRET, lifetime_seconds=100, clock=clock).is_valid(token)


def test_guard_locks_after_failures_and_releases(clock: FakeClock) -> None:
    guard = LoginGuard(max_failures=3, lockout_seconds=60, clock=clock)
    guard.record_failure()
    guard.record_failure()
    assert guard.seconds_locked() == 0
    guard.record_failure()
    assert guard.seconds_locked() == 60
    clock.advance(61)
    assert guard.seconds_locked() == 0


def test_guard_success_resets_failures(clock: FakeClock) -> None:
    guard = LoginGuard(max_failures=2, lockout_seconds=60, clock=clock)
    guard.record_failure()
    guard.record_success()
    guard.record_failure()
    assert guard.seconds_locked() == 0
