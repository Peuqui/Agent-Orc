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


@dataclass
class AnswerText:
    id: str
    # ISO time as Claude writes it (UTC).
    time: str
    text: str


@dataclass
class Turn:
    """One request of the user and what the agent wrote in answer."""

    id: str
    time: str
    prompt: str
    texts: list[AnswerText] = field(default_factory=list)


def _entry_text(entry: dict[str, Any]) -> str:
    return "\n\n".join(message_texts(entry)).strip()


def read_turns(transcript: Path, limit: int) -> list[Turn]:
    """The last `limit` requests with their texts, oldest first. A request that is still being
    answered is included with what the agent has written so far."""
    entries: list[dict[str, Any]] = []
    prompts = 0
    for line in lines_from_end(transcript, SCAN_BYTES):
        entry: dict[str, Any] = json.loads(line)
        # What subagents write is not the agent's own answer.
        if entry.get("isSidechain") or entry.get("type") not in ("user", "assistant"):
            continue
        entries.append(entry)
        if entry["type"] == "user" and _entry_text(entry):
            prompts += 1
            if prompts == limit:
                break
    turns: list[Turn] = []
    for entry in reversed(entries):
        text = _entry_text(entry)
        if not text:
            continue
        if entry["type"] == "user":
            turns.append(Turn(id=entry["uuid"], time=entry["timestamp"], prompt=text))
        elif turns:
            turns[-1].texts.append(AnswerText(id=entry["uuid"], time=entry["timestamp"], text=text))
    return turns
