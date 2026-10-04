from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_orc.config import config_dir, default_config_text, parse_config


def test_default_config_is_valid() -> None:
    config = parse_config(default_config_text())
    assert config.tmux.socket_name == "agent-orc"
    assert "claude" in config.agents
    assert config.files.base_dir.is_absolute()


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_config(default_config_text() + "\nunexpected: 1\n")


def test_missing_section_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_config("agents: {}\n")


def test_config_dir_follows_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_dir() == tmp_path / "agent-orc"


def test_terminal_keys_parse_escapes() -> None:
    keys = parse_config(default_config_text()).terminal.keys
    sends = {key.label: key.send for row in keys for key in row}
    assert sends["Esc"] == "\x1b"
    assert sends["⇧Tab"] == "\x1b[Z"
    assert sends["^C"] == "\x03"


def test_key_needs_exactly_one_action() -> None:
    text = default_config_text().replace('{label: Esc, send: "\\e"}', "{label: Esc}")
    with pytest.raises(ValidationError):
        parse_config(text)
