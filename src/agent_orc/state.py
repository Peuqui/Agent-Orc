"""Agent-Orc's own state on disk, below the XDG state directory."""

import json
import os
from pathlib import Path
from typing import Any

CARD_ORDER_FILE = "card-order.json"
WORKSPACES_FILE = "workspaces.json"
PROMPT_TEMPLATES_FILE = "prompt-templates.json"
EXTRA_KEYS_FILE = "extra-keys.json"
# Key of the unnamed workspace in the workspaces file; a name the user gives is never empty.
UNNAMED_WORKSPACE = ""


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
    """Workspaces (open agents, columns, widths) by name, the unnamed one under
    UNNAMED_WORKSPACE; empty until one is arranged."""
    path = state_dir() / WORKSPACES_FILE
    if not path.is_file():
        return {}
    workspaces: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return workspaces


def write_workspaces(workspaces: dict[str, Any]) -> None:
    write_atomically(state_dir() / WORKSPACES_FILE, json.dumps(workspaces))


def empty_workspace() -> dict[str, Any]:
    return {"tabs": [], "visible": 1, "widths": {}, "active": None}


def remove_workspace(workspaces: dict[str, Any], name: str) -> None:
    """Delete a named workspace; its agents move to the unnamed one."""
    removed = workspaces.pop(name, None)
    if removed is None:
        return
    unnamed = workspaces.setdefault(UNNAMED_WORKSPACE, empty_workspace())
    unnamed["tabs"].extend(agent for agent in removed["tabs"] if agent not in unnamed["tabs"])


def keep_living_agents(workspace: dict[str, Any], living: set[str]) -> dict[str, Any]:
    """The workspace without the agents that no longer exist (a stopped agent leaves its entry)."""
    tabs = [agent for agent in workspace["tabs"] if agent in living]
    active = workspace["active"]
    return {
        **workspace,
        "tabs": tabs,
        "widths": {agent: width for agent, width in workspace["widths"].items() if agent in tabs},
        "active": active if active in tabs else (tabs[0] if tabs else None),
    }


def place_workspace(workspaces: dict[str, Any], key: str, workspace: dict[str, Any]) -> None:
    """Store a workspace; its agents leave every other one, as an agent lives in one workspace."""
    workspaces[key] = workspace
    for other_key, other in workspaces.items():
        if other_key == key:
            continue
        other["tabs"] = [agent for agent in other["tabs"] if agent not in workspace["tabs"]]
        other["widths"] = {a: w for a, w in other["widths"].items() if a in other["tabs"]}
        if other["active"] not in other["tabs"]:
            other["active"] = other["tabs"][0] if other["tabs"] else None


def read_prompt_templates() -> list[dict[str, str]]:
    """The user's prompt templates ({"label", "text"}) in their order; empty until one is made."""
    path = state_dir() / PROMPT_TEMPLATES_FILE
    if not path.is_file():
        return []
    templates: list[dict[str, str]] = json.loads(path.read_text(encoding="utf-8"))
    return templates


def write_prompt_templates(templates: list[dict[str, str]]) -> None:
    write_atomically(state_dir() / PROMPT_TEMPLATES_FILE, json.dumps(templates))


def read_extra_keys() -> list[list[dict[str, Any]]] | None:
    """The user's arrangement of the extra keys, for every device; None until arranged (then the
    config's keys hold)."""
    path = state_dir() / EXTRA_KEYS_FILE
    if not path.is_file():
        return None
    rows: list[list[dict[str, Any]]] = json.loads(path.read_text(encoding="utf-8"))
    return rows


def write_extra_keys(rows: list[list[dict[str, Any]]]) -> None:
    write_atomically(state_dir() / EXTRA_KEYS_FILE, json.dumps(rows, ensure_ascii=False))


def reset_extra_keys() -> None:
    (state_dir() / EXTRA_KEYS_FILE).unlink(missing_ok=True)
