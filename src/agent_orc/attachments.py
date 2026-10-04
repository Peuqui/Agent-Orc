"""Files the user attaches for an agent (a photo, a screenshot), stored in its project folder.

Agents read files by path (Claude Code: "@path" in the prompt), so an attachment lands where
the agent works, in <folder>/.agent-orc/uploads/. A .gitignore with "*" inside .agent-orc keeps
the whole directory out of the project's repository without touching the project's own files.
"""

import re
import time
from pathlib import Path

from agent_orc.auth import Clock

AGENT_ORC_DIR = ".agent-orc"
UPLOADS_DIR = Path(AGENT_ORC_DIR) / "uploads"
IGNORE_EVERYTHING = "*\n"
# Characters that stay in a file name; everything else becomes "-".
UNSAFE_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]+")
UNNAMED = "attachment"
TIME_PREFIX_FORMAT = "%Y%m%d-%H%M%S"


def store_attachment(folder: Path, name: str, content: bytes, clock: Clock) -> Path:
    """Store the file and return its path relative to the folder, as the agent addresses it."""
    uploads = folder / UPLOADS_DIR
    uploads.mkdir(parents=True, exist_ok=True)
    ignore = folder / AGENT_ORC_DIR / ".gitignore"
    if not ignore.exists():
        ignore.write_text(IGNORE_EVERYTHING, encoding="utf-8")
    safe_name = UNSAFE_NAME_CHARACTERS.sub("-", Path(name).name).strip("-.") or UNNAMED
    stamp = time.strftime(TIME_PREFIX_FORMAT, time.localtime(clock()))
    target = uploads / f"{stamp}-{safe_name}"
    counter = 1
    # Two attachments within the same second keep their own files.
    while target.exists():
        target = uploads / f"{stamp}-{counter}-{safe_name}"
        counter += 1
    target.write_bytes(content)
    return target.relative_to(folder)
