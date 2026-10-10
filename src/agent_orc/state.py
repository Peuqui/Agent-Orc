"""Agent-Orc's own state on disk, below the XDG state directory."""

import json
import os
from pathlib import Path
from typing import Any

CARD_ORDER_FILE = "card-order.json"
WORKSPACES_FILE = "workspaces.json"
PROMPT_TEMPLATES_FILE = "prompt-templates.json"
EXTRA_KEYS_FILE = "extra-keys.json"
NOTEBOOKS_FILE = "notebooks.json"
BASE_DIR_FILE = "base-dir.json"
ANSWERS_SEEN_FILE = "answers-seen.json"
# Key of the unnamed workspace in the workspaces file; a name the user gives is never empty.
UNNAMED_WORKSPACE = ""


def state_dir() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state_home) / "agent-orc"


def notes_dir() -> Path:
    """Where the files attached to notes live (in the layout of attachments.py)."""
    return state_dir() / "notes"


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


def add_unassigned_agents(
    workspaces: dict[str, Any], living: set[str], unnamed: dict[str, Any]
) -> dict[str, Any]:
    """The unnamed workspace plus every living agent that is in no workspace at all, so no
    agent is ever invisible."""
    assigned = {agent for workspace in workspaces.values() for agent in workspace["tabs"]}
    tabs = unnamed["tabs"] + sorted(living - assigned)
    return {**unnamed, "tabs": tabs, "active": unnamed["active"] or (tabs[0] if tabs else None)}


def assign_agent(workspaces: dict[str, Any], key: str, agent: str) -> None:
    """Put the agent at the end of the workspace `key`; it leaves the one it was in."""
    workspace = workspaces.get(key, empty_workspace())
    if agent not in workspace["tabs"]:
        workspace["tabs"].append(agent)
    workspace["active"] = workspace["active"] or agent
    place_workspace(workspaces, key, workspace)


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


def read_notebooks() -> dict[str, Any]:
    """Notebooks by name, in the order the user keeps them; empty until one is created."""
    path = state_dir() / NOTEBOOKS_FILE
    if not path.is_file():
        return {}
    notebooks: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return notebooks


def write_notebooks(notebooks: dict[str, Any]) -> None:
    write_atomically(state_dir() / NOTEBOOKS_FILE, json.dumps(notebooks))


def rename_notebook(notebooks: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """The notebooks with `old` renamed to `new`, at the same position."""
    return {(new if name == old else name): notebook for name, notebook in notebooks.items()}


def read_answers_seen() -> dict[str, str]:
    """Per agent the time of the newest answer looked at (ISO), on any device."""
    path = state_dir() / ANSWERS_SEEN_FILE
    if not path.is_file():
        return {}
    seen: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return seen


def mark_answers_seen(session_id: str, time: str) -> None:
    """Only ever forward: a device that saw less (ISO times compare as text) changes nothing."""
    seen = read_answers_seen()
    if time <= seen.get(session_id, ""):
        return
    write_atomically(state_dir() / ANSWERS_SEEN_FILE, json.dumps({**seen, session_id: time}))


def read_base_dir() -> Path | None:
    """The base directory the user set in the app, which wins over the config's; None if none."""
    path = state_dir() / BASE_DIR_FILE
    if not path.is_file():
        return None
    return Path(json.loads(path.read_text(encoding="utf-8"))["path"])


def write_base_dir(folder: Path) -> None:
    write_atomically(state_dir() / BASE_DIR_FILE, json.dumps({"path": str(folder)}))
