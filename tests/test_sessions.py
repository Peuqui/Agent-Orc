"""Tests against a real tmux server on a throwaway socket."""

import subprocess
import time
from pathlib import Path

import pytest

from ai_orc.config import AgentProfile, EffortConfig
from ai_orc.sessions import (
    AgentSession,
    InvalidEffortError,
    SessionAlreadyRunningError,
    SessionManager,
    SessionNotFoundError,
    UnknownProfileError,
    build_command,
    exact_target,
    session_id_for,
)

AGENTS = {
    "sleeper": AgentProfile(
        label="Sleeper",
        start=["sleep", "60"],
        resume=["sleep", "61"],
        effort=EffortConfig(levels=["low", "high"], args=["--effort", "{effort}"]),
    ),
    "failing": AgentProfile(label="Failing", start=["sh", "-c", "exit 3"], resume=["true"]),
    "echo": AgentProfile(
        label="Echo", start=["sh", "-c", "echo started {name}; sleep 60"], resume=["sleep", "60"]
    ),
}


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
    session = manager.start("sleeper", workdir, resume=False, effort=None)
    assert session.running
    assert session.profile == "sleeper"
    assert session.path == workdir
    assert manager.list() == [session]

    manager.stop(session.id)
    assert manager.list() == []


def test_resume_uses_resume_command(
    manager: SessionManager, socket_name: str, workdir: Path
) -> None:
    session = manager.start("sleeper", workdir, resume=True, effort=None)
    command = tmux_query(
        socket_name, "display-message", "-p", "-t", exact_target(session.id),
        "#{pane_start_command}",
    )  # fmt: skip
    assert "61" in command


def test_agent_runs_in_folder_with_name_placeholder(
    manager: SessionManager, socket_name: str, workdir: Path
) -> None:
    session = manager.start("echo", workdir, resume=False, effort=None)
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
    manager.start("failing", workdir, resume=False, effort=None)
    session = wait_until_exited(manager, workdir)
    assert session.exit_status == 3


def test_exited_session_is_replaced_on_start(manager: SessionManager, workdir: Path) -> None:
    manager.start("failing", workdir, resume=False, effort=None)
    wait_until_exited(manager, workdir)
    session = manager.start("sleeper", workdir, resume=False, effort=None)
    assert session.running
    assert len(manager.list()) == 1


def test_only_one_running_agent_per_folder(manager: SessionManager, workdir: Path) -> None:
    manager.start("sleeper", workdir, resume=False, effort=None)
    with pytest.raises(SessionAlreadyRunningError):
        manager.start("echo", workdir, resume=False, effort=None)


def test_unknown_profile(manager: SessionManager, workdir: Path) -> None:
    with pytest.raises(UnknownProfileError):
        manager.start("nope", workdir, resume=False, effort=None)


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


def test_effort_is_appended_to_the_command(
    manager: SessionManager, socket_name: str, workdir: Path
) -> None:
    # sleep ignores the extra arguments; only the recorded command matters here.
    session = manager.start("sleeper", workdir, resume=False, effort="high")
    command = tmux_query(
        socket_name, "display-message", "-p", "-t", exact_target(session.id),
        "#{pane_start_command}",
    )  # fmt: skip
    assert command.endswith("--effort high")


def test_unknown_effort_is_refused(manager: SessionManager, workdir: Path) -> None:
    with pytest.raises(InvalidEffortError):
        manager.start("sleeper", workdir, resume=False, effort="ultra")
    with pytest.raises(InvalidEffortError):
        manager.start("echo", workdir, resume=False, effort="low")
    assert manager.list() == []
