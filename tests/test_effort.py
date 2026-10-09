import json
import stat
from pathlib import Path

import pytest

from agent_orc.config import LiveEffortConfig
from agent_orc.effort import (
    Reasoning,
    agent_settings_file,
    claude_settings,
    confirm_when_asked,
    read_agent_permission_mode,
    read_agent_reasoning,
    set_reasoning_live,
    store_agent_permission_mode,
    store_agent_reasoning,
    write_agent_settings,
)

BASE = {"statusLine": {"type": "command", "command": "agent-orc statusline"}}


@pytest.fixture(autouse=True)
def state_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


def test_each_agent_keeps_its_own_choices() -> None:
    assert read_agent_reasoning("a-1") is None
    assert read_agent_permission_mode("a-1") is None
    store_agent_reasoning("a-1", Reasoning("xhigh", ultracode=True))
    store_agent_permission_mode("a-1", "plan")
    store_agent_reasoning("a-Review-1", Reasoning("low", ultracode=False))
    # Storing one choice keeps the other.
    assert read_agent_reasoning("a-1") == Reasoning("xhigh", ultracode=True)
    assert read_agent_permission_mode("a-1") == "plan"
    assert read_agent_reasoning("a-Review-1") == Reasoning("low", ultracode=False)
    assert read_agent_permission_mode("a-Review-1") is None


def test_settings_carry_the_profiles_and_the_agents_own_values() -> None:
    settings = claude_settings(BASE, Reasoning("high", ultracode=False), "acceptEdits")
    assert settings == {
        **BASE,
        "effortLevel": "high",
        # Stated as false, so an older true in the folder's own settings does not show through.
        "ultracode": False,
        "permissions": {"defaultMode": "acceptEdits"},
    }
    assert BASE == {"statusLine": {"type": "command", "command": "agent-orc statusline"}}


def test_settings_keep_the_profiles_permissions() -> None:
    base = {"permissions": {"allow": ["Bash(git *)"]}}
    assert claude_settings(base, None, "plan") == {
        "permissions": {"allow": ["Bash(git *)"], "defaultMode": "plan"}
    }
    assert base == {"permissions": {"allow": ["Bash(git *)"]}}


def test_a_model_without_levels_gets_no_effort() -> None:
    assert claude_settings(BASE, Reasoning(None, ultracode=False), None) == {
        **BASE,
        "ultracode": False,
    }


def test_settings_file_is_the_agents_own() -> None:
    path = write_agent_settings("a-1", {"effortLevel": "low"})
    assert path == agent_settings_file("a-1") != agent_settings_file("a-Review-1")
    assert json.loads(path.read_text()) == {"effortLevel": "low"}


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


def test_confirm_presses_enter_once_the_agent_asks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_orc.effort.CONFIRM_SECONDS", 0.3)
    screens = iter(["", "Sure?  1. Yes"])
    pressed: list[str] = []
    confirm_when_asked(lambda: next(screens), lambda: pressed.append("enter"), "Sure?")
    assert pressed == ["enter"]


def test_confirm_does_nothing_when_the_agent_does_not_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_orc.effort.CONFIRM_SECONDS", 0.3)
    pressed: list[str] = []
    confirm_when_asked(lambda: "no question", lambda: pressed.append("enter"), "Sure?")
    assert pressed == []
