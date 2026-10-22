"""Handover advice: an agent whose context is nearly full should hand over to a fresh session.

Shortly before the window is full, Claude Code compacts the context by itself, and the agent
goes on with a summary of what it knew. So an agent beyond the threshold (set just below that
point) is advised to hand over as soon as it rests: once as a push message, or, if the user
switched it on, by typing the handover request into the agent itself. The agent cannot see how
full its context is; the request is its warning.

A handover runs its course (asked, working, done) and stays done while the context is beyond the
threshold, so the agent is asked once per filling; a compaction or a new session starts anew.
"""

import json
from dataclasses import dataclass
from typing import Any

from agent_orc.config import HandoverConfig
from agent_orc.context import session_busy, session_status
from agent_orc.sessions import AgentSession
from agent_orc.state import state_dir, write_atomically

SETTINGS_FILE = "handover.json"
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
    # Recommended, and resting: nothing is typed into a working agent.
    due: bool


def context_percent(session: AgentSession) -> float | None:
    status = session_status(session)
    tokens, window = status.get("context_tokens"), status.get("context_window")
    if tokens is None or not window:
        return None
    percent: float = tokens / window * PERCENT
    return percent


def advise(session: AgentSession, config: HandoverConfig) -> HandoverAdvice:
    percent = context_percent(session)
    recommended = session.running and percent is not None and percent >= config.threshold_percent
    return HandoverAdvice(recommended=recommended, due=recommended and not session_busy(session))


def follow_course(progress: str, busy: bool) -> str:
    """Where a request typed into the agent stands as it works or rests: asked, working, done.
    Done (or only advised) it stays; when that ends is the caller's to say."""
    if progress == ASKED:
        return WORKING if busy else ASKED
    if progress == WORKING:
        return WORKING if busy else DONE
    return progress


def read_auto() -> bool:
    """Whether Agent-Orc asks idle agents for their handover by itself (off until switched on)."""
    path = state_dir() / SETTINGS_FILE
    if not path.is_file():
        return False
    settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return settings["auto"] is True


def write_auto(auto: bool) -> None:
    write_atomically(state_dir() / SETTINGS_FILE, json.dumps({"auto": auto}))
