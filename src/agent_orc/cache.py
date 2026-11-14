"""When an agent's prompt cache expires, read from its transcript.

Every answer of the model is an entry with its time and its usage; `cache_creation` tells
whether the prompt went into the cache for one hour or for five minutes (Claude: 1 hour as a
rule, 5 minutes once the account is over its quota). Reading from the cache refreshes it, so
the cache expires one window after the last request. Answers that only read from the cache
write nothing, so the window comes from the newest answer that wrote to it.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from agent_orc.history import lines_from_end, transcript_entry

# The newest answers are near the end; a long tool result may push them back a little.
SCAN_BYTES = 4 * 1024 * 1024
WINDOW_SECONDS = {"ephemeral_1h_input_tokens": 3600, "ephemeral_5m_input_tokens": 300}


@dataclass(frozen=True)
class CacheState:
    # Unix time of the newest answer, i.e. of the last request.
    last_request: float
    window_seconds: int
    # What runs out at the end of the window: the prompt cache (read from the transcript), or a
    # local model that its server unloads. The page words its texts by it.
    kind: Literal["prompt_cache", "model"] = "prompt_cache"


@dataclass(frozen=True)
class Reading:
    """What one pass through a transcript finds."""

    # Unix time of the newest answer, whether or not it wrote to the cache; None without answers.
    last_answer: float | None
    # None until an answer wrote to the cache.
    state: CacheState | None


# Read once per version of a transcript: the session list asks for it every few seconds.
_known: dict[Path, tuple[int, int, Reading]] = {}


def cache_state(transcript: Path) -> CacheState | None:
    """None until the transcript has an answer that wrote to the cache."""
    return _reading(transcript).state


def last_answer(transcript: Path) -> float | None:
    """Unix time of the newest answer; None without one. For models whose server keeps no cache
    the transcript tells of (a local model stays loaded for a while after its last request)."""
    return _reading(transcript).last_answer


def _reading(transcript: Path) -> Reading:
    stat = transcript.stat()
    known = _known.get(transcript)
    if known is not None and known[:2] == (stat.st_mtime_ns, stat.st_size):
        return known[2]
    reading = _read(transcript)
    _known[transcript] = (stat.st_mtime_ns, stat.st_size, reading)
    return reading


def _read(transcript: Path) -> Reading:
    last_request: float | None = None
    for line in lines_from_end(transcript, SCAN_BYTES):
        entry = transcript_entry(line, transcript)
        if entry is None:
            continue
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
            return Reading(last_request, CacheState(last_request, window))
    return Reading(last_request, None)
