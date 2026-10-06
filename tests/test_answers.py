import json
from pathlib import Path
from typing import Any

from agent_orc.answers import read_turns


def entry(kind: str, uuid: str, content: Any, **extra: Any) -> dict[str, Any]:
    return {
        "type": kind,
        "uuid": uuid,
        "timestamp": f"2026-10-06T10:00:{uuid[1:].zfill(2)}.000Z",
        "message": {"content": content},
        **extra,
    }


def write(path: Path, entries: list[dict[str, Any]]) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return path


TRANSCRIPT = [
    entry("user", "u1", "Erste Frage"),
    entry("assistant", "a2", [{"type": "thinking", "thinking": "überlege"}]),
    entry("assistant", "a3", [{"type": "text", "text": "Ich schaue nach."}]),
    entry("assistant", "a4", [{"type": "tool_use", "name": "Bash", "input": {}}]),
    entry("user", "u5", [{"type": "tool_result", "content": "ls-Ausgabe"}]),
    entry("assistant", "a6", [{"type": "text", "text": "Fertig, es sind drei Dateien."}]),
    {"type": "attachment", "uuid": "x7"},
    entry("user", "u8", "<command-name>/clear</command-name>"),
    entry("user", "u9", "Zweite Frage"),
    entry("assistant", "a10", [{"type": "text", "text": "Unteragent"}], isSidechain=True),
    entry("assistant", "a11", [{"type": "text", "text": "Antwort zur zweiten Frage."}]),
]


def test_turns_hold_the_texts_of_the_agent_without_thoughts_and_tools(tmp_path: Path) -> None:
    turns = read_turns(write(tmp_path / "t.jsonl", TRANSCRIPT), limit=10)
    assert [turn.prompt for turn in turns] == ["Erste Frage", "Zweite Frage"]
    assert [t.text for t in turns[0].texts] == ["Ich schaue nach.", "Fertig, es sind drei Dateien."]
    # What a subagent wrote and notices ("<...>") are not the agent's answer.
    assert [t.text for t in turns[1].texts] == ["Antwort zur zweiten Frage."]
    assert turns[0].id == "u1" and turns[0].texts[0].id == "a3"


def test_only_the_last_requests_are_read(tmp_path: Path) -> None:
    turns = read_turns(write(tmp_path / "t.jsonl", TRANSCRIPT), limit=1)
    assert [turn.prompt for turn in turns] == ["Zweite Frage"]


def test_a_request_still_being_answered_shows_what_is_written_so_far(tmp_path: Path) -> None:
    started = TRANSCRIPT[:3]
    turns = read_turns(write(tmp_path / "t.jsonl", started), limit=5)
    assert [t.text for t in turns[0].texts] == ["Ich schaue nach."]
    assert read_turns(write(tmp_path / "e.jsonl", TRANSCRIPT[:1]), limit=5)[0].texts == []
