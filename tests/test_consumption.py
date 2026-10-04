import json
from pathlib import Path
from typing import Any

import pytest

from agent_orc import consumption
from agent_orc.consumption import Tokens, claude_consumption


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(consumption, "_files", {})


def answer(message_id: str, timestamp: str, model: str, output: int) -> dict[str, Any]:
    return {
        "type": "assistant",
        "timestamp": timestamp,
        "cwd": "/w/demo",
        "message": {
            "id": message_id,
            "model": model,
            "content": [{"type": "text", "text": "…"}],
            "usage": {
                "input_tokens": 2,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 1000,
                "output_tokens": output,
            },
        },
    }


def write(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))


def day_of(timestamp: str) -> str:
    return consumption._local_day(timestamp)


def test_each_answer_counts_once_by_day_project_and_model(tmp_path: Path) -> None:
    first, second = "2026-10-03T10:00:00Z", "2026-10-04T10:00:00Z"
    write(
        tmp_path / ".claude/projects/-w-demo/a.jsonl",
        [
            # Claude writes one entry per content block, all with the answer's usage.
            answer("msg-1", first, "opus", 50),
            answer("msg-1", first, "opus", 50),
            answer("msg-2", second, "opus", 7),
            answer("msg-3", second, "haiku", 3),
            {"type": "user", "timestamp": second, "message": {"content": "no usage here"}},
        ],
    )
    # Subagents keep their transcripts in subfolders; their tokens count too.
    write(
        tmp_path / ".claude/projects/-w-demo/a/subagents/agent-1.jsonl",
        [answer("msg-4", second, "haiku", 1)],
    )
    totals = claude_consumption(tmp_path)
    assert totals[(day_of(first), "/w/demo", "opus")] == Tokens(2, 100, 1000, 50, 1)
    assert totals[(day_of(second), "/w/demo", "opus")] == Tokens(2, 100, 1000, 7, 1)
    assert totals[(day_of(second), "/w/demo", "haiku")] == Tokens(4, 200, 2000, 4, 2)


def test_changed_and_removed_files_are_read_again(tmp_path: Path) -> None:
    path = tmp_path / ".claude/projects/-w-demo/a.jsonl"
    when = "2026-10-04T10:00:00Z"
    write(path, [answer("msg-1", when, "opus", 5)])
    assert claude_consumption(tmp_path)[(day_of(when), "/w/demo", "opus")].output == 5
    write(path, [answer("msg-1", when, "opus", 5), answer("msg-2", when, "opus", 6)])
    assert claude_consumption(tmp_path)[(day_of(when), "/w/demo", "opus")].output == 11
    path.unlink()
    assert claude_consumption(tmp_path) == {}
