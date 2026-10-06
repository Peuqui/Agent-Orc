"""What an agent answered, from Claude Code's transcript: per request of the user the texts it
wrote, without its thoughts, tool calls and their results.

The last text of a request is its summary, the ones before are comments between its steps. The
transcript is read from its end, so a long conversation costs no more than the turns shown.
"""

import base64
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
    # Pictures that came with it (their content is not shown).
    images: int
    # Not yet delivered to the agent (it takes it at its next step).
    pending: bool


@dataclass
class Turn:
    """One request of the user and what the agent wrote in answer."""

    id: str
    time: str
    prompt: str
    images: int
    texts: list[AnswerText] = field(default_factory=list)
    interjections: list[Interjection] = field(default_factory=list)


def _entry_text(entry: dict[str, Any]) -> str:
    return "\n\n".join(message_texts(entry)).strip()


def _prompt_parts(prompt: str | list[dict[str, Any]]) -> tuple[str, int]:
    """The text of a prompt and how many pictures came with it: Claude writes a prompt with
    pictures as a list of content blocks."""
    if isinstance(prompt, str):
        return prompt.strip(), 0
    texts = [str(block.get("text", "")) for block in prompt if block.get("type") == "text"]
    return "\n\n".join(texts).strip(), sum(block.get("type") == "image" for block in prompt)


def _is_human_message(entry: dict[str, Any]) -> bool:
    if entry["type"] != "user":
        return False
    content = entry["message"]["content"]
    return bool(_entry_text(entry)) or (isinstance(content, list) and _prompt_parts(content)[1] > 0)


def _handed_over(entry: dict[str, Any]) -> Interjection | None:
    """What the user typed during the answer and the agent has taken: an attachment of the next
    step, written with the time it was typed."""
    attachment = entry["attachment"]
    typed_by_user = attachment.get("origin", {}).get("kind") == "human"
    if attachment.get("type") != "queued_command" or not typed_by_user:
        return None
    text, images = _prompt_parts(attachment["prompt"])
    return Interjection(entry["uuid"], entry["timestamp"], text, images, pending=False)


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
    turns: list[Turn] = []
    # Typed during an answer and not yet taken, in the order typed (a message with pictures has
    # no text here, it only holds the place).
    waiting: list[dict[str, Any]] = []
    for entry in entries:
        if entry["type"] == "queue-operation":
            _queue_operation(entry, waiting)
        elif entry["type"] == "attachment":
            handed = _handed_over(entry)
            if handed is not None and turns:
                turns[-1].interjections.append(handed)
        elif _is_human_message(entry):
            content = entry["message"]["content"]
            images = _prompt_parts(content)[1] if isinstance(content, list) else 0
            turns.append(Turn(entry["uuid"], entry["timestamp"], _entry_text(entry), images))
        elif turns and _entry_text(entry):
            text = AnswerText(id=entry["uuid"], time=entry["timestamp"], text=_entry_text(entry))
            turns[-1].texts.append(text)
    if turns:
        for entry in waiting:
            if entry.get("content"):
                time = entry["timestamp"]
                turns[-1].interjections.append(
                    Interjection(f"queued-{time}", time, entry["content"], 0, pending=True)
                )
    return turns


def _queue_operation(entry: dict[str, Any], waiting: list[dict[str, Any]]) -> None:
    """Claude queues what the user types while it works: "enqueue" when typed, then either
    "dequeue" (it becomes a request of its own, the next user entry) or "remove" (it is handed to
    the running answer, as an attachment of its next step)."""
    operation = entry.get("operation")
    if operation == "enqueue":
        waiting.append(entry)
    elif operation == "dequeue" and waiting:
        waiting.pop(0)
    elif operation == "remove":
        taken = next((e for e in waiting if e.get("content") == entry.get("content")), None)
        if taken is not None:
            waiting.remove(taken)


# Pictures shown in the answers; anything else in a transcript is not served.
IMAGE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")


def _image_blocks(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """The pictures of a request or of what was typed during an answer, in the order they came."""
    attachment = entry["type"] == "attachment"
    content = entry["attachment"]["prompt"] if attachment else entry["message"]["content"]
    if not isinstance(content, list):
        return []
    return [block for block in content if block.get("type") == "image"]


def read_image(transcript: Path, entry_id: str, index: int) -> tuple[bytes, str]:
    """The picture `index` (counted from 0) of the entry with this id, and its media type."""
    for line in lines_from_end(transcript, SCAN_BYTES):
        # Cheap check on the raw line first; the picture's data makes lines large.
        if entry_id not in line:
            continue
        entry: dict[str, Any] = json.loads(line)
        if entry.get("uuid") != entry_id or entry.get("type") not in ("user", "attachment"):
            continue
        blocks = _image_blocks(entry)
        if index >= len(blocks):
            break
        source = blocks[index]["source"]
        if source["media_type"] not in IMAGE_TYPES:
            break
        return base64.b64decode(source["data"]), source["media_type"]
    raise FileNotFoundError(f"{entry_id}/{index}")
