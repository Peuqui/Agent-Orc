"""Permission requests of an agent, answered from the web app instead of the terminal.

Claude Code runs the PermissionRequest hook (`agent-orc agent-permission`) whenever it asks the
user, and shows its own prompt in the terminal at the same time: whichever answers first
decides. The hook leaves the request as a file and waits for a decision file next to it.

When the user answers in the terminal instead, Claude lets the hook wait on (seen with Claude
Code 2.1.289). So the agent's next hooks close it: the tool ran, failed or was denied (matched
by tool and input, as the permission hook gets no tool use id), or the agent's turn ended,
after which nothing can wait any more. A request whose hook is gone (killed) is ignored.

The answers are those of the terminal: yes (maybe with "don't ask again"), or no with what Claude
should do instead, or no without a word, which stops Claude as Esc does. Claude's plan approval
(ExitPlanMode) is answered with the permission mode to work on in, or with what to change.
"""

import hashlib
import json
import os
import signal
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agent_orc.state import state_dir, write_atomically

APPROVALS_DIR = "approvals"
REQUEST_SUFFIX = ".request.json"
DECISION_SUFFIX = ".decision.json"
# Tool input fields that say what a request is about, in order of preference.
SUBJECT_FIELDS = ("command", "file_path", "url", "pattern", "path")
MAX_SUBJECT_CHARS = 500
# Claude's request to leave plan mode; it takes an allowance only with its input handed back.
PLAN_APPROVAL_TOOL = "ExitPlanMode"
# The permission mode Claude plans in, which an approved plan leaves.
PLAN_MODE = "plan"
# Only a process running this command is ended as a waiting hook (pids get reused).
HOOK_COMMAND = "agent-permission"
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
    # Tool and input, to recognise the tool call once it ran without the web app.
    call: str
    # What Claude Code offers instead of asking again ("Yes, and don't ask again for ..."), as it
    # sent them: permission update entries (addRules, setMode, addDirectories, ...). Optional in
    # the hook input; a request without them can only be allowed or denied once.
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    # The plan in Markdown, for a plan approval.
    plan: str | None = None


@dataclass(frozen=True)
class Decision:
    allow: bool
    # The suggestion of the request to apply with the allowance, as Claude Code sent it.
    suggestion: dict[str, Any] | None = None
    # The permission mode a plan approval lets Claude work on in.
    mode: str | None = None
    # With a denial: what Claude should do instead. A denial without it stops Claude.
    message: str | None = None

    @property
    def stops(self) -> bool:
        return not self.allow and self.message is None


def approvals_dir() -> Path:
    return state_dir() / APPROVALS_DIR


def _request_file(request_id: str) -> Path:
    return approvals_dir() / f"{request_id}{REQUEST_SUFFIX}"


def _decision_file(request_id: str) -> Path:
    return approvals_dir() / f"{request_id}{DECISION_SUFFIX}"


def subject_of(tool_input: dict[str, Any]) -> str:
    for name in SUBJECT_FIELDS:
        value = tool_input.get(name)
        if isinstance(value, str):
            return value[:MAX_SUBJECT_CHARS]
    return json.dumps(tool_input)[:MAX_SUBJECT_CHARS]


def call_key(tool: str, tool_input: dict[str, Any]) -> str:
    text = json.dumps([tool, tool_input], sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


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
        call=call_key(hook["tool_name"], tool_input),
        suggestions=hook.get("permission_suggestions") or [],
        plan=tool_input["plan"] if hook["tool_name"] == PLAN_APPROVAL_TOOL else None,
    )
    write_atomically(_request_file(request.id), json.dumps(asdict(request)))
    return request


def close_request(request_id: str) -> None:
    _request_file(request_id).unlink(missing_ok=True)
    _decision_file(request_id).unlink(missing_ok=True)


def wait_for_decision(request_id: str) -> Decision:
    """Blocks until the user decided in the web app."""
    path = _decision_file(request_id)
    while not path.is_file():
        time.sleep(DECISION_POLL_SECONDS)
    return Decision(**json.loads(path.read_text(encoding="utf-8")))


def hook_answer(decision: Decision, tool_input: dict[str, Any]) -> dict[str, Any]:
    """The PermissionRequest hook output Claude Code takes as the user's answer; a suggestion goes
    back as Claude Code sent it, which applies it as the terminal's "don't ask again" would. An
    approved plan needs its input back, or Claude Code ignores the answer (seen with 2.1.311)."""
    answer: dict[str, Any] = {"behavior": "allow" if decision.allow else "deny"}
    if decision.message is not None:
        answer["message"] = decision.message
    elif decision.stops:
        answer["interrupt"] = True
    if decision.suggestion is not None:
        answer["updatedPermissions"] = [decision.suggestion]
    elif decision.mode is not None:
        answer["updatedInput"] = tool_input
        answer["updatedPermissions"] = [
            {"type": "setMode", "mode": decision.mode, "destination": "session"}
        ]
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": answer}}


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


class InvalidAnswerError(ValueError):
    """The answer does not fit the request: a suggestion it does not have, a suggestion or mode
    with a denial, a plan approved without a mode or another request with one, or a message with
    an allowance."""


def _check_answer(
    request: ApprovalRequest,
    allow: bool,
    suggestion: int | None,
    mode: str | None,
    message: str | None,
) -> None:
    if suggestion is not None and (not allow or not 0 <= suggestion < len(request.suggestions)):
        raise InvalidAnswerError(f"no suggestion {suggestion} to apply with this answer")
    is_plan = request.plan is not None
    if allow and is_plan and mode is None:
        raise InvalidAnswerError("a plan is approved with the mode to work on in")
    if mode is not None and (not allow or not is_plan):
        raise InvalidAnswerError("a mode goes only with an approved plan")
    if message is not None and allow:
        raise InvalidAnswerError("a message goes only with a denial")


def decide(
    request: ApprovalRequest,
    allow: bool,
    suggestion: int | None = None,
    mode: str | None = None,
    message: str | None = None,
) -> None:
    """The user's answer; ``suggestion``: the index of one of the request's suggestions to apply,
    ``mode``: the mode an approved plan lets Claude work on in, ``message``: with a denial, what
    Claude should do instead."""
    if not _request_file(request.id).is_file():
        raise ApprovalNotFoundError(request.id)
    _check_answer(request, allow, suggestion, mode, message)
    entry = None if suggestion is None else request.suggestions[suggestion]
    decision = Decision(allow, entry, mode, message)
    write_atomically(_decision_file(request.id), json.dumps(asdict(decision)))


def _end_hook(request: ApprovalRequest) -> None:
    """End the hook still waiting for an answer the user gave in the terminal."""
    command = Path(f"/proc/{request.pid}/cmdline")
    try:
        is_hook = HOOK_COMMAND in command.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        is_hook = False
    if is_hook:
        # Its handler exits quietly; Claude has its answer already.
        os.kill(request.pid, signal.SIGTERM)
    close_request(request.id)


def close_answered(session: str, tool: str, tool_input: dict[str, Any]) -> None:
    """The tool call ran, failed or was denied: its question has been answered."""
    key = call_key(tool, tool_input)
    for request in open_requests():
        if request.session == session and request.call == key:
            _end_hook(request)


def close_session_requests(session: str) -> None:
    """The agent's turn ended or a new one began: none of its questions is open any more."""
    for request in open_requests():
        if request.session == session:
            _end_hook(request)
