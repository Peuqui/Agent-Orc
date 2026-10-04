"""Reasoning (effort and ultracode) as a setting of the project folder.

Claude Code reads `effortLevel` from <folder>/.claude/settings.local.json; it takes precedence
over the user's global settings (verified, including the global per-model settings) and
affects nobody else. The same file holds `ultracode` (workflow orchestration, independent of
the effort level; documented settings key, verified in the installed Claude Code). A running
session does not pick up a change, so changing the reasoning of a running agent means
resuming it. Setting it here, rather than with /effort inside the session, matters: /effort
silently saves the level as the user's global default.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CLAUDE_PROJECT_SETTINGS = Path(".claude") / "settings.local.json"
CLAUDE_EFFORT_KEY = "effortLevel"
CLAUDE_ULTRACODE_KEY = "ultracode"
NEW_SETTINGS_MODE = 0o644


class InvalidEffortError(ValueError):
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
    read: Callable[[Path], Reasoning]
    write: Callable[[Path, Reasoning], None]


# Per agent profile setting "effort.store".
EFFORT_STORES: dict[str, EffortStore] = {
    "claude_project": EffortStore(read_claude_project_reasoning, write_claude_project_reasoning),
}
