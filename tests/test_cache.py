import json
from datetime import UTC, datetime
from pathlib import Path

from agent_orc.cache import CacheState, cache_state, last_answer

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
    entries: list[dict[str, object]] = [
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


def test_the_last_answer_is_told_without_anything_written_to_a_cache(tmp_path: Path) -> None:
    # A local model's answers carry no cache_creation at all.
    local: dict[str, object] = {
        "type": "assistant",
        "timestamp": "2026-11-14T10:00:00Z",
        "message": {"usage": {"input_tokens": 12}},
    }
    transcript = write(tmp_path / "a.jsonl", [local, {"type": "user", "message": {}}])
    assert cache_state(transcript) is None
    assert last_answer(transcript) == datetime(2026, 11, 14, 10, 0, tzinfo=UTC).timestamp()
    empty = write(tmp_path / "b.jsonl", [{"type": "user", "message": {"content": "hi"}}])
    assert last_answer(empty) is None
    # Also where an answer wrote to the cache: the newest one counts, not the one that wrote.
    both = write(tmp_path / "c.jsonl", [answer(1000.0, ONE_HOUR), answer(1500.0, NOTHING_WRITTEN)])
    assert last_answer(both) == 1500.0
