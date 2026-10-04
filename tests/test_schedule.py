from pathlib import Path

import pytest

from agent_orc.schedule import (
    Reason,
    ScheduledPromptNotFoundError,
    add_scheduled,
    mark_limited,
    next_reset,
    read_scheduled,
    remove_scheduled,
    remove_scheduled_of,
    take_limited,
)


@pytest.fixture(autouse=True)
def state_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


def test_prompts_come_earliest_first_and_can_be_removed() -> None:
    later = add_scheduled("a", "later", 200, Reason.USER)
    sooner = add_scheduled("a", "sooner", 100, Reason.USER)
    assert [p.text for p in read_scheduled()] == ["sooner", "later"]
    remove_scheduled(sooner.id)
    assert read_scheduled() == [later]
    with pytest.raises(ScheduledPromptNotFoundError):
        remove_scheduled(sooner.id)


def test_a_new_limit_resume_replaces_the_agents_earlier_one_only() -> None:
    add_scheduled("a", "own", 50, Reason.USER)
    add_scheduled("a", "resume", 100, Reason.LIMIT)
    add_scheduled("b", "resume", 100, Reason.LIMIT)
    add_scheduled("a", "resume", 300, Reason.LIMIT)
    kept = [(p.session, p.text, p.at) for p in read_scheduled()]
    assert kept == [("a", "own", 50), ("b", "resume", 100), ("a", "resume", 300)]
    remove_scheduled_of("a")
    assert [p.session for p in read_scheduled()] == ["b"]


def test_limit_markers_are_taken_once() -> None:
    assert take_limited() == []
    mark_limited("a")
    mark_limited("a")
    assert take_limited() == ["a"]
    assert take_limited() == []


def test_next_reset_is_the_earliest_coming_one() -> None:
    limits = {
        "five_hour": {"used_percentage": 100, "resets_at": 1000},
        "seven_day": {"used_percentage": 40, "resets_at": 5000},
    }
    assert next_reset(limits, now=500) == 1000
    # The five hours are over already: the week comes next.
    assert next_reset(limits, now=1500) == 5000
    assert next_reset(limits, now=9000) is None
    assert next_reset(None, now=500) is None
