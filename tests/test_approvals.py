import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agent_orc.approvals import (
    DENIED_MESSAGE,
    ApprovalNotFoundError,
    approvals_dir,
    close_request,
    decide,
    hook_answer,
    open_request,
    open_requests,
    subject_of,
)
from agent_orc.sessions import SESSION_ENV

HOOK_INPUT = {
    "hook_event_name": "PermissionRequest",
    "tool_name": "Bash",
    "tool_input": {"command": "rm probe-file.txt", "description": "Remove the probe file"},
}
WAIT_STEPS = 100
WAIT_STEP_SECONDS = 0.05


@pytest.fixture(autouse=True)
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "state"


def test_subject_is_what_the_tool_would_do() -> None:
    assert subject_of({"command": "git push", "description": "Push"}) == "git push"
    assert subject_of({"file_path": "/w/a.py", "content": "x"}) == "/w/a.py"
    assert subject_of({"query": "tmux"}) == '{"query": "tmux"}'


def test_request_is_listed_until_closed_and_decided_once() -> None:
    request = open_request("garden-1", HOOK_INPUT)
    assert open_requests() == [request]
    assert (request.tool, request.subject, request.description) == (
        "Bash",
        "rm probe-file.txt",
        "Remove the probe file",
    )
    close_request(request.id)
    assert open_requests() == []
    with pytest.raises(ApprovalNotFoundError):
        decide(request.id, allow=True)


def test_request_of_a_vanished_hook_is_ignored() -> None:
    request = open_request("garden-1", HOOK_INPUT)
    ended = subprocess.Popen(["true"])
    ended.wait()
    stored = approvals_dir() / f"{request.id}.request.json"
    stored.write_text(json.dumps({**json.loads(stored.read_text()), "pid": ended.pid}))
    assert open_requests() == []


def test_denial_carries_a_message() -> None:
    answer = hook_answer(allow=False)["hookSpecificOutput"]
    assert answer["decision"] == {"behavior": "deny", "message": DENIED_MESSAGE}
    assert hook_answer(allow=True)["hookSpecificOutput"]["decision"] == {"behavior": "allow"}


def start_hook(state: Path) -> subprocess.Popen[str]:
    environment = {**os.environ, "XDG_STATE_HOME": str(state), SESSION_ENV: "garden-1"}
    hook = subprocess.Popen(
        [sys.executable, "-c", "from agent_orc.cli import main; main()", "agent-permission"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env=environment,
    )
    assert hook.stdin is not None
    hook.stdin.write(json.dumps(HOOK_INPUT))
    hook.stdin.close()
    for _ in range(WAIT_STEPS):
        if open_requests():
            return hook
        time.sleep(WAIT_STEP_SECONDS)
    raise AssertionError("the hook did not open its request")


def test_hook_answers_claude_with_the_users_decision(state: Path) -> None:
    hook = start_hook(state)
    decide(open_requests()[0].id, allow=True)
    assert hook.wait(timeout=10) == 0
    assert hook.stdout is not None
    assert json.loads(hook.stdout.read()) == hook_answer(allow=True)
    assert open_requests() == []
    assert list(approvals_dir().iterdir()) == []


def test_hook_ended_by_claude_takes_its_request_along(state: Path) -> None:
    # Claude ends the hook when the user answers in the terminal.
    hook = start_hook(state)
    hook.send_signal(signal.SIGTERM)
    hook.wait(timeout=10)
    assert list(approvals_dir().iterdir()) == []
