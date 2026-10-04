import json
import stat
from pathlib import Path

import pytest

from agent_orc.config import LiveEffortConfig
from agent_orc.effort import (
    CLAUDE_PROJECT_SETTINGS,
    Reasoning,
    read_claude_permission_mode,
    read_claude_project_reasoning,
    set_reasoning_live,
    write_claude_permission_mode,
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


def test_permission_mode_keeps_the_folders_other_permissions(tmp_path: Path) -> None:
    path = settings_of(tmp_path)
    path.parent.mkdir()
    path.write_text(json.dumps({"permissions": {"allow": ["Bash(git *)"]}, "effortLevel": "high"}))
    assert read_claude_permission_mode(tmp_path) is None
    write_claude_permission_mode(tmp_path, "acceptEdits")
    assert read_claude_permission_mode(tmp_path) == "acceptEdits"
    assert json.loads(path.read_text()) == {
        "permissions": {"allow": ["Bash(git *)"], "defaultMode": "acceptEdits"},
        "effortLevel": "high",
    }


def test_permission_mode_in_a_folder_without_settings(tmp_path: Path) -> None:
    write_claude_permission_mode(tmp_path, "plan")
    assert json.loads(settings_of(tmp_path).read_text()) == {"permissions": {"defaultMode": "plan"}}


LIVE = LiveEffortConfig(
    command="/effort {level}",
    ultracode_command="/effort ultracode {state}",
    protected_file="",
)


def live_for(protected: Path) -> LiveEffortConfig:
    return LIVE.model_copy(update={"protected_file": str(protected)})


@pytest.fixture(autouse=True)
def short_protection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_orc.effort.PROTECT_SECONDS", 0.5)
    monkeypatch.setattr("agent_orc.effort.PROTECT_POLL_SECONDS", 0.05)


def test_live_switch_types_the_level_and_puts_the_protected_file_back(tmp_path: Path) -> None:
    protected = tmp_path / "settings.json"
    protected.write_text('{"effortLevel": "high"}\n')
    protected.chmod(0o600)
    typed: list[str] = []

    def agent_types(line: str) -> None:
        typed.append(line)
        # What Claude does on /effort: it saves the level as the user's own default.
        protected.write_text('{"effortLevel": "medium"}')

    old, new = Reasoning("high", ultracode=False), Reasoning("medium", ultracode=False)
    set_reasoning_live(agent_types, live_for(protected), old, new)
    assert typed == ["/effort medium"]
    assert protected.read_text() == '{"effortLevel": "high"}\n'
    assert stat.S_IMODE(protected.stat().st_mode) == 0o600


def test_live_switch_types_ultracode_only_when_it_changes(tmp_path: Path) -> None:
    typed: list[str] = []
    live = live_for(tmp_path / "settings.json")
    set_reasoning_live(typed.append, live, Reasoning("low", False), Reasoning("high", True))
    set_reasoning_live(typed.append, live, Reasoning("high", True), Reasoning("max", True))
    assert typed == ["/effort high", "/effort ultracode on", "/effort max"]


def test_live_switch_removes_a_protected_file_the_agent_created(tmp_path: Path) -> None:
    protected = tmp_path / "settings.json"

    def agent_types(_line: str) -> None:
        protected.write_text("{}")

    set_reasoning_live(
        agent_types,
        live_for(protected),
        Reasoning("low", False),
        Reasoning("high", False),
    )
    assert not protected.exists()
