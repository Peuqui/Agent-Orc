"""Files the user attaches for an agent (a photo, a screenshot), stored in its project folder.

Agents read files by path (Claude Code: "@path" in the prompt), so an attachment lands where
the agent works, in <folder>/.agent-orc/uploads/. A .gitignore with "*" inside .agent-orc keeps
the whole directory out of the project's repository without touching the project's own files.
"""

import re
import time
from pathlib import Path

from agent_orc.auth import Clock

# Where notes link to their files (relative to the page); the server serves them there.
NOTE_FILES_URL = "api/notes/files"
NOTE_FILE_LINK = re.compile(r"!?\[[^\]]*\]\(" + re.escape(NOTE_FILES_URL) + r"/([^)\s]+)\)")
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


def bring_note_files(text: str, folder: Path, notes_folder: Path, clock: Clock) -> str:
    """The note's text for an agent: each linked file is copied into the agent's folder and the
    link becomes "@path" there, as an attachment of its own would."""

    def replace(link: re.Match[str]) -> str:
        source = notes_folder / UPLOADS_DIR / link.group(1)
        if not source.is_file():
            return link.group(0)
        return f"@{store_attachment(folder, source.name, source.read_bytes(), clock)}"

    return NOTE_FILE_LINK.sub(replace, text)
