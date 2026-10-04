"""Prompts typed into an agent at a later time: planned by the user, or by Agent-Orc itself when
the agent ran into its usage limit (resumed once the limit is reset).

They are kept on disk, so a restart of Agent-Orc loses none, and written by the server alone:
the hook command (another process) only leaves a marker that its agent hit the limit, which
the server turns into the resume. The server types a due prompt as soon as its agent is idle.
"""

import json
import secrets
import threading
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from agent_orc.state import state_dir, write_atomically

SCHEDULED_PROMPTS_FILE = "scheduled-prompts.json"
LIMITED_DIR = "limited"
# Requests and the server's background check change the list from different threads.
_changing = threading.Lock()


class Reason(StrEnum):
    USER = "user"
    # Resumes an agent stopped by its usage limit; at most one per agent.
    LIMIT = "limit"


@dataclass(frozen=True)
class ScheduledPrompt:
    id: str
    session: str
    text: str
    # When it is due, in seconds since the epoch.
    at: float
    reason: Reason


class ScheduledPromptNotFoundError(LookupError):
    pass


def read_scheduled() -> list[ScheduledPrompt]:
    """All scheduled prompts, earliest first."""
    path = state_dir() / SCHEDULED_PROMPTS_FILE
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    prompts = [ScheduledPrompt(**{**entry, "reason": Reason(entry["reason"])}) for entry in entries]
    return sorted(prompts, key=lambda prompt: prompt.at)


def _write(prompts: list[ScheduledPrompt]) -> None:
    write_atomically(
        state_dir() / SCHEDULED_PROMPTS_FILE, json.dumps([asdict(prompt) for prompt in prompts])
    )


def add_scheduled(session: str, text: str, at: float, reason: Reason) -> ScheduledPrompt:
    """Schedule a prompt; a limit resume replaces the agent's earlier one."""
    prompt = ScheduledPrompt(secrets.token_hex(8), session, text, at, reason)
    with _changing:
        kept = [
            existing
            for existing in read_scheduled()
            if not (
                reason is Reason.LIMIT
                and existing.reason is Reason.LIMIT
                and existing.session == session
            )
        ]
        _write([*kept, prompt])
    return prompt


def remove_scheduled(prompt_id: str) -> None:
    with _changing:
        prompts = read_scheduled()
        kept = [prompt for prompt in prompts if prompt.id != prompt_id]
        if len(kept) == len(prompts):
            raise ScheduledPromptNotFoundError(prompt_id)
        _write(kept)


def remove_scheduled_of(session: str) -> None:
    """Drop the agent's prompts, e.g. when it is stopped."""
    with _changing:
        _write([prompt for prompt in read_scheduled() if prompt.session != session])


def mark_limited(session: str) -> None:
    """Called by the hook command: the usage limit stopped the agent. An empty file, so the
    server never sees a half-written one."""
    folder = state_dir() / LIMITED_DIR
    folder.mkdir(parents=True, exist_ok=True)
    (folder / session).touch()


def take_limited() -> list[str]:
    """Agents that hit their limit since the last call."""
    folder = state_dir() / LIMITED_DIR
    if not folder.is_dir():
        return []
    sessions = []
    for marker in folder.iterdir():
        marker.unlink()
        sessions.append(marker.name)
    return sessions


def next_reset(rate_limits: dict[str, Any] | None, now: float) -> float | None:
    """The earliest coming reset of the usage windows (five hours, week, ...); None while no
    agent has reported them. Should the agent still be limited then, its hook plans the next."""
    if not rate_limits:
        return None
    resets = [
        float(window["resets_at"]) for window in rate_limits.values() if window["resets_at"] > now
    ]
    return min(resets, default=None)
