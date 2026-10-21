"""Keeping the prompt cache of resting agents warm.

The cache expires one window after an agent's last request (an hour for Claude with a
subscription), and the next message then reads the whole context in again: slow, and a good
deal of the usage limit. A tiny prompt shortly before the end reads the cache instead, which
starts the window anew; a large context costs next to nothing that way.

The cache's window comes from the agent's transcript (cache.py), so nothing here knows an hour.
A prompt is typed only into a resting agent whose cache is still alive but about to expire,
and only so often in a row: the user's next input starts the count anew, as it ends a handover.
Switched on per agent, and only for as long as its session lives: the api keeps the switch in
memory, so a restart, an ended session or a crash leaves it off. The profile says whether it
applies at all.
"""

from dataclasses import dataclass

from agent_orc.cache import CacheState
from agent_orc.config import KeepWarmConfig
from agent_orc.handover import ASKED, DONE, follow_progress

SECONDS_PER_MINUTE = 60


@dataclass(frozen=True)
class KeepWarmProgress:
    """Where the prompts of one rest stand: the last one's course (asked, working, done as with
    a handover) and how many were typed."""

    progress: str
    pings: int

    @classmethod
    def typed(cls, pings: int) -> "KeepWarmProgress":
        return cls(ASKED, pings)

    @property
    def answered(self) -> bool:
        return self.progress == DONE

    def follow(self, busy: bool) -> "KeepWarmProgress | None":
        """None once the user's input has ended the rest: the count starts anew."""
        followed = follow_progress(self.progress, busy)
        return None if followed is None else KeepWarmProgress(followed, self.pings)


def due(config: KeepWarmConfig, cache: CacheState | None, now: float, pings: int) -> bool:
    """The cache is alive but within the lead time of its end. An expired cache is left alone:
    a prompt would only pay for reading it in again, which the next message does anyway. With a
    window no longer than the lead time (five minutes once the account is over its quota) a
    prompt would be due all the time, so there is none."""
    if cache is None or pings >= config.max_pings:
        return False
    lead = config.lead_minutes * SECONDS_PER_MINUTE
    remaining = cache.last_request + cache.window_seconds - now
    return lead < cache.window_seconds and 0 < remaining < lead
