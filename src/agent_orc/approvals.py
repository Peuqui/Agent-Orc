"""Permission requests of an agent, answered from the web app instead of the terminal.

Claude Code runs the PermissionRequest hook (`agent-orc agent-permission`) whenever it asks the
user, and shows its own prompt in the terminal at the same time (verified with Claude Code
2.1.289): whichever answers first decides. The hook leaves the request as a file and waits for
a decision file next to it; when the user answers in the terminal instead, Claude ends the hook,
which takes its request along. A request whose hook is gone otherwise (killed) is ignored.
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent_orc.state import state_dir, write_atomically

APPROVALS_DIR = "approvals"
REQUEST_SUFFIX = ".request.json"
DECISION_SUFFIX = ".decision.json"
# Tool input fields that say what a request is about, in order of preference.
SUBJECT_FIELDS = ("command", "file_path", "url", "pattern", "path")
MAX_SUBJECT_CHARS = 500
DENIED_MESSAGE = "Denied by the user in Agent-Orc."
# How often the waiting hook looks for the user's decision.
DECISION_POLL_SECONDS = 0.5


class ApprovalNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class ApprovalRequest:
    id: str
    session: str
    tool: str
    # What the tool would do: the command, the file, ...
    subject: str
    description: str | None
    # The waiting hook; a request without it is stale.
    pid: int


def approvals_dir() -> Path:
    return state_dir() / APPROVALS_DIR


def _request_file(request_id: str) -> Path:
    return approvals_dir() / f"{request_id}{REQUEST_SUFFIX}"


def _decision_file(request_id: str) -> Path:
    return approvals_dir() / f"{request_id}{DECISION_SUFFIX}"


def subject_of(tool_input: dict[str, Any]) -> str:
    for field in SUBJECT_FIELDS:
        value = tool_input.get(field)
        if isinstance(value, str):
            return value[:MAX_SUBJECT_CHARS]
    return json.dumps(tool_input)[:MAX_SUBJECT_CHARS]


def open_request(session: str, hook: dict[str, Any]) -> ApprovalRequest:
    tool_input: dict[str, Any] = hook["tool_input"]
    description = tool_input.get("description")
    request = ApprovalRequest(
        id=uuid.uuid4().hex,
        session=session,
        tool=hook["tool_name"],
        subject=subject_of(tool_input),
        description=description if isinstance(description, str) else None,
        pid=os.getpid(),
    )
    write_atomically(_request_file(request.id), json.dumps(asdict(request)))
    return request


def close_request(request_id: str) -> None:
    _request_file(request_id).unlink(missing_ok=True)
    _decision_file(request_id).unlink(missing_ok=True)


def wait_for_decision(request_id: str) -> bool:
    """Blocks until the user decided in the web app; True allows."""
    decision = _decision_file(request_id)
    while not decision.is_file():
        time.sleep(DECISION_POLL_SECONDS)
    allowed: bool = json.loads(decision.read_text(encoding="utf-8"))["allow"]
    return allowed


def hook_answer(allow: bool) -> dict[str, Any]:
    """The PermissionRequest hook output Claude Code takes as the user's answer."""
    decision: dict[str, str] = {"behavior": "allow" if allow else "deny"}
    if not allow:
        decision["message"] = DENIED_MESSAGE
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}


def _hook_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def open_requests() -> list[ApprovalRequest]:
    """Requests whose hook still waits."""
    directory = approvals_dir()
    if not directory.is_dir():
        return []
    requests = []
    for path in directory.glob(f"*{REQUEST_SUFFIX}"):
        try:
            stored = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            # Its hook finished while the directory was being read.
            continue
        requests.append(ApprovalRequest(**json.loads(stored)))
    return [request for request in requests if _hook_alive(request.pid)]


def decide(request_id: str, allow: bool) -> None:
    if not _request_file(request_id).is_file():
        raise ApprovalNotFoundError(request_id)
    write_atomically(_decision_file(request_id), json.dumps({"allow": allow}))
