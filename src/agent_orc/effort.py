"""Reasoning (effort and ultracode) as a setting of the project folder.

Claude Code reads `effortLevel` from <folder>/.claude/settings.local.json; it takes precedence
over the user's global settings (verified, including the global per-model settings) and
affects nobody else. The same file holds `ultracode` (workflow orchestration, independent of
the effort level; documented settings key, verified in the installed Claude Code). A running
session does not pick up a change, so changing the reasoning of a running agent means
resuming it. Setting it here, rather than with /effort inside the session, matters: /effort
silently saves the level as the user's global default.

A running Claude Code session can take a new reasoning in place: typing `/effort <level>` (and
`/effort ultracode on|off`) switches it at once, without a restart, so its background tasks
keep running (verified with Claude Code 2.1.289). /effort also rewrites the user's own
settings file; set_reasoning_live puts that file back as it was.

The same file also holds the permission mode a session starts in (`permissions.defaultMode`,
values as listed by the installed Claude Code); inside a session Shift+Tab switches it.
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_orc.config import LiveEffortConfig

CLAUDE_PROJECT_SETTINGS = Path(".claude") / "settings.local.json"
CLAUDE_EFFORT_KEY = "effortLevel"
CLAUDE_ULTRACODE_KEY = "ultracode"
CLAUDE_PERMISSIONS_KEY = "permissions"
CLAUDE_DEFAULT_MODE_KEY = "defaultMode"
NEW_SETTINGS_MODE = 0o644


class InvalidEffortError(ValueError):
    pass


class InvalidPermissionModeError(ValueError):
    pass


def _read_settings(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return settings


@dataclass(frozen=True)
class Reasoning:
    # None: the agent's own default.
    effort: str | None
    ultracode: bool


def read_claude_project_reasoning(folder: Path) -> Reasoning:
    settings = _read_settings(folder / CLAUDE_PROJECT_SETTINGS)
    effort = settings.get(CLAUDE_EFFORT_KEY)
    return Reasoning(
        effort=effort if isinstance(effort, str) else None,
        ultracode=settings.get(CLAUDE_ULTRACODE_KEY) is True,
    )


def write_claude_project_reasoning(folder: Path, reasoning: Reasoning) -> None:
    """Set the project's reasoning; all other settings stay as they are.

    An effort of None and ultracode off remove their keys: the user's own settings apply then.
    """
    path = folder / CLAUDE_PROJECT_SETTINGS
    settings = _read_settings(path)
    wanted = {
        CLAUDE_EFFORT_KEY: reasoning.effort,
        CLAUDE_ULTRACODE_KEY: True if reasoning.ultracode else None,
    }
    # Also covers "nothing set, nothing wanted": get() then returns None == value.
    if all(settings.get(key) == value for key, value in wanted.items()):
        return
    for key, value in wanted.items():
        if value is None:
            settings.pop(key, None)
        else:
            settings[key] = value
    _write_settings(path, settings)


def _write_settings(path: Path, settings: dict[str, Any]) -> None:
    """Replace the settings file at once, keeping its file mode."""
    path.parent.mkdir(exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else NEW_SETTINGS_MODE
    temporary = path.with_name(f"{path.name}.agent-orc-tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")
    os.chmod(temporary, mode)
    temporary.replace(path)


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


def _write_bytes_keeping_mode(path: Path, content: bytes) -> None:
    temporary = path.with_name(f"{path.name}.agent-orc-tmp")
    temporary.write_bytes(content)
    os.chmod(temporary, path.stat().st_mode & 0o777)
    temporary.replace(path)


def read_claude_permission_mode(folder: Path) -> str | None:
    """The mode the folder's sessions start in; None: the user's own setting."""
    permissions = _read_settings(folder / CLAUDE_PROJECT_SETTINGS).get(CLAUDE_PERMISSIONS_KEY)
    mode = permissions.get(CLAUDE_DEFAULT_MODE_KEY) if isinstance(permissions, dict) else None
    return mode if isinstance(mode, str) else None


def write_claude_permission_mode(folder: Path, mode: str) -> None:
    """Set the start mode; the folder's other permissions (allow lists, ...) stay as they are."""
    if read_claude_permission_mode(folder) == mode:
        return
    path = folder / CLAUDE_PROJECT_SETTINGS
    settings = _read_settings(path)
    settings.setdefault(CLAUDE_PERMISSIONS_KEY, {})[CLAUDE_DEFAULT_MODE_KEY] = mode
    _write_settings(path, settings)


@dataclass(frozen=True)
class EffortStore:
    read: Callable[[Path], Reasoning]
    write: Callable[[Path, Reasoning], None]


# Per agent profile setting "effort.store".
EFFORT_STORES: dict[str, EffortStore] = {
    "claude_project": EffortStore(read_claude_project_reasoning, write_claude_project_reasoning),
}


@dataclass(frozen=True)
class PermissionStore:
    read: Callable[[Path], str | None]
    write: Callable[[Path, str], None]


# Per agent profile setting "permission.store".
PERMISSION_STORES: dict[str, PermissionStore] = {
    "claude_project": PermissionStore(read_claude_permission_mode, write_claude_permission_mode),
}
