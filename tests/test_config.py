from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_orc.config import default_config_text, parse_config, user_config_path


def test_default_config_is_valid() -> None:
    config = parse_config(default_config_text())
    assert config.tmux.socket_name == "ai-orc"
    assert "claude" in config.agents


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_config(default_config_text() + "\nunexpected: 1\n")


def test_missing_section_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_config("agents: {}\n")


def test_user_config_path_follows_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert user_config_path() == tmp_path / "ai-orc" / "config.yaml"
