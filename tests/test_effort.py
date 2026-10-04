import json
import stat
from pathlib import Path

from agent_orc.effort import (
    CLAUDE_PROJECT_SETTINGS,
    read_claude_project_effort,
    write_claude_project_effort,
)


def settings_of(folder: Path) -> Path:
    return folder / CLAUDE_PROJECT_SETTINGS


def test_creates_settings_when_missing(tmp_path: Path) -> None:
    assert read_claude_project_effort(tmp_path) is None
    write_claude_project_effort(tmp_path, "xhigh")
    assert json.loads(settings_of(tmp_path).read_text()) == {"effortLevel": "xhigh"}
    assert read_claude_project_effort(tmp_path) == "xhigh"


def test_keeps_other_settings_and_file_mode(tmp_path: Path) -> None:
    path = settings_of(tmp_path)
    path.parent.mkdir()
    path.write_text(json.dumps({"permissions": {"allow": ["Bash(git *)"]}}))
    path.chmod(0o600)
    write_claude_project_effort(tmp_path, "high")
    assert json.loads(path.read_text()) == {
        "permissions": {"allow": ["Bash(git *)"]},
        "effortLevel": "high",
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(path.parent.glob("*.agent-orc-tmp"))


def test_none_removes_only_the_effort(tmp_path: Path) -> None:
    write_claude_project_effort(tmp_path, "low")
    path = settings_of(tmp_path)
    data = json.loads(path.read_text())
    path.write_text(json.dumps({**data, "model": "opus"}))
    write_claude_project_effort(tmp_path, None)
    assert json.loads(path.read_text()) == {"model": "opus"}


def test_nothing_to_change_does_not_touch_anything(tmp_path: Path) -> None:
    write_claude_project_effort(tmp_path, None)
    assert not settings_of(tmp_path).parent.exists()
    write_claude_project_effort(tmp_path, "low")
    before = settings_of(tmp_path).stat().st_mtime_ns
    write_claude_project_effort(tmp_path, "low")
    assert settings_of(tmp_path).stat().st_mtime_ns == before
