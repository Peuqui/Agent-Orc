from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from agent_orc.auth import load_credentials, verify_password
from agent_orc.config import Config, default_config_text, load_config
from agent_orc.setup import (
    SetupAnswers,
    ask_backend,
    backend_entry,
    backend_presets,
    configured_text,
    run_setup,
    set_value,
)


def test_set_value_changes_only_that_key_and_keeps_the_comments() -> None:
    text = default_config_text()
    changed = set_value(text, "dictation", "whisper_url", None)
    assert yaml.safe_load(changed)["dictation"]["whisper_url"] is None
    assert changed.count("#") == text.count("#")
    assert len(changed.splitlines()) == len(text.splitlines())


def test_set_value_refuses_what_is_not_there() -> None:
    with pytest.raises(ValueError):
        set_value(default_config_text(), "dictation", "no_such_key", "x")
    with pytest.raises(ValueError):
        set_value(default_config_text(), "no_such_section", "port", "1")


def test_answers_make_a_valid_config() -> None:
    answers = SetupAnswers(
        base_dir="~/code",
        behind_https=False,
        whisper_url=None,
        push_contact="mailto:friend@example.org",
    )
    config = Config.model_validate(yaml.safe_load(configured_text(answers)))
    assert config.files.base_dir == Path("~/code").expanduser()
    assert config.server.cookie_secure is False
    assert config.dictation.whisper_url is None
    assert config.push.contact == "mailto:friend@example.org"


def answers_from(lines: list[str]) -> Iterator[str]:
    yield from lines


def test_setup_asks_checks_and_writes_config_and_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    projects = tmp_path / "projects"
    typed = answers_from(
        [str(projects), "y", "n", "n", "y", "http://127.0.0.1:9", "n", "n", "me@example.org"]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(typed))
    passwords = answers_from(["secret-1", "secret-1"])
    monkeypatch.setattr("agent_orc.setup.getpass.getpass", lambda _prompt: next(passwords))
    monkeypatch.setattr("agent_orc.setup.WHISPER_CHECK_SECONDS", 0.2)

    run_setup()

    directory = tmp_path / "config" / "agent-orc"
    config = load_config(directory / "config.yaml")
    assert projects.is_dir()
    assert config.files.base_dir == projects
    assert config.server.cookie_secure is False
    assert config.dictation.whisper_url == "http://127.0.0.1:9"
    assert config.push.contact == "mailto:me@example.org"
    assert verify_password(
        "secret-1", load_credentials(directory / "credentials.json").password_hash
    )


def test_setup_does_not_touch_an_existing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    existing = tmp_path / "config" / "agent-orc" / "config.yaml"
    existing.parent.mkdir(parents=True)
    existing.write_text("mine")
    with pytest.raises(SystemExit):
        run_setup()
    assert existing.read_text() == "mine"


def test_setup_for_a_machine_another_agent_orc_controls_needs_no_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    socket = tmp_path / "run" / "orc.sock"
    # Folder exists, controlled through SSH: yes, the socket, no Whisper, no backends, no e-mail.
    typed = answers_from([str(tmp_path), "y", str(socket), "n", "n", "n", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(typed))
    monkeypatch.setattr(
        "agent_orc.setup.getpass.getpass", lambda _prompt: pytest.fail("no password is asked for")
    )

    run_setup()

    directory = tmp_path / "config" / "agent-orc"
    config = load_config(directory / "config.yaml")
    assert config.server.socket == socket
    assert config.server.port is None
    assert not (directory / "credentials.json").exists()


def answers_with_backends(backends: dict[str, dict[str, Any]]) -> SetupAnswers:
    return SetupAnswers("~/code", False, None, None, backends=backends)


def test_a_local_backend_adds_its_entry_and_a_profile_to_a_valid_config() -> None:
    entry = backend_entry(backend_presets()["local"], "http://127.0.0.1:11435", ["m-1", "m-2"])
    config = Config.model_validate(
        yaml.safe_load(configured_text(answers_with_backends({"local": entry})))
    )
    assert config.backends is not None
    assert list(config.backends["local"].models) == ["m-1", "m-2"]
    assert config.backends["local"].base_urls == ["http://127.0.0.1:11435"]
    profile = config.agents["claude-local"]
    assert profile.start is not None and profile.start[:4] == [
        "agent-orc",
        "backend",
        "run",
        "local",
    ]
    assert profile.models == ["agent-orc", "backend", "models", "local"]
    assert profile.hint is not None


def test_a_cloud_backend_offers_the_models_the_preset_names_not_every_listed_one() -> None:
    presets = backend_presets()
    entry = backend_entry(presets["dashscope"], "https://example.org", ["qwen-a", "other"])
    assert list(entry["models"]) == ["qwen*"]
    config = Config.model_validate(
        yaml.safe_load(configured_text(answers_with_backends({"dashscope": entry})))
    )
    assert config.agents["claude-dashscope"].hint is None
    assert config.backends is not None
    assert config.backends["dashscope"].key_file == Path("~/.config/agent-orc/dashscope.key")


def test_no_backend_leaves_the_config_as_it_was() -> None:
    assert configured_text(answers_with_backends({})) == configured_text(
        SetupAnswers("~/code", False, None, None)
    )


def test_asking_for_a_cloud_backend_keeps_the_key_for_the_user_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key_file = tmp_path / "keys" / "dashscope.key"
    preset = backend_presets()["dashscope"]
    preset["backend"]["key_file"] = str(key_file)
    typed = answers_from(["y", "https://example.org"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(typed))
    monkeypatch.setattr("agent_orc.setup.getpass.getpass", lambda _prompt: "secret-key")
    monkeypatch.setattr(
        "agent_orc.setup.fetch_json", lambda url, key, timeout: {"data": [{"id": "qwen-a"}]}
    )

    entry = ask_backend(preset)

    assert entry is not None and entry["base_urls"] == ["https://example.org"]
    assert key_file.read_text() == "secret-key\n"
    assert key_file.stat().st_mode & 0o777 == 0o600


def test_a_server_that_does_not_answer_writes_no_entry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    typed = answers_from(["y", "http://127.0.0.1:9"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(typed))

    def unreachable(url: str, key: str | None, timeout: float) -> None:
        raise OSError("refused")

    monkeypatch.setattr("agent_orc.setup.fetch_json", unreachable)
    assert ask_backend(backend_presets()["local"]) is None
    assert "Skipped" in capsys.readouterr().out
