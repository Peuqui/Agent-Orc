import json
from datetime import UTC, datetime
from pathlib import Path

from agent_orc.cache import CacheState, cache_state

ONE_HOUR = {"ephemeral_1h_input_tokens": 724, "ephemeral_5m_input_tokens": 0}
FIVE_MINUTES = {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 300}
NOTHING_WRITTEN = {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0}


def answer(at: float, written: dict[str, int]) -> dict[str, object]:
    stamp = datetime.fromtimestamp(at, UTC).isoformat().replace("+00:00", "Z")
    usage = {"cache_creation": written, "cache_read_input_tokens": 1000}
    return {"type": "assistant", "timestamp": stamp, "message": {"usage": usage}}


def write(path: Path, entries: list[dict[str, object]]) -> Path:
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    return path


def test_expires_one_window_after_the_last_request(tmp_path: Path) -> None:
    entries = [
        answer(1000.0, ONE_HOUR),
        {"type": "user", "message": {"content": "next"}},
        # Only read from the cache (refreshing it): the window comes from the answer before.
        answer(1500.0, NOTHING_WRITTEN),
    ]
    transcript = write(tmp_path / "a.jsonl", entries)
    assert cache_state(transcript) == CacheState(last_request=1500.0, window_seconds=3600)


def test_five_minutes_once_over_quota(tmp_path: Path) -> None:
    transcript = write(
        tmp_path / "a.jsonl", [answer(1000.0, ONE_HOUR), answer(2000.0, FIVE_MINUTES)]
    )
    assert cache_state(transcript) == CacheState(last_request=2000.0, window_seconds=300)


def test_nothing_before_the_first_answer(tmp_path: Path) -> None:
    transcript = write(tmp_path / "a.jsonl", [{"type": "user", "message": {"content": "hi"}}])
    assert cache_state(transcript) is None


def test_a_changed_transcript_is_read_again(tmp_path: Path) -> None:
    transcript = write(tmp_path / "a.jsonl", [answer(1000.0, ONE_HOUR)])
    assert cache_state(transcript) == CacheState(last_request=1000.0, window_seconds=3600)
    with transcript.open("a") as handle:
        handle.write(json.dumps(answer(4000.0, ONE_HOUR)) + "\n")
    assert cache_state(transcript) == CacheState(last_request=4000.0, window_seconds=3600)
