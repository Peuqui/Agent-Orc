"""Reasoning (effort and ultracode) and permission mode of each agent.

Agent-Orc keeps them per agent: by its session id, which its folder and suffix make, so they
outlast a stop and preselect the next start under the same name. At every start the agent gets
them in a settings file of its own (Claude: --settings <file>). Settings given at start take
precedence over the project folder's (.claude/settings.local.json), and of several --settings
only the last counts (both verified with Claude Code 2.1.295): the file also carries the
profile's own settings (status line, hooks), and states every value explicitly, so an older
value in the folder's file does not show through. Setting them here, rather than with /effort
inside the session, matters: /effort silently saves the level as the user's global default.

A running Claude Code session can take a new reasoning in place: typing `/effort <level>` (and
`/effort ultracode on|off`) switches it at once, without a restart, so its background tasks
keep running (verified with Claude Code 2.1.289). /effort also rewrites the user's own
settings file; set_reasoning_live puts that file back as it was. The permission mode switches
inside a session with Shift+Tab.
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_orc.config import LiveEffortConfig
from agent_orc.state import state_dir, write_atomically

CLAUDE_EFFORT_KEY = "effortLevel"
CLAUDE_ULTRACODE_KEY = "ultracode"
CLAUDE_PERMISSIONS_KEY = "permissions"
CLAUDE_DEFAULT_MODE_KEY = "defaultMode"
# Keys of an agent's stored choices.
EFFORT_KEY = "effort"
ULTRACODE_KEY = "ultracode"
PERMISSION_MODE_KEY = "permission_mode"


class InvalidEffortError(ValueError):
    pass


class InvalidPermissionModeError(ValueError):
    pass


@dataclass(frozen=True)
class Reasoning:
    # None: the agent's own default.
    effort: str | None
    ultracode: bool


def agents_dir() -> Path:
    return state_dir() / "agents"


def _choices_file(session_id: str) -> Path:
    return agents_dir() / f"{session_id}.json"


def agent_settings_file(session_id: str) -> Path:
    """The settings file the agent gets at start ({settings} in its command)."""
    return agents_dir() / f"{session_id}.settings.json"


def _read_choices(session_id: str) -> dict[str, Any]:
    path = _choices_file(session_id)
    if not path.is_file():
        return {}
    choices: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return choices


def _store_choices(session_id: str, changes: dict[str, Any]) -> None:
    choices = {**_read_choices(session_id), **changes}
    write_atomically(_choices_file(session_id), json.dumps(choices))


def read_agent_reasoning(session_id: str) -> Reasoning | None:
    """The agent's reasoning; None until one was stored for it."""
    choices = _read_choices(session_id)
    if EFFORT_KEY not in choices:
        return None
    return Reasoning(effort=choices[EFFORT_KEY], ultracode=choices[ULTRACODE_KEY])


def store_agent_reasoning(session_id: str, reasoning: Reasoning) -> None:
    _store_choices(session_id, {EFFORT_KEY: reasoning.effort, ULTRACODE_KEY: reasoning.ultracode})


def read_agent_permission_mode(session_id: str) -> str | None:
    """The mode the agent starts in; None until one was stored for it."""
    mode = _read_choices(session_id).get(PERMISSION_MODE_KEY)
    return mode if isinstance(mode, str) else None


def store_agent_permission_mode(session_id: str, mode: str) -> None:
    _store_choices(session_id, {PERMISSION_MODE_KEY: mode})


def claude_settings(
    base: dict[str, Any], reasoning: Reasoning | None, permission_mode: str | None
) -> dict[str, Any]:
    """The profile's settings with the agent's own values in Claude's keys. Ultracode is always
    stated (off as false), so an older value in the folder's settings does not show through."""
    settings = dict(base)
    if reasoning is not None:
        if reasoning.effort is not None:
            settings[CLAUDE_EFFORT_KEY] = reasoning.effort
        settings[CLAUDE_ULTRACODE_KEY] = reasoning.ultracode
    if permission_mode is not None:
        permissions = dict(settings.get(CLAUDE_PERMISSIONS_KEY, {}))
        permissions[CLAUDE_DEFAULT_MODE_KEY] = permission_mode
        settings[CLAUDE_PERMISSIONS_KEY] = permissions
    return settings


def write_agent_settings(session_id: str, settings: dict[str, Any]) -> Path:
    return write_atomically(agent_settings_file(session_id), json.dumps(settings, indent=2))


# How long after typing /effort or /model the protected file is watched for the agent's rewrite.
PROTECT_SECONDS = 5.0
PROTECT_POLL_SECONDS = 0.2


def set_reasoning_live(
    type_line: Callable[[str], None],
    live: LiveEffortConfig,
    previous: Reasoning,
    wanted: Reasoning,
) -> None:
    """Switch a running agent's reasoning by typing its commands; the protected file stays.

    `wanted.effort` is always typed (it may differ from what the agent runs with), ultracode
    only when it changes.
    """

    def type_commands() -> None:
        type_line(live.command.format(level=wanted.effort))
        if wanted.ultracode != previous.ultracode:
            type_line(live.ultracode_command.format(state="on" if wanted.ultracode else "off"))

    keep_file_while(live.protected_file, type_commands)


def keep_file_while(protected_file: str, action: Callable[[], None]) -> None:
    """Run `action` (typing a command that makes the agent rewrite the file) and undo whatever
    the agent writes into the file shortly after."""
    protected = Path(protected_file).expanduser()
    before = protected.read_bytes() if protected.is_file() else None
    action()
    # The agent rewrites the file shortly after; whatever it writes within this time is undone.
    deadline = time.monotonic() + PROTECT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(PROTECT_POLL_SECONDS)
        current = protected.read_bytes() if protected.is_file() else None
        if current == before:
            continue
        if before is None:
            protected.unlink()
        else:
            _write_bytes_keeping_mode(protected, before)


# How long after typing a command the agent may take to ask for a confirmation.
CONFIRM_SECONDS = 2.0
CONFIRM_POLL_SECONDS = 0.1


def confirm_when_asked(
    read_screen: Callable[[], str], press_enter: Callable[[], None], asking: str
) -> None:
    """Press Enter once the agent's screen shows `asking`; nothing if it does not ask."""
    deadline = time.monotonic() + CONFIRM_SECONDS
    while time.monotonic() < deadline:
        if asking in read_screen():
            press_enter()
            return
        time.sleep(CONFIRM_POLL_SECONDS)


def _write_bytes_keeping_mode(path: Path, content: bytes) -> None:
    temporary = path.with_name(f"{path.name}.agent-orc-tmp")
    temporary.write_bytes(content)
    os.chmod(temporary, path.stat().st_mode & 0o777)
    temporary.replace(path)
