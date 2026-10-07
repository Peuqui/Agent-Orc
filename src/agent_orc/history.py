"""Earlier conversations of an agent in a folder, so any of them can be resumed.

Claude Code keeps each conversation as ~/.claude/projects/<folder>/<id>.jsonl, no matter
whether it ran in a terminal, in VS Code or in Agent-Orc, so all of them are listed here.
"""

import json
import re
import shutil
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent_orc.auth import Clock
from agent_orc.scope import OutsideScopeError

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
# A search lists at most this many conversations, the newest first.
SEARCH_RESULTS = 30
# Characters of context on each side of a hit in its excerpt.
EXCERPT_CONTEXT_CHARS = 60


class ConversationNotFoundError(LookupError):
    pass


class ConversationInUseError(RuntimeError):
    """The conversation is still being written: an agent runs in it, or another program has it
    open."""


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


def lines_from_end(path: Path, limit: int) -> Iterator[str]:
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
    for line in lines_from_end(path, TITLE_SCAN_BYTES):
        entry: dict[str, Any] = json.loads(line)
        if entry.get("type") == CLAUDE_TITLE_ENTRY and entry.get("aiTitle"):
            return str(entry["aiTitle"])
    return _first_prompt(path)


def list_claude_conversations(home: Path, folder: Path, clock: Clock) -> list[Conversation]:
    """Newest first."""
    directory = claude_project_dir(home, folder)
    return _list_directory(directory, clock) if directory.is_dir() else []


def _list_directory(directory: Path, clock: Clock) -> list[Conversation]:
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


@dataclass(frozen=True)
class CleanupConversation(Conversation):
    # Not to be deleted now (see ConversationInUseError).
    in_use: bool


@dataclass(frozen=True)
class ProjectConversations:
    """All conversations kept for one project folder."""

    # Name of the transcript directory under ~/.claude/projects, to address deletions.
    directory: str
    folder: Path
    conversations: list[CleanupConversation]


def _project_folder(directory: Path) -> Path | None:
    """The folder the conversations in a transcript directory ran in. The directory name cannot
    tell (every special character became '-'), the conversation's own entries do."""
    for path in directory.glob("*.jsonl"):
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                folder = json.loads(line).get("cwd")
                if isinstance(folder, str):
                    return Path(folder)
    return None


def _conversation_bytes(directory: Path, conversation_id: str) -> int:
    """What a conversation takes on disk: its transcript and the folder of results beside it."""
    results = directory / conversation_id
    return (directory / f"{conversation_id}.jsonl").stat().st_size + sum(
        file.stat().st_size for file in results.rglob("*") if file.is_file()
    )


def _in_scope_project_folder(directory: Path, in_scope: Callable[[Path], bool]) -> Path | None:
    folder = _project_folder(directory)
    return folder if folder is not None and in_scope(folder.resolve()) else None


def list_all_claude_conversations(
    home: Path, clock: Clock, in_scope: Callable[[Path], bool], running: set[Path]
) -> list[ProjectConversations]:
    """The conversations of every project folder `in_scope` allows, projects in name order,
    each project's conversations newest first. `running` holds the transcripts of agents that
    are running now."""
    projects = []
    for directory in sorted((home / CLAUDE_PROJECTS).iterdir()):
        folder = _in_scope_project_folder(directory, in_scope) if directory.is_dir() else None
        if folder is None:
            continue
        conversations = [
            CleanupConversation(
                **{**asdict(conversation), "size": _conversation_bytes(directory, conversation.id)},
                in_use=conversation.recently_active
                or directory / f"{conversation.id}.jsonl" in running,
            )
            for conversation in _list_directory(directory, clock)
        ]
        if conversations:
            projects.append(ProjectConversations(directory.name, folder, conversations))
    return sorted(projects, key=lambda project: project.folder.name.lower())


def delete_claude_conversation(
    home: Path,
    directory_name: str,
    conversation_id: str,
    clock: Clock,
    in_scope: Callable[[Path], bool],
    running: set[Path],
) -> int:
    """Delete a conversation for good (its transcript and the folder of results beside it);
    returns the bytes freed."""
    directory = home / CLAUDE_PROJECTS / directory_name
    transcript = directory / f"{conversation_id}.jsonl"
    if (
        Path(directory_name).name != directory_name
        or not CONVERSATION_ID.match(conversation_id)
        or not transcript.is_file()
    ):
        raise ConversationNotFoundError(conversation_id)
    if _in_scope_project_folder(directory, in_scope) is None:
        raise OutsideScopeError(directory_name)
    if transcript in running or clock() - transcript.stat().st_mtime < RECENTLY_ACTIVE_SECONDS:
        raise ConversationInUseError(conversation_id)
    results = directory / conversation_id
    freed = _conversation_bytes(directory, conversation_id)
    transcript.unlink()
    if results.is_dir():
        shutil.rmtree(results)
    return freed


@dataclass(frozen=True)
class SearchHit:
    id: str
    title: str
    modified: float
    # Where the words were found first, with some context around them.
    excerpt: str
    # How often they occur in the conversation's messages.
    matches: int


def message_texts(entry: dict[str, Any]) -> Iterator[str]:
    """What the user and Claude wrote in a transcript entry; tool calls and results are left
    out, as are commands and notices ("<...>")."""
    if entry.get("type") not in ("user", "assistant"):
        return
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        if not content.startswith("<"):
            yield content
        return
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                yield str(part.get("text", ""))


def _excerpt(text: str, start: int, length: int) -> str:
    begin = max(0, start - EXCERPT_CONTEXT_CHARS)
    end = min(len(text), start + length + EXCERPT_CONTEXT_CHARS)
    excerpt = " ".join(text[begin:end].split())
    return ("…" if begin > 0 else "") + excerpt + ("…" if end < len(text) else "")


def search_claude_conversations(home: Path, folder: Path, query: str) -> list[SearchHit]:
    """Conversations of the folder whose messages contain the query (any case), newest first."""
    directory = claude_project_dir(home, folder)
    needle = query.casefold()
    if not needle or not directory.is_dir():
        return []
    hits = []
    for path in directory.glob("*.jsonl"):
        if not CONVERSATION_ID.match(path.stem):
            continue
        matches = 0
        excerpt = ""
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                # Cheap check on the raw line first; only lines with the words are parsed.
                if needle not in line.casefold():
                    continue
                for text in message_texts(json.loads(line)):
                    folded = text.casefold()
                    found = folded.find(needle)
                    if found < 0:
                        continue
                    matches += folded.count(needle)
                    excerpt = excerpt or _excerpt(text, found, len(needle))
        if matches:
            hits.append(
                SearchHit(
                    id=path.stem,
                    title=_claude_title(path)[:TITLE_MAX_CHARS],
                    modified=path.stat().st_mtime,
                    excerpt=excerpt,
                    matches=matches,
                )
            )
    hits.sort(key=lambda hit: hit.modified, reverse=True)
    return hits[:SEARCH_RESULTS]


# Per agent profile setting "conversations.source": listing and searching.
CONVERSATION_SOURCES: dict[str, Callable[[Path, Path, Clock], list[Conversation]]] = {
    "claude": list_claude_conversations,
}
CONVERSATION_SEARCHES: dict[str, Callable[[Path, Path, str], list[SearchHit]]] = {
    "claude": search_claude_conversations,
}
