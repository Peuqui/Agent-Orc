"""The mark a local session carries to the card gate (see card_gate in the config).

The gate recognizes the session by it, and other users of the machine cannot get in: the mark is
the session id signed with a secret that lies in the state folder, readable for the user alone.
`agent-orc backend run` forms it from AGENT_ORC_SESSION without asking the server, and the gate
checks it without storing anything.
"""

import contextlib
import hmac
import os
import secrets
import stat
import tempfile
from hashlib import sha256
from pathlib import Path

from agent_orc.state import state_dir

GATE_SECRET_FILE = "gate-secret"
GATE_SECRET_FILE_MODE = 0o600
GATE_SECRET_BYTES = 32
# Session ids hold no dot (tmux forbids it), the mark is cut at its last one all the same.
MARK_SEPARATOR = "."


class GateSecretError(RuntimeError):
    """The gate's secret cannot be used safely."""


def gate_secret() -> bytes:
    """The secret, created on first use; a file open to others is refused, not corrected."""
    path = state_dir() / GATE_SECRET_FILE
    if not path.exists():
        _create_secret(path)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != GATE_SECRET_FILE_MODE:
        raise GateSecretError(
            f"{path} must be readable for you alone (chmod {GATE_SECRET_FILE_MODE:o} {path})"
        )
    return path.read_bytes()


def _create_secret(path: Path) -> None:
    """Written whole into a file of its own (mkstemp: 0600 from the start), then linked into place
    at once: a start that reads it at the same time never sees it half written, and of two starts
    creating it the first link wins and the second one's file is dropped."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(secrets.token_hex(GATE_SECRET_BYTES).encode())
        with contextlib.suppress(FileExistsError):
            os.link(temporary, path)
    finally:
        temporary.unlink()


def _signature(session_id: str) -> str:
    return hmac.new(gate_secret(), session_id.encode(), sha256).hexdigest()


def session_token(session_id: str) -> str:
    return f"{session_id}{MARK_SEPARATOR}{_signature(session_id)}"


def token_session(token: str) -> str | None:
    """The session id of a genuine mark, otherwise None."""
    session_id, separator, signature = token.rpartition(MARK_SEPARATOR)
    if not separator or not hmac.compare_digest(signature, _signature(session_id)):
        return None
    return session_id
