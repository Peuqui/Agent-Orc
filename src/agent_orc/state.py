"""Agent-Orc's own state on disk, below the XDG state directory."""

import json
import os
from pathlib import Path
from typing import Any

CARD_ORDER_FILE = "card-order.json"
WORKSPACES_FILE = "workspaces.json"


def state_dir() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state_home) / "agent-orc"


def write_atomically(target: Path, text: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temporary file and rename, so readers never see a half-written file.
    temporary = target.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(target)
    return target


def read_card_order() -> list[str]:
    """Folders in the order the user arranged their agent cards; empty until arranged."""
    path = state_dir() / CARD_ORDER_FILE
    if not path.is_file():
        return []
    order: list[str] = json.loads(path.read_text(encoding="utf-8"))
    return order


def write_card_order(folders: list[str]) -> None:
    write_atomically(state_dir() / CARD_ORDER_FILE, json.dumps(folders))


def read_workspaces() -> dict[str, Any]:
    """Named workspaces (open agents, columns, widths) by name; empty until one is named."""
    path = state_dir() / WORKSPACES_FILE
    if not path.is_file():
        return {}
    workspaces: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return workspaces


def write_workspaces(workspaces: dict[str, Any]) -> None:
    write_atomically(state_dir() / WORKSPACES_FILE, json.dumps(workspaces))
