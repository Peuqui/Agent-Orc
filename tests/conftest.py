import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def socket_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    # Socket files live in pytest's tmp dir, so nothing is left behind in /tmp/tmux-<uid>.
    monkeypatch.setenv("TMUX_TMPDIR", str(tmp_path))
    name = f"agent-orc-test-{uuid.uuid4().hex[:8]}"
    yield name
    subprocess.run(["tmux", "-L", name, "kill-server"], capture_output=True)
