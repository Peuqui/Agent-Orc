"""Telling the owner of a GPU-Orc hold, in its session, that a person asked for the end.

GPU-Orc tells nobody when a person asks for the end of an active hold (POST /hold/end): the hold
is marked and stays until its owner lets go. Whoever holds for long asks between its steps, but an
owner that is an agent session of this machine (its folder is the hold's owner) only learns it by
being told. This watcher asks the GPU-Orcs of the backends in a fixed beat and types the text of
`hold_end_notice` into that session at once, also while it works: Claude Code queues an input made
during a turn and hands it to the session still in that turn. That differs from the card gate,
whose text would hang behind a request that fails and so waits for the session to rest.

A hold is told once: the key is the GPU-Orc, the owner and the hold's start (a new hold of the same
owner starts anew). What was told is kept in memory only, so after a restart of Agent-Orc a request
that is still pending is typed once more; that is wanted, the owner may not have got the first one
through.
"""

import asyncio
import logging
from collections.abc import Callable

from agent_orc.backends import Fetch
from agent_orc.config import Config, HoldEndNoticeConfig
from agent_orc.holds import GpuOrcHolds, holds_of_backends
from agent_orc.sessions import AgentSession

logger = logging.getLogger(__name__)

# The GPU-Orc's address, the owner and the start of the hold.
NoticeKey = tuple[str, str, str]


class HoldEndNotice:
    def __init__(
        self,
        config: Config,
        notice: HoldEndNoticeConfig,
        fetch: Fetch,
        list_sessions: Callable[[], list[AgentSession]],
        type_line: Callable[[str, str], None],
    ) -> None:
        self._config = config
        self._notice = notice
        self._fetch = fetch
        self._list_sessions = list_sessions
        self._type_line = type_line
        self._told: set[NoticeKey] = set()

    def notify_once(self) -> None:
        """Tell the owner of each active hold whose end was asked for, if not told yet. Blocking."""
        pending: set[NoticeKey] = set()
        for entry in holds_of_backends(self._config, self._fetch):
            key = _pending_key(entry)
            if key is None:
                continue
            pending.add(key)
            if key not in self._told and self._tell_owner(entry, key):
                self._told.add(key)
        # What is not pending any more (the hold is gone) need not be remembered.
        self._told &= pending

    def _tell_owner(self, entry: GpuOrcHolds, key: NoticeKey) -> bool:
        """Whether the owner's session was told; False while no running session of it is there."""
        hold = entry.hold
        assert hold is not None and hold.end_requested_by is not None
        for session in self._list_sessions():
            # A folder's plain terminal has the agent's name; the text is meant for the agent only.
            if not session.running or session.terminal or session.name != hold.owner:
                continue
            text = self._notice.text.format(
                owner=hold.owner, machine=entry.label, by=hold.end_requested_by
            )
            logger.info("hold end notice: telling %s that %s asked for the end", session.id, key)
            self._type_line(session.id, text)
            return True
        return False

    async def run(self) -> None:
        """Watch until cancelled."""
        while True:
            try:
                await asyncio.to_thread(self.notify_once)
            except Exception:
                # Keep watching; the next beat tries again.
                logger.exception("telling the owner of a hold about the end request failed")
            await asyncio.sleep(self._notice.check_seconds)


def _pending_key(entry: GpuOrcHolds) -> NoticeKey | None:
    """The key of an active hold with an end request; None for anything else (no hold, a requested
    hold, a GPU-Orc that could not be asked, a hold nobody asked the end of)."""
    hold = entry.hold
    if entry.url is None or hold is None or hold.state != "active":
        return None
    if hold.end_requested_by is None:
        return None
    return (entry.url, hold.owner, hold.since)
