"""Reasoning effort as a setting of the project folder.

Claude Code reads `effortLevel` from <folder>/.claude/settings.local.json; it takes precedence
over the user's global settings (verified, including the global per-model settings) and
affects nobody else. A running session does not pick up a change, so changing the effort
of a running agent means resuming it. Setting it here, rather than with /effort inside the
session, matters: /effort silently saves the level as the user's global default.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CLAUDE_PROJECT_SETTINGS = Path(".claude") / "settings.local.json"
CLAUDE_EFFORT_KEY = "effortLevel"
NEW_SETTINGS_MODE = 0o644


class InvalidEffortError(ValueError):
    pass


def _read_settings(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return settings


def read_claude_project_effort(folder: Path) -> str | None:
    effort = _read_settings(folder / CLAUDE_PROJECT_SETTINGS).get(CLAUDE_EFFORT_KEY)
    return effort if isinstance(effort, str) else None


def write_claude_project_effort(folder: Path, effort: str | None) -> None:
    """Set (or with None remove) the project's effort; all other settings stay as they are."""
    path = folder / CLAUDE_PROJECT_SETTINGS
    settings = _read_settings(path)
    # Also covers "nothing set, nothing wanted": get() then returns None == effort.
    if settings.get(CLAUDE_EFFORT_KEY) == effort:
        return
    if effort is None:
        del settings[CLAUDE_EFFORT_KEY]
    else:
        settings[CLAUDE_EFFORT_KEY] = effort
    path.parent.mkdir(exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else NEW_SETTINGS_MODE
    temporary = path.with_name(f"{path.name}.agent-orc-tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")
    os.chmod(temporary, mode)
    temporary.replace(path)


@dataclass(frozen=True)
class EffortStore:
    read: Callable[[Path], str | None]
    write: Callable[[Path, str | None], None]


# Per agent profile setting "effort.store".
EFFORT_STORES: dict[str, EffortStore] = {
    "claude_project": EffortStore(read_claude_project_effort, write_claude_project_effort),
}
