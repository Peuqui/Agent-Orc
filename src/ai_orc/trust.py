"""Mark a folder as trusted before an agent starts there, so it does not stop at a
"do you trust this folder?" prompt. Starting an agent in a folder via AI-Orc is the user's
explicit decision to trust it."""

import json
import os
from collections.abc import Callable
from pathlib import Path

# Claude Code keeps per-folder state, including the trust decision, in this file.
CLAUDE_STATE = Path(".claude.json")
CLAUDE_STATE_MODE = 0o600


def trust_claude_folder(home: Path, folder: Path) -> None:
    """Set projects[folder].hasTrustDialogAccepted in ~/.claude.json.

    Running Claude instances rewrite this file now and then. Writing a temporary file and
    renaming it means the file is never half-written; should an instance overwrite the
    entry in the same moment, Claude simply asks once more.
    """
    path = home / CLAUDE_STATE
    state = json.loads(path.read_text(encoding="utf-8"))
    project = state.setdefault("projects", {}).setdefault(str(folder), {})
    if project.get("hasTrustDialogAccepted"):
        return
    project["hasTrustDialogAccepted"] = True
    temporary = path.with_name(f"{path.name}.ai-orc-tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, CLAUDE_STATE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    temporary.replace(path)


# Per agent profile setting "trust".
FOLDER_TRUST: dict[str, Callable[[Path, Path], None]] = {
    "claude": trust_claude_folder,
}
