import json
import os
from pathlib import Path
from typing import Any

import pytest

from agent_orc.history import (
    READ_CHUNK_BYTES,
    RECENTLY_ACTIVE_SECONDS,
    ConversationInUseError,
    ConversationNotFoundError,
    claude_project_dir,
    delete_claude_conversation,
    list_all_claude_conversations,
    list_claude_conversations,
    search_claude_conversations,
)
from agent_orc.scope import OutsideScopeError
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
    # As Claude Code writes them: UTF-8, not \u escapes.
    path.write_text("".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries))
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


def assistant(text: str) -> dict[str, Any]:
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def test_search_finds_words_in_messages_with_an_excerpt(tmp_path: Path) -> None:
    write_conversation(
        tmp_path,
        FIRST,
        [
            user("Bau eine kleine Glühbirne in die Kopfzeile"),
            assistant("Die GLÜHBIRNE sitzt rechts."),
        ],
        mtime=1000,
    )
    write_conversation(tmp_path, SECOND, [user("Etwas anderes")], mtime=2000)
    [hit] = search_claude_conversations(tmp_path, FOLDER, "glühbirne")
    assert (hit.id, hit.matches) == (FIRST, 2)
    assert "Glühbirne" in hit.excerpt


def test_search_leaves_out_tool_output_and_commands(tmp_path: Path) -> None:
    tool_result = {
        "type": "user",
        "message": {"content": [{"type": "tool_result", "content": "secret-word in a log"}]},
    }
    write_conversation(
        tmp_path, FIRST, [tool_result, user("<command-name>secret-word</command-name>")], mtime=1000
    )
    assert search_claude_conversations(tmp_path, FOLDER, "secret-word") == []


def test_search_newest_first_and_long_texts_cut_around_the_hit(tmp_path: Path) -> None:
    long_text = "a " * 200 + "needle" + " b" * 200
    write_conversation(tmp_path, FIRST, [user(long_text)], mtime=1000)
    write_conversation(tmp_path, SECOND, [assistant("needle")], mtime=2000)
    hits = search_claude_conversations(tmp_path, FOLDER, "needle")
    assert [hit.id for hit in hits] == [SECOND, FIRST]
    assert hits[1].excerpt.startswith("…") and hits[1].excerpt.endswith("…")
    assert len(hits[1].excerpt) < len(long_text)


PROJECTS = Path("/home/u/Projekte")
OTHER = Path("/home/u/other")
THIRD = "1b0c8f2e-0000-4000-8000-000000000003"


def in_projects(path: Path) -> bool:
    return path.is_relative_to(PROJECTS)


def write_in(
    home: Path, folder: Path, conversation_id: str, mtime: float, results: bool = False
) -> Path:
    """A conversation that ran in `folder`; its entries name the folder as Claude Code does."""
    directory = claude_project_dir(home, folder)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{conversation_id}.jsonl"
    path.write_text(json.dumps({"type": "user", "cwd": str(folder), "message": {"content": "Hi"}}))
    os.utime(path, (mtime, mtime))
    if results:
        (directory / conversation_id).mkdir()
        (directory / conversation_id / "tool-result.txt").write_text("x" * 1000)
    return path


def test_cleanup_lists_the_projects_in_scope_by_name_with_their_conversations(
    tmp_path: Path, clock: FakeClock
) -> None:
    old = clock.now - 86400
    write_in(tmp_path, PROJECTS / "zeta", FIRST, old)
    write_in(tmp_path, PROJECTS / "Alpha", FIRST, old)
    write_in(tmp_path, PROJECTS / "Alpha", SECOND, old + 60)
    write_in(tmp_path, OTHER, FIRST, old)
    listed = list_all_claude_conversations(tmp_path, clock, in_projects, set())
    assert [(p.folder, [c.id for c in p.conversations]) for p in listed] == [
        (PROJECTS / "Alpha", [SECOND, FIRST]),
        (PROJECTS / "zeta", [FIRST]),
    ]
    # Widened scope (the safety switch) shows the other folder too.
    everywhere = list_all_claude_conversations(tmp_path, clock, lambda _: True, set())
    assert {p.folder for p in everywhere} == {PROJECTS / "Alpha", PROJECTS / "zeta", OTHER}


def test_cleanup_marks_conversations_in_use(tmp_path: Path, clock: FakeClock) -> None:
    old = clock.now - 86400
    running = write_in(tmp_path, PROJECTS / "a", FIRST, old)
    write_in(tmp_path, PROJECTS / "a", SECOND, clock.now - 5)
    write_in(tmp_path, PROJECTS / "a", THIRD, old)
    [project] = list_all_claude_conversations(tmp_path, clock, in_projects, {running})
    assert {c.id: c.in_use for c in project.conversations} == {
        FIRST: True, SECOND: True, THIRD: False,
    }  # fmt: skip


def test_deleting_a_conversation_removes_transcript_and_results_and_reports_the_size(
    tmp_path: Path, clock: FakeClock
) -> None:
    transcript = write_in(tmp_path, PROJECTS / "a", FIRST, clock.now - 86400, results=True)
    other = write_in(tmp_path, PROJECTS / "a", SECOND, clock.now - 86400)
    memory = transcript.parent / "memory"
    memory.mkdir()
    directory = transcript.parent.name
    size = transcript.stat().st_size
    freed = delete_claude_conversation(tmp_path, directory, FIRST, clock, in_projects, set())
    assert freed == size + 1000
    assert not transcript.exists() and not (transcript.parent / FIRST).exists()
    # The project's other conversations and its memory stay.
    assert other.exists() and memory.is_dir()


def test_deleting_refuses_what_is_in_use_outside_the_scope_or_not_a_conversation(
    tmp_path: Path, clock: FakeClock
) -> None:
    running = write_in(tmp_path, PROJECTS / "a", FIRST, clock.now - 86400)
    recent = write_in(tmp_path, PROJECTS / "a", SECOND, clock.now - 5)
    outside = write_in(tmp_path, OTHER, FIRST, clock.now - 86400)
    directory = running.parent.name

    def delete(name: str, conversation_id: str, running_now: set[Path]) -> int:
        return delete_claude_conversation(
            tmp_path, name, conversation_id, clock, in_projects, running_now
        )

    with pytest.raises(ConversationInUseError):
        delete(directory, FIRST, {running})
    with pytest.raises(ConversationInUseError):
        delete(directory, SECOND, set())
    with pytest.raises(OutsideScopeError):
        delete(outside.parent.name, FIRST, set())
    for name, conversation_id in [(directory, THIRD), ("..", FIRST), (directory, "../x")]:
        with pytest.raises(ConversationNotFoundError):
            delete(name, conversation_id, set())
    assert running.exists() and recent.exists() and outside.exists()


def test_cleanup_size_counts_the_results_folder_beside_the_transcript(
    tmp_path: Path, clock: FakeClock
) -> None:
    transcript = write_in(tmp_path, PROJECTS / "a", FIRST, clock.now - 86400, results=True)
    [project] = list_all_claude_conversations(tmp_path, clock, in_projects, set())
    assert project.conversations[0].size == transcript.stat().st_size + 1000
