"""Earlier conversations of an agent in a folder, so any of them can be resumed.

Claude Code keeps each conversation as ~/.claude/projects/<folder>/<id>.jsonl, no matter
whether it ran in a terminal, in VS Code or in Agent-Orc, so all of them are listed here.
"""

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_orc.auth import Clock

CLAUDE_PROJECTS = Path(".claude") / "projects"
CLAUDE_TITLE_ENTRY = "ai-title"
CONVERSATION_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
READ_CHUNK_BYTES = 256 * 1024
# Claude refreshes the title during a conversation, so it sits near the end; stop looking
# after this much and take the first message instead.
TITLE_SCAN_BYTES = 4 * 1024 * 1024
TITLE_MAX_CHARS = 100
# Written to this recently: probably still open elsewhere (e.g. in VS Code).
RECENTLY_ACTIVE_SECONDS = 120


class ConversationNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    modified: float
    size: int
    recently_active: bool


def claude_project_dir(home: Path, folder: Path) -> Path:
    """Claude Code names a folder's transcript directory after its path, every character
    except letters and digits replaced by '-' (verified with a path containing '.' and '_')."""
    return home / CLAUDE_PROJECTS / re.sub(r"[^A-Za-z0-9]", "-", str(folder))


def _lines_from_end(path: Path, limit: int) -> Iterator[str]:
    """Complete lines from the end of a file, reading at most `limit` bytes."""
    with path.open("rb") as handle:
        position = handle.seek(0, 2)
        stop = max(0, position - limit)
        rest = b""
        while position > stop:
            size = min(READ_CHUNK_BYTES, position - stop)
            position -= size
            handle.seek(position)
            lines = (handle.read(size) + rest).split(b"\n")
            # The first piece may be cut off; keep it for the next, earlier block.
            rest = lines.pop(0)
            for line in reversed(lines):
                if line.strip():
                    yield line.decode("utf-8", errors="replace")
        if position == 0 and rest.strip():
            yield rest.decode("utf-8", errors="replace")


def _first_prompt(path: Path) -> str:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            entry: dict[str, Any] = json.loads(line)
            content = (
                entry.get("message", {}).get("content") if entry.get("type") == "user" else None
            )
            # Plain text only; lists are tool results, "<...>" are commands and notices.
            if isinstance(content, str) and content.strip() and not content.startswith("<"):
                return content.strip().splitlines()[0]
    return ""


def _claude_title(path: Path) -> str:
    for line in _lines_from_end(path, TITLE_SCAN_BYTES):
        entry: dict[str, Any] = json.loads(line)
        if entry.get("type") == CLAUDE_TITLE_ENTRY and entry.get("aiTitle"):
            return str(entry["aiTitle"])
    return _first_prompt(path)


def list_claude_conversations(home: Path, folder: Path, clock: Clock) -> list[Conversation]:
    """Newest first."""
    directory = claude_project_dir(home, folder)
    if not directory.is_dir():
        return []
    conversations = []
    for path in directory.glob("*.jsonl"):
        if not CONVERSATION_ID.match(path.stem):
            continue
        stat = path.stat()
        conversations.append(
            Conversation(
                id=path.stem,
                title=_claude_title(path)[:TITLE_MAX_CHARS],
                modified=stat.st_mtime,
                size=stat.st_size,
                recently_active=clock() - stat.st_mtime < RECENTLY_ACTIVE_SECONDS,
            )
        )
    return sorted(conversations, key=lambda conversation: conversation.modified, reverse=True)


# Per agent profile setting "conversations.source".
CONVERSATION_SOURCES: dict[str, Callable[[Path, Path, Clock], list[Conversation]]] = {
    "claude": list_claude_conversations,
}
