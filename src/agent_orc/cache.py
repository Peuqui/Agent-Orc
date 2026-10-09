"""When an agent's prompt cache expires, read from its transcript.

Every answer of the model is an entry with its time and its usage; `cache_creation` tells
whether the prompt went into the cache for one hour or for five minutes (Claude: 1 hour as a
rule, 5 minutes once the account is over its quota). Reading from the cache refreshes it, so
the cache expires one window after the last request. Answers that only read from the cache
write nothing, so the window comes from the newest answer that wrote to it.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_orc.history import lines_from_end

# The newest answers are near the end; a long tool result may push them back a little.
SCAN_BYTES = 4 * 1024 * 1024
WINDOW_SECONDS = {"ephemeral_1h_input_tokens": 3600, "ephemeral_5m_input_tokens": 300}


@dataclass(frozen=True)
class CacheState:
    # Unix time of the newest answer, i.e. of the last request.
    last_request: float
    window_seconds: int


# Read once per version of a transcript: the session list asks for it every few seconds.
_known: dict[Path, tuple[int, int, CacheState | None]] = {}


def cache_state(transcript: Path) -> CacheState | None:
    """None until the transcript has an answer that wrote to the cache."""
    stat = transcript.stat()
    known = _known.get(transcript)
    if known is not None and known[:2] == (stat.st_mtime_ns, stat.st_size):
        return known[2]
    state = _read_state(transcript)
    _known[transcript] = (stat.st_mtime_ns, stat.st_size, state)
    return state


def _read_state(transcript: Path) -> CacheState | None:
    last_request: float | None = None
    for line in lines_from_end(transcript, SCAN_BYTES):
        entry: dict[str, Any] = json.loads(line)
        usage = entry.get("message", {}).get("usage") if entry.get("type") == "assistant" else None
        if not usage:
            continue
        if last_request is None:
            last_request = datetime.fromisoformat(entry["timestamp"]).timestamp()
        written = usage.get("cache_creation") or {}
        window = max(
            (seconds for key, seconds in WINDOW_SECONDS.items() if written.get(key)), default=None
        )
        if window is not None:
            return CacheState(last_request=last_request, window_seconds=window)
    return None
