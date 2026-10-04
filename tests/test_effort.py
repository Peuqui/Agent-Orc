import json
import stat
from pathlib import Path

from agent_orc.effort import (
    CLAUDE_PROJECT_SETTINGS,
    Reasoning,
    read_claude_project_reasoning,
    write_claude_project_reasoning,
)

DEFAULT = Reasoning(effort=None, ultracode=False)


def settings_of(folder: Path) -> Path:
    return folder / CLAUDE_PROJECT_SETTINGS


def test_creates_settings_when_missing(tmp_path: Path) -> None:
    assert read_claude_project_reasoning(tmp_path) == DEFAULT
    write_claude_project_reasoning(tmp_path, Reasoning("xhigh", ultracode=True))
    assert json.loads(settings_of(tmp_path).read_text()) == {
        "effortLevel": "xhigh",
        "ultracode": True,
    }
    assert read_claude_project_reasoning(tmp_path) == Reasoning("xhigh", ultracode=True)


def test_keeps_other_settings_and_file_mode(tmp_path: Path) -> None:
    path = settings_of(tmp_path)
    path.parent.mkdir()
    path.write_text(json.dumps({"permissions": {"allow": ["Bash(git *)"]}}))
    path.chmod(0o600)
    write_claude_project_reasoning(tmp_path, Reasoning("high", ultracode=False))
    assert json.loads(path.read_text()) == {
        "permissions": {"allow": ["Bash(git *)"]},
        "effortLevel": "high",
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(path.parent.glob("*.agent-orc-tmp"))


def test_default_removes_only_its_own_keys(tmp_path: Path) -> None:
    write_claude_project_reasoning(tmp_path, Reasoning("low", ultracode=True))
    path = settings_of(tmp_path)
    data = json.loads(path.read_text())
    path.write_text(json.dumps({**data, "model": "opus"}))
    write_claude_project_reasoning(tmp_path, DEFAULT)
    assert json.loads(path.read_text()) == {"model": "opus"}


def test_ultracode_alone(tmp_path: Path) -> None:
    write_claude_project_reasoning(tmp_path, Reasoning(None, ultracode=True))
    assert json.loads(settings_of(tmp_path).read_text()) == {"ultracode": True}


def test_nothing_to_change_does_not_touch_anything(tmp_path: Path) -> None:
    write_claude_project_reasoning(tmp_path, DEFAULT)
    assert not settings_of(tmp_path).parent.exists()
    write_claude_project_reasoning(tmp_path, Reasoning("low", ultracode=True))
    before = settings_of(tmp_path).stat().st_mtime_ns
    write_claude_project_reasoning(tmp_path, Reasoning("low", ultracode=True))
    assert settings_of(tmp_path).stat().st_mtime_ns == before
