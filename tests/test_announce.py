"""The announce endpoints against a stand-in for AIfred's announce API."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.config import Config, default_config_text
from tests.conftest import MAX_CHARS, TOKEN, FakeAifred, FakeClock

PASSWORD = "richtig-langes-passwort"


def make_client(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, url: str | None
) -> TestClient:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    directory = tmp_path / "config" / "agent-orc"
    directory.mkdir(parents=True)
    (directory / "announce-token").write_text(TOKEN + "\n", encoding="utf-8")
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["server"]["cookie_secure"] = False  # TestClient talks plain HTTP
    raw["files"]["base_dir"] = str(tmp_path)
    if url is not None:
        raw["announce"] = {
            "url": url,
            "token_file": "announce-token",
            "max_chars": MAX_CHARS,
            "timeout_seconds": 5,
        }
    credentials = new_credentials(PASSWORD)
    app = create_app(Config.model_validate(raw), credentials, static_dir=None, clock=clock)
    client = TestClient(app)
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 204
    return client


def test_without_a_section_in_the_config_there_is_no_echo(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, url=None)
    assert client.get("/api/announce").json() == {"configured": False, "rooms": [], "max_chars": 0}
    sent = client.post("/api/announce", json={"room": "testraum", "text": "Hallo"})
    assert sent.status_code == 404


def test_the_rooms_and_the_text_go_to_aifred_with_the_token(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, aifred: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, aifred)
    assert client.get("/api/announce").json() == {
        "configured": True,
        "rooms": ["testraum"],
        "max_chars": MAX_CHARS,
    }
    sent = client.post("/api/announce", json={"room": "testraum", "text": "Alles fertig."})
    assert sent.status_code == 204
    assert FakeAifred.spoken == [{"room": "testraum", "text": "Alles fertig."}]
    # AIfred's refusals reach the browser as they are: unknown room, text too long.
    assert client.post("/api/announce", json={"room": "Küche", "text": "x"}).status_code == 404
    long_text = {"room": "testraum", "text": "x" * (MAX_CHARS + 1)}
    assert client.post("/api/announce", json=long_text).status_code == 413


def test_a_wrong_token_is_a_bad_gateway_not_an_open_door(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, aifred: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, aifred)
    (tmp_path / "config" / "agent-orc" / "announce-token").write_text("wrong", encoding="utf-8")
    assert client.get("/api/announce").status_code == 502
