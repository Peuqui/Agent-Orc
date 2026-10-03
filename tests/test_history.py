import json
import os
from pathlib import Path
from typing import Any

from ai_orc.history import (
    READ_CHUNK_BYTES,
    RECENTLY_ACTIVE_SECONDS,
    claude_project_dir,
    list_claude_conversations,
)
from tests.conftest import FakeClock

FOLDER = Path("/home/u/Projekte/demo.app")
FIRST = "1b0c8f2e-0000-4000-8000-000000000001"
SECOND = "1b0c8f2e-0000-4000-8000-000000000002"


def write_conversation(
    home: Path, conversation_id: str, entries: list[dict[str, Any]], mtime: float
) -> Path:
    directory = claude_project_dir(home, FOLDER)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{conversation_id}.jsonl"
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    os.utime(path, (mtime, mtime))
    return path


def user(text: Any) -> dict[str, Any]:
    return {"type": "user", "message": {"content": text}}


def test_project_dir_replaces_everything_but_letters_and_digits(tmp_path: Path) -> None:
    assert claude_project_dir(tmp_path, Path("/tmp/a.b_c/D-1")) == (
        tmp_path / ".claude" / "projects" / "-tmp-a-b-c-D-1"
    )


def test_latest_ai_title_wins_and_newest_conversation_first(
    tmp_path: Path, clock: FakeClock
) -> None:
    old = clock.now - 3600
    write_conversation(tmp_path, FIRST, [user("Hallo"), {"type": "ai-title", "aiTitle": "Alt"},
                                         {"type": "ai-title", "aiTitle": "Neu"}], old)  # fmt: skip
    write_conversation(tmp_path, SECOND, [user("Zweites Gespräch")], old + 60)
    listed = list_claude_conversations(tmp_path, FOLDER, clock)
    assert [(c.id, c.title) for c in listed] == [(SECOND, "Zweites Gespräch"), (FIRST, "Neu")]


def test_first_plain_prompt_when_untitled(tmp_path: Path, clock: FakeClock) -> None:
    entries = [
        user("<command-name>/clear</command-name>"),
        user([{"type": "tool_result", "content": "x"}]),
        user("Baue mir einen Lander\nmit zweiter Zeile"),
    ]
    write_conversation(tmp_path, FIRST, entries, clock.now - 3600)
    assert list_claude_conversations(tmp_path, FOLDER, clock)[0].title == "Baue mir einen Lander"


def test_title_found_behind_a_line_larger_than_the_read_chunk(
    tmp_path: Path, clock: FakeClock
) -> None:
    entries = [{"type": "ai-title", "aiTitle": "Titel"}, user("x" * (READ_CHUNK_BYTES * 2))]
    write_conversation(tmp_path, FIRST, entries, clock.now - 3600)
    assert list_claude_conversations(tmp_path, FOLDER, clock)[0].title == "Titel"


def test_recently_written_conversation_is_marked(tmp_path: Path, clock: FakeClock) -> None:
    write_conversation(tmp_path, FIRST, [user("a")], clock.now - RECENTLY_ACTIVE_SECONDS / 2)
    write_conversation(tmp_path, SECOND, [user("b")], clock.now - RECENTLY_ACTIVE_SECONDS * 2)
    active = {c.id: c.recently_active for c in list_claude_conversations(tmp_path, FOLDER, clock)}
    assert active == {FIRST: True, SECOND: False}


def test_only_conversation_files_are_listed(tmp_path: Path, clock: FakeClock) -> None:
    write_conversation(tmp_path, FIRST, [user("a")], clock.now - 3600)
    directory = claude_project_dir(tmp_path, FOLDER)
    (directory / "notes.jsonl").write_text("{}\n")
    (directory / FIRST).mkdir()  # Claude's per-conversation side folder
    assert [c.id for c in list_claude_conversations(tmp_path, FOLDER, clock)] == [FIRST]


def test_folder_without_conversations(tmp_path: Path, clock: FakeClock) -> None:
    assert list_claude_conversations(tmp_path, FOLDER, clock) == []
