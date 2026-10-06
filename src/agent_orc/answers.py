"""What an agent answered, from Claude Code's transcript: per request of the user the texts it
wrote, without its thoughts, tool calls and their results.

The last text of a request is its summary, the ones before are comments between its steps. The
transcript is read from its end, so a long conversation costs no more than the turns shown.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_orc.history import lines_from_end, message_texts

# Read at most this much of the transcript's end per call (tool results can be large).
SCAN_BYTES = 32 * 1024 * 1024
# The transcript entries that matter here; the user's typing ahead is in the queue operations.
KEPT_TYPES = ("user", "assistant", "queue-operation", "attachment")


@dataclass
class AnswerText:
    id: str
    # ISO time as Claude writes it (UTC).
    time: str
    text: str


@dataclass
class Interjection:
    """What the user typed while the agent was answering."""

    id: str
    # When it was typed.
    time: str
    text: str
    # Not yet delivered to the agent (it takes it at its next step).
    pending: bool


@dataclass
class Turn:
    """One request of the user and what the agent wrote in answer."""

    id: str
    time: str
    prompt: str
    texts: list[AnswerText] = field(default_factory=list)
    interjections: list[Interjection] = field(default_factory=list)


def _entry_text(entry: dict[str, Any]) -> str:
    return "\n\n".join(message_texts(entry)).strip()


def _is_human_message(entry: dict[str, Any]) -> bool:
    return entry["type"] == "user" and bool(_entry_text(entry))


def read_turns(transcript: Path, limit: int) -> list[Turn]:
    """The last `limit` requests with their texts, oldest first. A request that is still being
    answered is included with what the agent has written so far."""
    entries: list[dict[str, Any]] = []
    prompts = 0
    for line in lines_from_end(transcript, SCAN_BYTES):
        entry: dict[str, Any] = json.loads(line)
        # What subagents write is not the agent's own answer.
        if entry.get("isSidechain") or entry.get("type") not in KEPT_TYPES:
            continue
        entries.append(entry)
        if _is_human_message(entry):
            prompts += 1
            if prompts == limit:
                break
    entries.reverse()
    delivered = {
        entry["attachment"].get("prompt")
        for entry in entries
        if entry["type"] == "attachment" and entry["attachment"].get("type") == "queued_command"
    }
    turns: list[Turn] = []
    # Typed while the agent works, not yet taken: the oldest is taken first.
    waiting: list[dict[str, Any]] = []
    for entry in entries:
        if entry["type"] == "queue-operation":
            _queue_operation(entry, waiting, delivered, turns)
        elif entry["type"] == "attachment":
            continue
        elif _is_human_message(entry):
            turns.append(Turn(id=entry["uuid"], time=entry["timestamp"], prompt=_entry_text(entry)))
        elif turns and _entry_text(entry):
            text = AnswerText(id=entry["uuid"], time=entry["timestamp"], text=_entry_text(entry))
            turns[-1].texts.append(text)
    if turns:
        turns[-1].interjections.extend(_interjection(entry, pending=True) for entry in waiting)
    return turns


def _interjection(entry: dict[str, Any], pending: bool) -> Interjection:
    time = entry["timestamp"]
    return Interjection(id=f"queued-{time}", time=time, text=entry["content"], pending=pending)


def _queue_operation(
    entry: dict[str, Any], waiting: list[dict[str, Any]], delivered: set[Any], turns: list[Turn]
) -> None:
    """Claude queues what the user types while it works: "enqueue" when typed, then either
    "dequeue" (it becomes a request of its own, the next user entry) or "remove" (it is handed to
    the running answer, as a "queued_command" attachment)."""
    operation = entry.get("operation")
    if operation == "enqueue" and entry.get("content"):
        waiting.append(entry)
    elif operation == "dequeue" and waiting:
        waiting.pop(0)
    elif operation == "remove":
        taken = next((e for e in waiting if e["content"] == entry.get("content")), None)
        if taken is not None:
            waiting.remove(taken)
            if turns and taken["content"] in delivered:
                turns[-1].interjections.append(_interjection(taken, pending=False))
