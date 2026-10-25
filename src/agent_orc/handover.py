"""Handover advice: an agent whose context is nearly full should hand over to a fresh session.

Shortly before the window is full, Claude Code compacts the context by itself, and the agent
goes on with a summary of what it knew. The agent cannot see how full its context is, so
Agent-Orc tells it. From the advice share on, the card advises a handover, and while automatic
handovers are off a push message says so once, early enough for the user to ask for it. From
the threshold on (set just below the compaction) the handover is due: with automatic handovers
on, the request is typed into the agent at once, also while it works, as Claude Code takes in
what is typed during a turn at its next step. Not while it waits for a permission (the text
would answer the prompt) or compacts.

A handover runs its course (asked, working, done) and stays done while the context is beyond the
advice share, so the agent is asked once per filling; a compaction or a new session starts anew.

Handed over to a fresh session (a switch next to the automatic one): the request asks the agent to
write its handover to a known file and end its turn, instead of going on. Once it has, Agent-Orc
types /clear (Claude Code starts a new conversation in the same folder, with CLAUDE.md and memory)
and then the request to read the file and go on: no compaction, and the new conversation starts
small. The conversations before stay listed for the answers view.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from agent_orc.config import HandoverConfig
from agent_orc.context import session_status
from agent_orc.sessions import AgentSession
from agent_orc.state import state_dir, write_atomically

SETTINGS_FILE = "handover.json"
# What Claude Code takes as "start a new conversation in this folder".
CLEAR_COMMAND = "/clear"
# Where each agent's handover stands, kept across restarts of the service: otherwise a restart
# would take a handover already written for "not asked yet" and ask the same filling again.
PROGRESS_FILE = "handover-progress.json"
PERCENT = 100
# Where a handover stands: typed into the agent, being written, written; or only advised to
# the user (automatic handovers switched off).
ASKED = "asked"
WORKING = "working"
DONE = "done"
ADVISED = "advised"
# Handed over to a fresh session: /clear typed, then the request to read the handover.
CLEARED = "cleared"
RESUMED = "resumed"


@dataclass(frozen=True)
class HandoverAdvice:
    # Beyond the advice share.
    recommended: bool
    # Beyond the threshold.
    due: bool


def context_percent(session: AgentSession) -> float | None:
    status = session_status(session)
    tokens, window = status.get("context_tokens"), status.get("context_window")
    if tokens is None or not window:
        return None
    percent: float = tokens / window * PERCENT
    return percent


def advise(session: AgentSession, config: HandoverConfig) -> HandoverAdvice:
    percent = context_percent(session) if session.running else None
    if percent is None:
        return HandoverAdvice(recommended=False, due=False)
    return HandoverAdvice(
        recommended=percent >= config.advice_percent, due=percent >= config.threshold_percent
    )


def follow_course(progress: str, busy: bool) -> str:
    """Where a request typed into the agent stands as it works or rests: asked, working, done.
    Done (or only advised) it stays; when that ends is the caller's to say."""
    if progress == ASKED:
        return WORKING if busy else ASKED
    if progress == WORKING:
        return WORKING if busy else DONE
    return progress


@dataclass(frozen=True)
class HandoverSwitches:
    # Agent-Orc asks agents for their handover by itself.
    auto: bool
    # ... and hands over to a fresh session instead of letting the agent go on.
    fresh: bool


def read_handover_switches() -> HandoverSwitches:
    """Both off until switched on."""
    path = state_dir() / SETTINGS_FILE
    if not path.is_file():
        return HandoverSwitches(auto=False, fresh=False)
    settings: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return HandoverSwitches(auto=settings["auto"] is True, fresh=settings["fresh"] is True)


def write_handover_switches(switches: HandoverSwitches) -> None:
    write_atomically(state_dir() / SETTINGS_FILE, json.dumps(asdict(switches)))


@dataclass
class HandoverState:
    """Where each agent's handover stands; the agents whose handover was asked for by hand early;
    those handed over to a fresh session; and per agent the transcripts of its conversations
    before such a handover, oldest first (for the answers view)."""

    progress: dict[str, str] = field(default_factory=dict)
    early: set[str] = field(default_factory=set)
    fresh: set[str] = field(default_factory=set)
    previous: dict[str, list[str]] = field(default_factory=dict)

    def as_json(self) -> str:
        return json.dumps({
            "progress": self.progress,
            "early": sorted(self.early),
            "fresh": sorted(self.fresh),
            "previous": self.previous,
        })


def read_state() -> HandoverState:
    """Empty before the first handover."""
    path = state_dir() / PROGRESS_FILE
    if not path.is_file():
        return HandoverState()
    stored: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return HandoverState(
        progress=dict(stored["progress"]),
        early=set(stored["early"]),
        fresh=set(stored["fresh"]),
        previous=dict(stored["previous"]),
    )


def write_state(state: HandoverState) -> None:
    write_atomically(state_dir() / PROGRESS_FILE, state.as_json())
