"""Handover advice: an agent whose context is filling up should hand over to a fresh session.

A large context costs on every message, the more so once the prompt cache has gone cold (after
a pause the whole context is read in again at full price). An agent whose context is beyond
the threshold is advised to hand over shortly before its cache expires while it rests: once
as a push message, or, if the user switched it on, by typing the handover request into the
agent itself, which writes it while the cache is still warm.

Writing the handover warms the cache again; it would be due again an hour later. So a
handover runs its course (asked, working, done) and stays done until the user's next input;
the agent is left to go cold after that.
"""

import json
from dataclasses import dataclass
from typing import Any

from agent_orc.cache import CacheState
from agent_orc.config import HandoverConfig
from agent_orc.context import session_busy, session_status
from agent_orc.sessions import AgentSession
from agent_orc.state import state_dir, write_atomically

SETTINGS_FILE = "handover.json"
SECONDS_PER_MINUTE = 60
PERCENT = 100
# Where a handover stands: typed into the agent, being written, written; or only advised to
# the user (automatic handovers switched off).
ASKED = "asked"
WORKING = "working"
DONE = "done"
ADVISED = "advised"


@dataclass(frozen=True)
class HandoverAdvice:
    recommended: bool
    # Resting, and its prompt cache expires within the lead time (or has expired).
    due: bool


def context_percent(session: AgentSession) -> float | None:
    status = session_status(session)
    tokens, window = status.get("context_tokens"), status.get("context_window")
    if tokens is None or not window:
        return None
    percent: float = tokens / window * PERCENT
    return percent


def advise(
    session: AgentSession, config: HandoverConfig, cache: CacheState | None, now: float
) -> HandoverAdvice:
    percent = context_percent(session)
    recommended = session.running and percent is not None and percent >= config.threshold_percent
    if not recommended or cache is None or session_busy(session):
        return HandoverAdvice(recommended=recommended, due=False)
    remaining = cache.last_request + cache.window_seconds - now
    return HandoverAdvice(
        recommended=True, due=remaining < config.lead_minutes * SECONDS_PER_MINUTE
    )


def follow_progress(progress: str, busy: bool) -> str | None:
    """Where a handover stands as the agent works or rests; None once the user's next input
    has ended it."""
    if progress == ASKED:
        return WORKING if busy else ASKED
    if progress == WORKING:
        return WORKING if busy else DONE
    # Done or only advised: whatever the agent works on next, the user gave it.
    return None if busy else progress


def read_auto() -> bool:
    """Whether Agent-Orc asks idle agents for their handover by itself (off until switched on)."""
    path = state_dir() / SETTINGS_FILE
    if not path.is_file():
        return False
    settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return settings["auto"] is True


def write_auto(auto: bool) -> None:
    write_atomically(state_dir() / SETTINGS_FILE, json.dumps({"auto": auto}))
