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
    {"type": "attachment", "uuid": "x7", "attachment": {"type": "hook_success"}},
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


def queue(operation: str, uuid: str, content: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": "queue-operation",
        "operation": operation,
        "timestamp": f"2026-10-06T10:00:{uuid[1:].zfill(2)}.000Z",
    }
    if content is not None:
        record["content"] = content
    return record


def delivered(uuid: str, prompt: str | list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "attachment",
        "uuid": uuid,
        "timestamp": f"2026-10-06T10:00:{uuid[1:].zfill(2)}.000Z",
        "attachment": {"type": "queued_command", "prompt": prompt, "origin": {"kind": "human"}},
    }


def test_what_the_user_types_during_an_answer_is_shown_with_it(tmp_path: Path) -> None:
    entries = [
        entry("user", "u1", "Frage"),
        entry("assistant", "a2", [{"type": "text", "text": "Ich arbeite."}]),
        queue("enqueue", "q3", "Noch ein Einwand"),
        queue("remove", "q4", "Noch ein Einwand"),
        delivered("d5", "Noch ein Einwand"),
        entry("assistant", "a6", [{"type": "text", "text": "Verstanden."}]),
        # Typed while the agent works, taken as a request of its own afterwards.
        queue("enqueue", "q7", "Nächste Frage"),
        queue("dequeue", "q8"),
        entry("user", "u9", "Nächste Frage"),
        entry("assistant", "a10", [{"type": "text", "text": "Antwort."}]),
    ]
    turns = read_turns(write(tmp_path / "t.jsonl", entries), limit=10)
    assert [turn.prompt for turn in turns] == ["Frage", "Nächste Frage"]
    first = turns[0].interjections
    assert [(i.text, i.pending) for i in first] == [("Noch ein Einwand", False)]
    # The attachment carries the time the message was typed.
    assert first[0].time == "2026-10-06T10:00:05.000Z"
    # The request taken as its own turn is not also an interjection.
    assert turns[1].interjections == []


def test_what_is_typed_but_not_yet_taken_shows_as_waiting(tmp_path: Path) -> None:
    entries = [
        entry("user", "u1", "Frage"),
        entry("assistant", "a2", [{"type": "text", "text": "Ich arbeite."}]),
        queue("enqueue", "q3", "Noch nicht angekommen"),
    ]
    turns = read_turns(write(tmp_path / "t.jsonl", entries), limit=10)
    waiting = [(i.text, i.pending) for i in turns[0].interjections]
    assert waiting == [("Noch nicht angekommen", True)]


def test_a_withdrawn_message_is_not_shown(tmp_path: Path) -> None:
    entries = [
        entry("user", "u1", "Frage"),
        queue("enqueue", "q2", "Zurückgenommen"),
        queue("remove", "q3", "Zurückgenommen"),
    ]
    turns = read_turns(write(tmp_path / "t.jsonl", entries), limit=10)
    assert turns[0].interjections == []


def test_a_message_with_a_picture_and_notices_of_the_system(tmp_path: Path) -> None:
    picture = {"type": "image", "source": {"type": "base64", "data": "AAAA"}}
    entries = [
        entry("user", "u1", [{"type": "text", "text": "Schau mal"}, picture]),
        # Typed with only a picture: no text in the queue operations, a list in the attachment.
        queue("enqueue", "q2"),
        queue("remove", "q3"),
        delivered("d4", [picture]),
        # What the system hands to the agent is not what the user typed.
        {
            "type": "attachment",
            "uuid": "d5",
            "timestamp": "2026-10-06T10:00:05.000Z",
            "attachment": {
                "type": "queued_command",
                "prompt": "<task-notification>",
                "origin": {"kind": "task-notification"},
            },
        },
    ]
    turns = read_turns(write(tmp_path / "t.jsonl", entries), limit=10)
    assert (turns[0].prompt, turns[0].images) == ("Schau mal", 1)
    assert [(i.text, i.images) for i in turns[0].interjections] == [("", 1)]
