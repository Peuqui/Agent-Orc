"""Tests against a real tmux server on a throwaway socket."""

import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from ai_orc.config import AgentProfile
from ai_orc.sessions import (
    AgentSession,
    SessionAlreadyRunningError,
    SessionManager,
    SessionNotFoundError,
    UnknownProfileError,
    build_command,
    exact_target,
    session_id_for,
)

AGENTS = {
    "sleeper": AgentProfile(label="Sleeper", start=["sleep", "60"], resume=["sleep", "61"]),
    "failing": AgentProfile(label="Failing", start=["sh", "-c", "exit 3"], resume=["true"]),
    "echo": AgentProfile(
        label="Echo", start=["sh", "-c", "echo started {name}; sleep 60"], resume=["sleep", "60"]
    ),
}


@pytest.fixture
def socket_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    # Socket files live in pytest's tmp dir, so nothing is left behind in /tmp/tmux-<uid>.
    monkeypatch.setenv("TMUX_TMPDIR", str(tmp_path))
    name = f"ai-orc-test-{uuid.uuid4().hex[:8]}"
    yield name
    subprocess.run(["tmux", "-L", name, "kill-server"], capture_output=True)


@pytest.fixture
def manager(socket_name: str) -> SessionManager:
    return SessionManager(socket_name, AGENTS)


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    folder = tmp_path / "my.project"
    folder.mkdir()
    return folder


def tmux_query(socket_name: str, *arguments: str) -> str:
    return subprocess.run(
        ["tmux", "-L", socket_name, *arguments], capture_output=True, text=True, check=True
    ).stdout.strip()


def wait_until_exited(manager: SessionManager, path: Path) -> AgentSession:
    for _ in range(50):
        session = manager.find_by_path(path)
        assert session is not None
        if not session.running:
            return session
        time.sleep(0.1)
    raise AssertionError("agent did not exit")


def test_list_without_server_is_empty(manager: SessionManager) -> None:
    assert manager.list() == []


def test_start_list_stop(manager: SessionManager, workdir: Path) -> None:
    session = manager.start("sleeper", workdir, resume=False)
    assert session.running
    assert session.profile == "sleeper"
    assert session.path == workdir
    assert manager.list() == [session]

    manager.stop(session.id)
    assert manager.list() == []


def test_resume_uses_resume_command(
    manager: SessionManager, socket_name: str, workdir: Path
) -> None:
    session = manager.start("sleeper", workdir, resume=True)
    command = tmux_query(
        socket_name, "display-message", "-p", "-t", exact_target(session.id),
        "#{pane_start_command}",
    )  # fmt: skip
    assert "61" in command


def test_agent_runs_in_folder_with_name_placeholder(
    manager: SessionManager, socket_name: str, workdir: Path
) -> None:
    session = manager.start("echo", workdir, resume=False)
    target = exact_target(session.id)
    for _ in range(50):
        pane = tmux_query(socket_name, "capture-pane", "-p", "-t", target)
        if "started my.project" in pane:
            break
        time.sleep(0.1)
    assert "started my.project" in pane
    cwd = tmux_query(socket_name, "display-message", "-p", "-t", target, "#{pane_current_path}")
    assert Path(cwd) == workdir


def test_exited_agent_stays_visible_with_status(manager: SessionManager, workdir: Path) -> None:
    manager.start("failing", workdir, resume=False)
    session = wait_until_exited(manager, workdir)
    assert session.exit_status == 3


def test_exited_session_is_replaced_on_start(manager: SessionManager, workdir: Path) -> None:
    manager.start("failing", workdir, resume=False)
    wait_until_exited(manager, workdir)
    session = manager.start("sleeper", workdir, resume=False)
    assert session.running
    assert len(manager.list()) == 1


def test_only_one_running_agent_per_folder(manager: SessionManager, workdir: Path) -> None:
    manager.start("sleeper", workdir, resume=False)
    with pytest.raises(SessionAlreadyRunningError):
        manager.start("echo", workdir, resume=False)


def test_unknown_profile(manager: SessionManager, workdir: Path) -> None:
    with pytest.raises(UnknownProfileError):
        manager.start("nope", workdir, resume=False)


def test_stop_unknown_session(manager: SessionManager) -> None:
    with pytest.raises(SessionNotFoundError):
        manager.stop("does-not-exist")


def test_session_id_is_tmux_safe_and_unique() -> None:
    first = session_id_for(Path("/a/my.project"))
    second = session_id_for(Path("/b/my.project"))
    assert first != second
    assert "." not in first and ":" not in first


def test_build_command_replaces_placeholder() -> None:
    assert build_command(["x", "--name", "{name}"], "demo") == ["x", "--name", "demo"]
