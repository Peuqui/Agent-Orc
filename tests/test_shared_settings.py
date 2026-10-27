"""Settings that are the same on every device: defaults, changes, what is refused, what lasts."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.config import Config, default_config_text
from agent_orc.shared_settings import SharedSettings, SharedSettingsInvalidError, changed
from tests.conftest import FakeClock

PASSWORD = "correct horse"


def client_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["server"]["cookie_secure"] = False
    raw["files"]["base_dir"] = str(tmp_path)
    app = create_app(
        Config.model_validate(raw), new_credentials(PASSWORD), static_dir=None, clock=FakeClock()
    )
    client = TestClient(app)
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 204
    return client


def test_a_new_server_starts_with_the_factory_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answer = client_for(tmp_path, monkeypatch).get("/api/settings").json()
    assert answer == SharedSettings().model_dump()
    assert answer["dictation_device"] == "cpu"  # the CPU unless the GPU is chosen on purpose
    assert answer["dictation_sends_at_once"] is False and answer["speech_engine"] == "browser"
    # Speed and pitch are overrides: nothing set means the service's own values apply.
    assert answer["speech_rate"] is None and answer["speech_pitch"] is None


def test_a_change_names_only_what_it_changes_and_lasts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = client_for(tmp_path, monkeypatch)
    first = client.patch("/api/settings", json={"dictation_device": "cuda"})
    second = client.patch("/api/settings", json={"speech_voices": {"tts-suite": "Alfred"}})
    assert first.status_code == 200 and second.status_code == 200
    now = second.json()
    assert now["dictation_device"] == "cuda"  # the first change is still there after the second
    assert now["speech_voices"] == {"tts-suite": "Alfred"}
    # Another server on the same state (a restart, or another device) reads the same.
    assert client_for(tmp_path, monkeypatch).get("/api/settings").json() == now


@pytest.mark.parametrize(
    "wrong",
    [
        {"no_such_setting": 1},
        {"dictation_device": "tpu"},
        {"speech_rate": 0},
        {"speech_rate": "fast"},
        {"speech_pitch": -1},
        {"speech_max_chars": 5},
        {"speech_engine": ""},
        {"keep_warm_max_pings": 0},
    ],
)
def test_what_cannot_be_kept_is_refused_and_nothing_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong: dict[str, Any]
) -> None:
    client = client_for(tmp_path, monkeypatch)
    answer = client.patch("/api/settings", json={"speech_rate": 1.3, **wrong})
    assert answer.status_code == 422
    # Not even the good part of the change was kept.
    assert client.get("/api/settings").json()["speech_rate"] is None


def test_changed_applies_a_change_to_what_was_stored() -> None:
    now = changed({"speech_rate": 1.2}, {"speech_announce_name": False})
    assert (now.speech_rate, now.speech_announce_name) == (1.2, False)
    with pytest.raises(SharedSettingsInvalidError, match="unknown settings: nope"):
        changed({}, {"nope": True})
