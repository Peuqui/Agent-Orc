from pathlib import Path

import pytest

from agent_orc.cache import CacheState
from agent_orc.config import KeepWarmConfig
from agent_orc.handover import ASKED, DONE, WORKING
from agent_orc.keepwarm import KeepWarmProgress, due, read_enabled, write_agent

CONFIG = KeepWarmConfig(prompt="Keep-alive", lead_minutes=5, max_pings=3)
HOUR = 3600
NOW = 1_000_000.0


def cache_ending_in(seconds: float, window: int = HOUR) -> CacheState:
    return CacheState(last_request=NOW + seconds - window, window_seconds=window)


def test_due_within_the_lead_time_of_a_living_cache() -> None:
    assert due(CONFIG, cache_ending_in(299), NOW, pings=0)
    assert not due(CONFIG, cache_ending_in(301), NOW, pings=0)


def test_not_due_for_an_expired_cache_or_without_one() -> None:
    # Reading an expired cache in again is what the next message does; no reason to pay it now.
    assert not due(CONFIG, cache_ending_in(-1), NOW, pings=0)
    assert not due(CONFIG, None, NOW, pings=0)


def test_not_due_after_the_pings_in_a_row() -> None:
    assert due(CONFIG, cache_ending_in(100), NOW, pings=2)
    assert not due(CONFIG, cache_ending_in(100), NOW, pings=3)


def test_not_due_when_the_window_is_no_longer_than_the_lead_time() -> None:
    # Five minutes of window (the account is over its quota): it would be due all the time.
    assert not due(CONFIG, cache_ending_in(100, window=300), NOW, pings=0)


def test_a_prompt_runs_its_course_and_the_users_input_ends_the_rest() -> None:
    progress = KeepWarmProgress.typed(2)
    assert progress.progress == ASKED and progress.pings == 2 and not progress.answered
    working = progress.follow(busy=True)
    assert working == KeepWarmProgress(WORKING, 2)
    done = working.follow(busy=False) if working else None
    assert done == KeepWarmProgress(DONE, 2) and done.answered
    # Work after the answer is the user's: the count starts anew.
    assert done.follow(busy=False) == done
    assert done.follow(busy=True) is None


def test_agents_are_switched_on_one_by_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert read_enabled() == set()
    write_agent("a", True)
    write_agent("b", True)
    assert read_enabled() == {"a", "b"}
    write_agent("a", False)
    # Off again for an agent that was never on changes nothing.
    write_agent("c", False)
    assert read_enabled() == {"b"}
