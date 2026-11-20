"""Telling GPU-Orc while sessions on its backends work (POST /work, github.com/Peuqui/GPU-Orc).

A hold that a person handed the cards by a click is cleared only once no work of anybody else is
reported, so that an answer that is running is never broken off. Agent-Orc reports one lease per
GPU-Orc (backends on the same one count once) while at least one running session on a backend of
it works, and ends it when the last one rests. GPU-Orc ends a lease by itself when the renewals
stop, so a crash of Agent-Orc holds nothing back.

A session turned away by the card gate waits for the hold: it is no work, or GPU-Orc would wait for
it and it for the hold (the grant's last paragraph in GPU-Orc's docs/interface.md).
"""

import asyncio
import logging
from collections import Counter
from collections.abc import Callable, Collection

from agent_orc.backends import Fetch, backend_of_profile
from agent_orc.catalog import machine_name
from agent_orc.config import Config
from agent_orc.context import session_busy
from agent_orc.gpu_orc_client import GpuOrc, GpuOrcError
from agent_orc.holds import ASKING_ERRORS, gpu_orc_of
from agent_orc.sessions import AgentSession

logger = logging.getLogger(__name__)


def work_owner() -> str:
    """The name of the report: one per machine, so that Agent-Orcs on several machines never end
    each other's report."""
    return f"agent-orc@{machine_name()}"


class WorkReporter:
    def __init__(
        self,
        config: Config,
        fetch: Fetch,
        list_sessions: Callable[[], list[AgentSession]],
        waiting_sessions: Callable[[], Collection[str]],  # the sessions the gate turned away
    ) -> None:
        self._config = config
        self._fetch = fetch
        self._list_sessions = list_sessions
        self._waiting_sessions = waiting_sessions
        self._owner = work_owner()
        self._reported: dict[str, GpuOrc] = {}  # by address: the GPU-Orcs holding a lease of ours
        self._failing: set[str] = set()  # what did not get through at the last report

    def working_sessions(self) -> Counter[str]:
        """How many running sessions work on each backend with a GPU-Orc, those waiting for the
        cards left out."""
        backends = self._config.backends or {}
        waiting = self._waiting_sessions()
        working: Counter[str] = Counter()
        for session in self._list_sessions():
            profile = self._config.agents.get(session.profile)
            name = None if profile is None else backend_of_profile(profile)
            if name is None or name not in backends or backends[name].gpu_orc is None:
                continue
            if session.running and session_busy(session) and session.id not in waiting:
                working[name] += 1
        return working

    def report_once(self) -> None:
        """Bring the leases at the GPU-Orcs in line with the sessions that work now. Blocking."""
        failing: set[str] = set()
        workers: dict[str, tuple[GpuOrc, int]] = {}  # by address
        for name, count in self.working_sessions().items():
            backend = (self._config.backends or {})[name]
            try:
                orc, url = gpu_orc_of(backend, self._fetch)
            except ASKING_ERRORS as error:
                failing.add(self._note_failure(name, error))
                continue
            workers[url] = (orc, workers.get(url, (orc, 0))[1] + count)
        for url, (orc, count) in workers.items():
            try:
                orc.work_begin(self._owner, f"Agent-Orc: {count} working session(s)", self._ttl())
                self._reported[url] = orc
            except GpuOrcError as error:
                failing.add(self._note_failure(url, error))
        # A GPU-Orc that could not be found out this time may still be the one of a lease we hold:
        # nothing is ended then, the lease runs out by itself.
        if not failing:
            for url in self._reported.keys() - workers.keys():
                self._end(url, failing)
        for recovered in self._failing - failing:
            logger.info("GPU-Orc work report: %s answers again", recovered)
        self._failing = failing

    def end_all(self) -> None:
        """Blocking; a lease that cannot be ended runs out by itself."""
        for url in list(self._reported):
            self._end(url, set())

    def _end(self, url: str, failing: set[str]) -> None:
        try:
            self._reported[url].work_end(self._owner)
            del self._reported[url]
        except GpuOrcError as error:
            failing.add(self._note_failure(url, error))

    def _note_failure(self, key: str, error: Exception) -> str:
        """Logged once per failure, not on every poll; the key says which one failed."""
        if key not in self._failing:
            logger.warning("GPU-Orc work report to %s failed: %s", key, error)
        return key

    def _ttl(self) -> float:
        return self._config.gpu_orc_work_ttl_seconds

    async def run(self) -> None:
        """Report until cancelled; ends the leases still held when the server stops."""
        try:
            while True:
                try:
                    await asyncio.to_thread(self.report_once)
                except Exception:
                    # Keep reporting; the next poll tries again.
                    logger.exception("reporting work to GPU-Orc failed")
                await asyncio.sleep(self._config.gpu_orc_work_poll_seconds)
        except asyncio.CancelledError:
            await asyncio.to_thread(self.end_all)
            raise
