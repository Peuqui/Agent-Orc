import base64
import json
from pathlib import Path
from typing import Any

import pytest

from agent_orc.answers import interrupted_at, read_image, read_turns, request_queued


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


def test_the_summary_of_a_compaction_is_no_request(tmp_path: Path) -> None:
    summary = "This session is being continued from a previous conversation ..."
    compacted = [*TRANSCRIPT, entry("user", "u12", summary, isCompactSummary=True)]
    turns = read_turns(write(tmp_path / "t.jsonl", compacted), limit=10)
    assert [turn.prompt for turn in turns] == ["Erste Frage", "Zweite Frage"]
    assert [t.text for t in turns[1].texts] == ["Antwort zur zweiten Frage."]


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


def test_a_request_queued_during_the_answer_is_found(tmp_path: Path) -> None:
    answer = [
        queue("enqueue", "q1", "Frage"),
        queue("dequeue", "q2"),
        entry("user", "u3", "Frage", origin={"kind": "human"}),
        entry("assistant", "a4", [{"type": "text", "text": "Ich arbeite."}]),
    ]
    assert not request_queued(write(tmp_path / "a.jsonl", answer))
    # Handed to the running answer: nothing waits.
    handed = [*answer, queue("enqueue", "q5", "Einwand"), queue("remove", "q6", "Einwand")]
    assert not request_queued(write(tmp_path / "h.jsonl", handed))
    # Typed and not yet taken: the next request waits.
    typed = [*answer, queue("enqueue", "q5", "Nächste Frage")]
    assert request_queued(write(tmp_path / "t.jsonl", typed))


def test_only_the_queue_since_the_answer_began_counts(tmp_path: Path) -> None:
    # Left over from an earlier conversation that ended before taking it.
    left_over = queue("enqueue", "q1", "Vergessen")
    sent_while_resting = [left_over, entry("user", "u2", "Frage", origin={"kind": "human"})]
    assert not request_queued(write(tmp_path / "r.jsonl", sent_while_resting))
    taken_from_queue = [left_over, queue("enqueue", "q2", "Frage"), queue("dequeue", "q3")]
    assert not request_queued(write(tmp_path / "q.jsonl", taken_from_queue))
    # Tool results and subagents start no request.
    working = [
        *sent_while_resting,
        entry("user", "u3", [{"type": "tool_result", "content": "ok"}]),
        entry("user", "u4", "Auftrag", isSidechain=True, origin={"kind": "human"}),
        queue("enqueue", "q5", "Nächste Frage"),
    ]
    assert request_queued(write(tmp_path / "w.jsonl", working))


def test_what_was_queued_as_the_answer_began_counts_though_written_before(tmp_path: Path) -> None:
    # Claude writes a notification queued while it takes a request before that request.
    entries = [
        queue("enqueue", "q1", "Nachricht eines Peers"),
        queue("dequeue", "q2"),
        queue("enqueue", "q4", "<task-notification>"),
        entry("user", "u3", "Nachricht eines Peers", origin={"kind": "peer"}),
        entry("assistant", "a5", [{"type": "text", "text": "Gelesen."}]),
    ]
    assert request_queued(write(tmp_path / "t.jsonl", entries))


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


def test_a_picture_of_a_request_or_of_a_message_typed_during_an_answer_is_read(
    tmp_path: Path,
) -> None:
    def block(data: bytes, media_type: str = "image/png") -> dict[str, Any]:
        encoded = base64.b64encode(data).decode()
        source = {"type": "base64", "media_type": media_type, "data": encoded}
        return {"type": "image", "source": source}

    entries = [
        entry("user", "u1", [{"type": "text", "text": "Schau"}, block(b"one"), block(b"two")]),
        delivered("d2", [block(b"typed")]),
        entry("user", "u3", [{"type": "text", "text": "Skript"}, block(b"<s/>", "image/svg+xml")]),
    ]
    transcript = write(tmp_path / "t.jsonl", entries)
    assert read_image(transcript, "u1", 0) == (b"one", "image/png")
    assert read_image(transcript, "u1", 1) == (b"two", "image/png")
    assert read_image(transcript, "d2", 0) == (b"typed", "image/png")
    # Only pictures a browser shows safely are served, and only ones that exist.
    for missing in (("u1", 2), ("u3", 0), ("nope", 0)):
        with pytest.raises(FileNotFoundError):
            read_image(transcript, *missing)


def test_the_marks_around_pasted_text_are_not_shown(tmp_path: Path) -> None:
    pasted = '\n\n<pasted_content id="4b3d">\nEingefügt\n</pasted_content id="4b3d">\n'
    entries = [
        entry("user", "u1", pasted),
        entry("assistant", "a2", [{"type": "text", "text": "Ich erkläre <pasted_content> hier."}]),
        queue("enqueue", "q3", pasted),
        delivered("d4", pasted),
    ]
    turn = read_turns(write(tmp_path / "t.jsonl", entries), limit=10)[0]
    assert turn.prompt == "Eingefügt"
    # An answer that speaks about the marks keeps its words.
    assert turn.texts[0].text == "Ich erkläre <pasted_content> hier."
    assert [i.text for i in turn.interjections] == ["Eingefügt", "Eingefügt"]


def test_a_stop_by_the_user_is_found_at_the_end_of_the_conversation(tmp_path: Path) -> None:
    stopped = [
        entry("user", "u1", "Frage"),
        entry("assistant", "a2", [{"type": "tool_use", "name": "Bash", "input": {}}]),
        entry(
            "user", "u3", [{"type": "text", "text": "[Request interrupted by user for tool use]"}]
        ),
        # A subagent's entry and Claude's own bookkeeping come after it and do not count.
        entry("assistant", "a4", [{"type": "text", "text": "Unteragent"}], isSidechain=True),
        {"type": "file-history-snapshot", "uuid": "x5"},
    ]
    assert interrupted_at(write(tmp_path / "s.jsonl", stopped)) == "2026-10-06T10:00:03.000Z"
    # Asked again after the stop: the newest entry is the new request.
    asked_again = [*stopped, entry("user", "u6", "Neue Frage")]
    assert interrupted_at(write(tmp_path / "a.jsonl", asked_again)) is None
    assert interrupted_at(write(tmp_path / "t.jsonl", TRANSCRIPT)) is None
