"""Live status of agent sessions (model, used context window, busy or idle), reported by the
agent itself.

Claude Code passes a JSON document to its status line command on every update. Sessions
started by AI-Orc use `ai-orc statusline` as that command (see the claude profile in
default_config.yaml), which stores the document here, one file per session. The command
learns its session from the environment variable AI-Orc sets for every agent.
The window size thus always matches the model actually running, also after /model.

Whether the agent is working comes from Claude's hooks: UserPromptSubmit runs
`ai-orc agent-busy`, Stop runs `ai-orc agent-idle`.
"""

import json
import os
from pathlib import Path
from typing import Any

from ai_orc.sessions import AgentSession

STATUS_SUFFIX = ".json"
ACTIVITY_SUFFIX = ".activity"
BUSY = "busy"
IDLE = "idle"
# The input side of the last request: what the model had to read, i.e. the occupied context.
CONTEXT_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def status_dir() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state_home) / "ai-orc" / "status"


def status_file(session_id: str) -> Path:
    return status_dir() / f"{session_id}{STATUS_SUFFIX}"


def _write_atomically(target: Path, text: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temporary file and rename, so readers never see a half-written file.
    temporary = target.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(target)
    return target


def activity_file(session_id: str) -> Path:
    return status_dir() / f"{session_id}{ACTIVITY_SUFFIX}"


def store_activity(session_id: str, busy: bool) -> Path:
    return _write_atomically(activity_file(session_id), BUSY if busy else IDLE)


def session_busy(session: AgentSession) -> bool:
    """True while the agent works on a request (also while it waits for a permission)."""
    path = activity_file(session.id)
    if not path.is_file() or path.stat().st_mtime < session.created:
        return False
    return path.read_text(encoding="utf-8") == BUSY


def store_status(session_id: str, status: dict[str, Any]) -> Path:
    """Store the latest status document of a session."""
    return _write_atomically(status_file(session_id), json.dumps(status))


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
