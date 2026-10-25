"""The agents' switches, shared by every device: keeping warm (off by default) and answers as
summaries only (every text by default). Kept across restarts of the service, which a deploy would
otherwise switch off for every agent; they still belong to the agent's session: the server drops
those of a session that no longer runs and resets them when an agent starts anew."""

import json
from typing import Any

from agent_orc.state import state_dir, write_atomically

SWITCHES_FILE = "switches.json"


def read_switches() -> tuple[set[str], set[str]]:
    """The agents that are kept warm, and those whose answers show only the summaries."""
    path = state_dir() / SWITCHES_FILE
    if not path.is_file():
        return set(), set()
    stored: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return set(stored["keep_warm"]), set(stored["summaries"])


def write_switches(keep_warm: set[str], summaries: set[str]) -> None:
    stored = {"keep_warm": sorted(keep_warm), "summaries": sorted(summaries)}
    write_atomically(state_dir() / SWITCHES_FILE, json.dumps(stored))
