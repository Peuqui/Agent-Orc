"""A record of what was said to the agents on the Echo Dot, as the recognition heard it and what
Agent-Orc made of it: to compare with what was meant, and to show a spoken request in the
agent's answers."""

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_orc.state import state_dir


@dataclass(frozen=True)
class VoiceEntry:
    id: str
    time: str
    room: str
    # The words as recognised.
    heard: str
    # What Agent-Orc did with them (voice.Action's value).
    action: str
    agent_id: str | None
    agent: str | None
    # The text for the agent, without its name.
    request: str
    # How well the spoken name matched; None when none was spoken.
    score: float | None
    # For a yes: the entry of the sentence it confirms.
    source: str | None


def _log_file() -> Path:
    return state_dir() / "voice-log.jsonl"


def _recordings_dir() -> Path:
    return state_dir() / "voice-recordings"


def store_recording(entry_id: str, recording: bytes) -> None:
    """The WAV of what was said, next to the entry (same id)."""
    _recordings_dir().mkdir(parents=True, exist_ok=True)
    (_recordings_dir() / f"{entry_id}.wav").write_bytes(recording)


def recording_file(entry_id: str) -> Path:
    """Only an entry's id names a recording: nothing else reaches the folder's other files."""
    if re.fullmatch(r"[0-9a-f]{32}", entry_id) is None:
        raise FileNotFoundError(entry_id)
    path = _recordings_dir() / f"{entry_id}.wav"
    if not path.is_file():
        raise FileNotFoundError(entry_id)
    return path


def new_entry(now: float, **fields: Any) -> VoiceEntry:
    time = datetime.fromtimestamp(now, UTC).isoformat()
    return VoiceEntry(id=uuid.uuid4().hex, time=time, **fields)


def append_entry(entry: VoiceEntry) -> None:
    path = _log_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def read_entries() -> list[dict[str, Any]]:
    path = _log_file()
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def requests_to_agent(agent_id: str) -> list[dict[str, Any]]:
    """What was spoken to this agent and sent on, oldest first: the confirmed request, with the
    sentence it was said in (its words as recognised and how its name matched)."""
    entries = read_entries()
    by_id = {entry["id"]: entry for entry in entries}
    requests = []
    for entry in entries:
        if entry["action"] != "sent" or entry["agent_id"] != agent_id:
            continue
        spoken = by_id.get(entry["source"] or "", entry)
        requests.append(
            {
                "id": spoken["id"],
                "time": entry["time"],
                "request": entry["request"],
                "heard": spoken["heard"],
                "score": spoken["score"],
            }
        )
    return requests
