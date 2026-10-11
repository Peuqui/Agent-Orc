import json
import threading
import time
from pathlib import Path

import pytest

from agent_orc.state import (
    changing_workspaces,
    empty_workspace,
    read_workspaces,
    write_atomically,
)


def test_writes_at_once_never_leave_a_mixture(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    texts = [json.dumps({"writer": number, "padding": "x" * (number * 500)}) for number in range(8)]
    for _ in range(50):
        threads = [threading.Thread(target=write_atomically, args=(target, text)) for text in texts]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert target.read_text(encoding="utf-8") in texts
    assert list(tmp_path.iterdir()) == [target]


def test_changes_made_at_once_to_the_workspaces_are_all_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    def add(name: str) -> None:
        with changing_workspaces() as stored:
            time.sleep(0.002)  # long enough for every other change to read the old state
            stored[name] = empty_workspace()

    names = [f"workspace-{number}" for number in range(20)]
    threads = [threading.Thread(target=add, args=(name,)) for name in names]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(read_workspaces()) == sorted(names)


def test_a_change_that_fails_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    with pytest.raises(RuntimeError), changing_workspaces() as stored:
        stored["half"] = empty_workspace()
        raise RuntimeError("stop")
    assert read_workspaces() == {}


def test_a_failed_write_leaves_no_file_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def disk_full(self: Path, target: Path) -> Path:
        raise OSError("no space left on device")

    monkeypatch.setattr(Path, "replace", disk_full)
    with pytest.raises(OSError, match="no space"):
        write_atomically(tmp_path / "state.json", "{}")
    assert list(tmp_path.iterdir()) == []
