import os
from pathlib import Path
from typing import Any

import pytest

from agent_orc.context import (
    begin_compaction,
    claude_rate_limits,
    end_compaction,
    session_busy,
    session_status,
    status_file,
    status_line,
    store_activity,
    store_status,
)
from agent_orc.sessions import AgentSession

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
    return AgentSession(session_id, "claude", Path("/w"), True, None, SESSION_START, False, None)


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


def test_rate_limits_come_from_the_newest_report() -> None:
    assert claude_rate_limits() is None
    older = {"five_hour": {"used_percentage": 5, "resets_at": 100}}
    newer = {"five_hour": {"used_percentage": 7, "resets_at": 100}}
    touch(store_status("a-1", {**claude_status(1, None), "rate_limits": older}), SESSION_START)
    touch(store_status("b-2", {**claude_status(1, None), "rate_limits": newer}), SESSION_START + 1)
    # Reported later, but without limits (older Claude versions omit them): ignored.
    touch(store_status("c-3", claude_status(1, None)), SESSION_START + 2)
    assert claude_rate_limits() == newer


def test_compaction_marks_a_resting_agent_as_working_until_it_is_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    session = AgentSession("c-1", "claude", tmp_path, True, None, 0.0, False, None)
    store_activity("c-1", busy=False)
    assert not session_busy(session)
    begin_compaction("c-1")
    assert session_busy(session)
    end_compaction("c-1")
    assert not session_busy(session)


def test_compaction_in_the_middle_of_an_answer_leaves_the_agent_working(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    session = AgentSession("c-2", "claude", tmp_path, True, None, 0.0, False, None)
    store_activity("c-2", busy=True)
    begin_compaction("c-2")
    end_compaction("c-2")
    # An automatic compaction does not end the answer; only Stop does.
    assert session_busy(session)


def test_compaction_of_an_agent_that_never_reported_counts_as_resting_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    session = AgentSession("c-3", "claude", tmp_path, True, None, 0.0, False, None)
    begin_compaction("c-3")
    assert session_busy(session)
    end_compaction("c-3")
    assert not session_busy(session)
