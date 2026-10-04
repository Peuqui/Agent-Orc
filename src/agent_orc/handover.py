"""Handover advice: an agent whose context is filling up should hand over to a fresh session.

A large context costs on every message, the more so once the prompt cache has gone cold (after
a pause the whole context is read in again at full price). From a threshold on, Agent-Orc
advises a handover: on the agent's card, once as a push message, and, if the user switched it
on, by typing the handover request into the idle agent itself.
"""

import json
import time
from dataclasses import dataclass
from typing import Any

from agent_orc.config import HandoverConfig
from agent_orc.context import activity_file, session_busy, session_status
from agent_orc.sessions import AgentSession
from agent_orc.state import state_dir, write_atomically

SETTINGS_FILE = "handover.json"
SECONDS_PER_MINUTE = 60
PERCENT = 100


@dataclass(frozen=True)
class HandoverAdvice:
    recommended: bool
    # Idle long enough for the prompt cache to have expired.
    cache_cold: bool


def context_percent(session: AgentSession) -> float | None:
    status = session_status(session)
    tokens, window = status.get("context_tokens"), status.get("context_window")
    if tokens is None or not window:
        return None
    percent: float = tokens / window * PERCENT
    return percent


def idle_seconds(session: AgentSession) -> float | None:
    """How long the agent has been idle; None while it works or before it ever reported."""
    path = activity_file(session.id)
    if not path.is_file() or path.stat().st_mtime < session.created or session_busy(session):
        return None
    return time.time() - path.stat().st_mtime


def advise(session: AgentSession, config: HandoverConfig) -> HandoverAdvice:
    percent = context_percent(session)
    idle = idle_seconds(session)
    recommended = session.running and percent is not None and percent >= config.threshold_percent
    cold = idle is not None and idle >= config.cold_after_minutes * SECONDS_PER_MINUTE
    return HandoverAdvice(recommended=recommended, cache_cold=recommended and cold)


def read_auto() -> bool:
    """Whether Agent-Orc asks idle agents for their handover by itself (off until switched on)."""
    path = state_dir() / SETTINGS_FILE
    if not path.is_file():
        return False
    settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return settings["auto"] is True


def write_auto(auto: bool) -> None:
    write_atomically(state_dir() / SETTINGS_FILE, json.dumps({"auto": auto}))
