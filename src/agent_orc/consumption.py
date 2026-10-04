"""Token consumption of Claude Code, from its own transcripts (~/.claude/projects/), so every
conversation counts, whether it ran in Agent-Orc, a terminal or VS Code, and the subagents' too
(in subfolders).

Each answer carries its usage; Claude writes one transcript entry per content block, all with
the same message id and usage, so every message is counted once. A file is read again only
when it changed; the totals per file are kept in memory.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_orc.history import CLAUDE_PROJECTS

USAGE_FIELDS = {
    "input": "input_tokens",
    "cache_write": "cache_creation_input_tokens",
    "cache_read": "cache_read_input_tokens",
    "output": "output_tokens",
}


@dataclass
class Tokens:
    input: int = 0
    cache_write: int = 0
    cache_read: int = 0
    output: int = 0
    messages: int = 0

    def add(self, other: "Tokens") -> None:
        self.input += other.input
        self.cache_write += other.cache_write
        self.cache_read += other.cache_read
        self.output += other.output
        self.messages += other.messages


# (day as YYYY-MM-DD in local time, project folder, model) -> tokens
Totals = dict[tuple[str, str, str], Tokens]


@dataclass
class _FileTotals:
    mtime: float
    size: int
    totals: Totals = field(default_factory=dict)


_files: dict[Path, _FileTotals] = {}


def _local_day(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone().date().isoformat()


def _read_file(path: Path) -> Totals:
    usage_by_message: dict[str, tuple[tuple[str, str, str], dict[str, Any]]] = {}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            # Cheap check first: only answers carry a usage.
            if '"usage"' not in line:
                continue
            entry: dict[str, Any] = json.loads(line)
            message = entry.get("message") or {}
            if entry.get("type") != "assistant" or "usage" not in message or "id" not in message:
                continue
            key = (_local_day(entry["timestamp"]), entry.get("cwd", ""), message.get("model", ""))
            usage_by_message[message["id"]] = (key, message["usage"])
    totals: Totals = defaultdict(Tokens)
    for key, usage in usage_by_message.values():
        tokens = Tokens(
            messages=1,
            **{name: int(usage.get(source) or 0) for name, source in USAGE_FIELDS.items()},
        )
        totals[key].add(tokens)
    return dict(totals)


def claude_consumption(home: Path) -> Totals:
    """All of Claude's token consumption by day, project and model."""
    seen = set()
    for path in (home / CLAUDE_PROJECTS).rglob("*.jsonl"):
        seen.add(path)
        stat = path.stat()
        known = _files.get(path)
        if known is None or (known.mtime, known.size) != (stat.st_mtime, stat.st_size):
            _files[path] = _FileTotals(stat.st_mtime, stat.st_size, _read_file(path))
    for gone in set(_files) - seen:
        del _files[gone]
    combined: Totals = defaultdict(Tokens)
    for file_totals in _files.values():
        for key, tokens in file_totals.totals.items():
            combined[key].add(tokens)
    return dict(combined)
