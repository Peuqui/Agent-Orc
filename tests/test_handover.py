import os
from pathlib import Path

from agent_orc.config import HandoverConfig
from agent_orc.handover import (
    ADVISED,
    ASKED,
    DONE,
    HANDOVER_FILE,
    SETTLED_SECONDS,
    WORKING,
    HandoverAdvice,
    assess,
    follow_course,
    handover_prompt,
    handover_written,
)

CONFIG = HandoverConfig(
    advice_percent=90,
    compact_percent=97,
    reserve_tokens=50_000,
    prompt="p",
    early_prompt="e",
    fresh_prompt="write {file}",
    resume_prompt="read {file}",
)


def test_an_asked_request_runs_its_course() -> None:
    # Typed in, but the agent has not started yet.
    assert follow_course(ASKED, busy=False) == ASKED
    assert follow_course(ASKED, busy=True) == WORKING
    assert follow_course(WORKING, busy=True) == WORKING
    assert follow_course(WORKING, busy=False) == DONE


def test_done_or_advised_stays_whatever_the_agent_does() -> None:
    for progress in (DONE, ADVISED):
        assert follow_course(progress, busy=False) == progress
        assert follow_course(progress, busy=True) == progress


def test_the_handover_is_due_a_reserve_of_tokens_before_the_compaction() -> None:
    # A million: compaction at 970,000, due from 920,000 on (92 %), advised from 90 % on.
    assert assess(899_000, 1_000_000, CONFIG) == HandoverAdvice(recommended=False, due=False)
    assert assess(905_000, 1_000_000, CONFIG) == HandoverAdvice(recommended=True, due=False)
    assert assess(920_000, 1_000_000, CONFIG) == HandoverAdvice(recommended=True, due=True)
    # 200,000: due from 144,000 on (72 %), before the advice share, which it advises then too.
    assert assess(143_000, 200_000, CONFIG) == HandoverAdvice(recommended=False, due=False)
    assert assess(144_000, 200_000, CONFIG) == HandoverAdvice(recommended=True, due=True)


def test_the_prompts_name_the_handover_file() -> None:
    assert handover_prompt(CONFIG.fresh_prompt) == f"write {HANDOVER_FILE}"


def test_the_handover_counts_as_written_once_new_and_settled(tmp_path: Path) -> None:
    assert not handover_written(tmp_path, asked_at=100.0, now=200.0)
    path = tmp_path / HANDOVER_FILE
    path.parent.mkdir()
    path.write_text("handover")
    os.utime(path, (150.0, 150.0))
    # Written before the request: an old one.
    assert not handover_written(tmp_path, asked_at=160.0, now=200.0)
    # Written since, but just now: the agent may still be writing.
    assert not handover_written(tmp_path, asked_at=100.0, now=150.0 + SETTLED_SECONDS - 1)
    assert handover_written(tmp_path, asked_at=100.0, now=150.0 + SETTLED_SECONDS)
