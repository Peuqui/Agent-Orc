"""Live status of agent sessions (model, used context window, busy or idle), reported by the
agent itself.

Claude Code passes a JSON document to its status line command on every update. Sessions
started by Agent-Orc use `agent-orc statusline` as that command (see the claude profile in
default_config.yaml), which stores the document here, one file per session. The command
learns its session from the environment variable Agent-Orc sets for every agent.
The window size thus always matches the model actually running, also after /model.

The same document carries the account's usage limits (five hours, week); they hold for every
session alike, so the most recently reported ones are the current ones.

Whether the agent is working comes from Claude's hooks: UserPromptSubmit runs
`agent-orc agent-busy`, Stop runs `agent-orc agent-idle`.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_orc.sessions import AgentSession
from agent_orc.state import state_dir, write_atomically

STATUS_SUFFIX = ".json"
ACTIVITY_SUFFIX = ".activity"
BUSY = "busy"
IDLE = "idle"
# The input side of the last request: what the model had to read, i.e. the occupied context.
CONTEXT_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def status_dir() -> Path:
    return state_dir() / "status"


def status_file(session_id: str) -> Path:
    return status_dir() / f"{session_id}{STATUS_SUFFIX}"


def activity_file(session_id: str) -> Path:
    return status_dir() / f"{session_id}{ACTIVITY_SUFFIX}"


def store_activity(session_id: str, busy: bool) -> Path:
    return write_atomically(activity_file(session_id), BUSY if busy else IDLE)


def session_busy(session: AgentSession) -> bool:
    """True while the agent works on a request (also while it waits for a permission)."""
    path = activity_file(session.id)
    if not path.is_file() or path.stat().st_mtime < session.created:
        return False
    return path.read_text(encoding="utf-8") == BUSY


def store_status(session_id: str, status: dict[str, Any]) -> Path:
    """Store the latest status document of a session."""
    return write_atomically(status_file(session_id), json.dumps(status))


def status_line(status: dict[str, Any]) -> str:
    """The text Claude Code shows in its own status line."""
    model = status["model"]["display_name"]
    window = status.get("context_window") or {}
    used = window.get("used_percentage")
    return model if used is None else f"{model} · ctx {used}%"


def session_status(session: AgentSession) -> dict[str, Any]:
    """Model and context window of a session; empty if it has not reported since it started."""
    path = status_file(session.id)
    if not path.is_file() or path.stat().st_mtime < session.created:
        return {}
    status = json.loads(path.read_text(encoding="utf-8"))
    window = status.get("context_window") or {}
    # Before the first answer there is no usage yet: unknown, not zero.
    usage = window.get("current_usage")
    return {
        "model": status["model"]["display_name"],
        "effort": (status.get("effort") or {}).get("level"),
        "context_tokens": sum(usage.get(field, 0) for field in CONTEXT_FIELDS) if usage else None,
        "context_window": window.get("context_window_size"),
    }


def session_transcript(session: AgentSession) -> Path | None:
    """Where the agent writes its conversation (Claude's status line reports it); None until it
    has reported since it started."""
    path = status_file(session.id)
    if not path.is_file() or path.stat().st_mtime < session.created:
        return None
    transcript = json.loads(path.read_text(encoding="utf-8")).get("transcript_path")
    return Path(transcript) if transcript else None


def claude_rate_limits() -> dict[str, Any] | None:
    """Usage windows from the newest Claude status, e.g. {"five_hour": {"used_percentage": 5,
    "resets_at": 1791111000}, "seven_day": ...}; None until a session has reported them."""
    reports = sorted(status_dir().glob(f"*{STATUS_SUFFIX}"), key=lambda path: path.stat().st_mtime)
    for path in reversed(reports):
        limits = json.loads(path.read_text(encoding="utf-8")).get("rate_limits")
        if limits:
            return dict(limits)
    return None


# Per agent profile setting "quota": where the usage limits of that agent come from.
QUOTA_SOURCES: dict[str, Callable[[], dict[str, Any] | None]] = {
    "claude": claude_rate_limits,
}
