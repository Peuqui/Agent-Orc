"""Tests against a real tmux server on a throwaway socket."""

import subprocess
import time
from pathlib import Path

import pytest

from agent_orc.config import AgentProfile, TerminalConfig
from agent_orc.sessions import (
    AgentSession,
    MissingModelError,
    SessionAlreadyRunningError,
    SessionManager,
    SessionNotFoundError,
    UnknownProfileError,
    build_command,
    exact_target,
    session_id_for,
    text_pieces,
)

AGENTS = {
    "sleeper": AgentProfile(label="Sleeper", start=["sleep", "60"], resume=["sleep", "61"]),
    "failing": AgentProfile(label="Failing", start=["sh", "-c", "exit 3"], resume=["true"]),
    "killed": AgentProfile(label="Killed", start=["sh", "-c", "kill -KILL $$"], resume=["true"]),
    "echo": AgentProfile(
        label="Echo", start=["sh", "-c", "echo started {name}; sleep 60"], resume=["sleep", "60"]
    ),
    "reader": AgentProfile(label="Reader", start=["cat"], resume=["cat"]),
    "chooser": AgentProfile(
        label="Chooser",
        start=["sh", "-c", 'echo "started {model} $ORC_EFFORT"; sleep 60'],
        resume=["sh", "-c", 'echo "resumed {model} $ORC_EFFORT"; sleep 60'],
    ),
    "terminal": AgentProfile(
        label="Terminal", start=["sleep", "60"], resume=["sleep", "60"], terminal=True
    ),
}


@pytest.fixture
def manager(socket_name: str) -> SessionManager:
    terminal = TerminalConfig(
        keys=[],
        submit_delay_ms=50,
        text_history_lines=200,
        type_chunk_chars=50,
        type_chunk_delay_ms=5,
    )
    return SessionManager(socket_name, AGENTS, terminal)


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
        session = manager.find_by_path(path, terminal=False)
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


def test_agent_killed_by_signal_has_no_exit_status(manager: SessionManager, workdir: Path) -> None:
    manager.start("killed", workdir, resume=False)
    assert wait_until_exited(manager, workdir).exit_status is None


def test_exited_session_is_started_again_in_place(manager: SessionManager, workdir: Path) -> None:
    exited = manager.start("failing", workdir, resume=False)
    wait_until_exited(manager, workdir)
    session = manager.start("sleeper", workdir, resume=False)
    assert session.running
    # Same id: open terminals and workspace columns stay valid.
    assert (session.id, session.profile) == (exited.id, "sleeper")
    assert len(manager.list()) == 1


def test_restart_resumes_a_running_agent_in_its_session(
    manager: SessionManager, workdir: Path, socket_name: str
) -> None:
    session = manager.start("sleeper", workdir, resume=False)
    restarted = manager.restart(session, {})
    assert (restarted.id, restarted.running) == (session.id, True)
    target = f"={session.id}:"
    command = tmux_query(
        socket_name, "display-message", "-p", "-t", target, "#{pane_start_command}"
    )
    assert command == "sleep 61"


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
    first = session_id_for(Path("/a/my.project"), terminal=False)
    second = session_id_for(Path("/b/my.project"), terminal=False)
    assert first != second
    assert "." not in first and ":" not in first
    # The folder's terminal is a session of its own next to the agent.
    assert session_id_for(Path("/a/my.project"), terminal=True) not in (first, second)


def test_build_command_replaces_placeholders() -> None:
    assert build_command(["x", "--name", "{name}"], "demo", None) == ["x", "--name", "demo"]
    assert build_command(["x", "{model}"], "demo", "qwen") == ["x", "qwen"]


def test_build_command_refuses_a_missing_model() -> None:
    with pytest.raises(MissingModelError):
        build_command(["x", "--model", "{model}"], "demo", None)


def test_server_passes_mouse_clipboard_and_focus_on(
    manager: SessionManager, workdir: Path, socket_name: str
) -> None:
    manager.start("sleeper", workdir, resume=False)
    # Wheel scrolling and focus changes reach the agent; its copies (OSC 52) reach the browser.
    assert tmux_query(socket_name, "show-options", "-gv", "mouse") == "on"
    assert tmux_query(socket_name, "show-options", "-gv", "set-clipboard") == "on"
    assert tmux_query(socket_name, "show-options", "-sv", "focus-events") == "on"


def test_a_terminal_runs_next_to_the_folders_agent(manager: SessionManager, workdir: Path) -> None:
    agent = manager.start("sleeper", workdir, resume=False)
    terminal = manager.start("terminal", workdir, resume=False)
    assert (agent.terminal, terminal.terminal) == (False, True)
    assert agent.id != terminal.id
    assert {s.id for s in manager.list()} == {agent.id, terminal.id}
    # Still one of each per folder.
    with pytest.raises(SessionAlreadyRunningError):
        manager.start("echo", workdir, resume=False)
    with pytest.raises(SessionAlreadyRunningError):
        manager.start("terminal", workdir, resume=False)
    assert manager.find_by_path(workdir, terminal=True) == terminal
    assert manager.find_by_path(workdir, terminal=False) == agent


def test_chosen_model_and_environment_stay_with_the_session(
    manager: SessionManager, workdir: Path, socket_name: str
) -> None:
    session = manager.start("chooser", workdir, False, None, "qwen", {"ORC_EFFORT": "medium"})
    assert session.chosen_model == "qwen"

    def screen() -> str:
        for _ in range(50):
            text = manager.text(session.id, 50)
            if "qwen" in text:
                return text
            time.sleep(0.1)
        raise AssertionError("the agent printed nothing")

    assert "started qwen medium" in screen()
    # A restart takes the same model, and the environment it is given now.
    restarted = manager.restart(session, {"ORC_EFFORT": "xhigh"})
    assert restarted.chosen_model == "qwen"
    for _ in range(50):
        if "resumed qwen xhigh" in manager.text(session.id, 50):
            break
        time.sleep(0.1)
    assert "resumed qwen xhigh" in manager.text(session.id, 50)


def test_an_agent_can_be_pasted_into_without_submitting(
    manager: SessionManager, workdir: Path, socket_name: str
) -> None:
    session = manager.start("reader", workdir, resume=False)
    manager.paste_text(session.id, "- not sent yet")
    for _ in range(50):
        if "not sent yet" in manager.text(session.id, 50):
            break
        time.sleep(0.1)
    time.sleep(0.3)
    # cat prints a line only once it is submitted: the terminal's own echo is alone on screen.
    assert manager.text(session.id, 50).count("not sent yet") == 1


def test_text_is_cut_into_pieces() -> None:
    assert text_pieces("abcdefg", 3) == ["abc", "def", "g"]
    assert text_pieces("abc", 3) == ["abc"]
    assert text_pieces("", 3) == []


def test_a_long_line_is_typed_in_pieces_and_arrives_whole(
    manager: SessionManager, workdir: Path
) -> None:
    session = manager.start("reader", workdir, resume=False)
    line = "".join(f"{number:04d}-" for number in range(60))
    manager.type_line(session.id, line)
    for _ in range(50):
        # cat prints the line again once it is submitted: the echo and its output.
        if manager.text(session.id, 50).count(line) == 2:
            break
        time.sleep(0.1)
    assert manager.text(session.id, 50).count(line) == 2
