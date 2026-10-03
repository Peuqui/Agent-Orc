import os
from pathlib import Path
from typing import Any

import pytest

from ai_orc.context import session_status, status_file, status_line, store_status
from ai_orc.sessions import AgentSession

SESSION_START = 1_000_000.0


def claude_status(used_percentage: int | None, usage: dict[str, int] | None) -> dict[str, Any]:
    """Shape of Claude Code's status line input (recorded from version 2.1.288)."""
    return {
        "model": {"id": "claude-opus-5-5[1m]", "display_name": "Opus 5.5 (1M context)"},
        "effort": {"level": "medium"},
        "workspace": {"current_dir": "/w", "project_dir": "/w"},
        "context_window": {
            "context_window_size": 1_000_000,
            "current_usage": usage,
            "used_percentage": used_percentage,
        },
    }


@pytest.fixture(autouse=True)
def state_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return tmp_path


def session(session_id: str = "demo-abc123") -> AgentSession:
    return AgentSession(session_id, "claude", Path("/w"), True, None, SESSION_START)


def touch(path: Path, mtime: float) -> None:
    os.utime(path, (mtime, mtime))


def test_stored_status_is_reported() -> None:
    usage = {
        "input_tokens": 2,
        "cache_creation_input_tokens": 577,
        "cache_read_input_tokens": 48042,
    }
    touch(store_status("demo-abc123", claude_status(5, usage)), SESSION_START + 10)
    assert session_status(session()) == {
        "model": "Opus 5.5 (1M context)",
        "effort": "medium",
        "context_tokens": 48621,
        "context_window": 1_000_000,
    }


def test_no_usage_before_first_answer_is_unknown_not_zero() -> None:
    touch(store_status("demo-abc123", claude_status(None, None)), SESSION_START + 10)
    assert session_status(session())["context_tokens"] is None


def test_status_from_before_the_session_is_ignored() -> None:
    touch(store_status("demo-abc123", claude_status(5, {"input_tokens": 1})), SESSION_START - 60)
    assert session_status(session()) == {}


def test_no_status_yet() -> None:
    assert session_status(session()) == {}


def test_each_session_has_its_own_file() -> None:
    assert status_file("a-1") != status_file("b-2")
    store_status("other-999", claude_status(5, {"input_tokens": 1}))
    assert session_status(session()) == {}


def test_status_line_text() -> None:
    assert status_line(claude_status(5, {"input_tokens": 1})) == "Opus 5.5 (1M context) · ctx 5%"
    assert status_line(claude_status(None, None)) == "Opus 5.5 (1M context)"
