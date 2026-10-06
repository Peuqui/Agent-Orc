"""The announce endpoints against a stand-in for AIfred's announce API."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.config import Config, default_config_text
from tests.conftest import FakeClock

TOKEN = "secret-token"
MAX_CHARS = 50
PASSWORD = "richtig-langes-passwort"


class FakeAifred(BaseHTTPRequestHandler):
    """Knows one room, "Büro"; keeps what it was asked to say."""

    spoken: list[dict[str, Any]] = []

    def _answer(self, status: int, body: dict[str, Any]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def _allowed(self) -> bool:
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._answer(403, {"detail": "wrong token"})
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        if self._allowed():
            self._answer(200, {"rooms": ["Büro"]})

    def do_POST(self) -> None:  # noqa: N802
        if not self._allowed():
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body["room"] not in ("Büro", "*"):
            self._answer(404, {"detail": "unknown room"})
        elif len(body["text"]) > MAX_CHARS:
            self._answer(413, {"detail": "too long"})
        else:
            self.spoken.append(body)
            self._answer(200, {"success": True, "rooms": ["Büro"]})

    def log_message(self, *arguments: Any) -> None:
        pass


@pytest.fixture
def aifred() -> Iterator[str]:
    FakeAifred.spoken = []
    server = HTTPServer(("127.0.0.1", 0), FakeAifred)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/api"
    server.shutdown()


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
    assert client.post("/api/announce", json={"room": "Büro", "text": "Hallo"}).status_code == 404


def test_the_rooms_and_the_text_go_to_aifred_with_the_token(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, aifred: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, aifred)
    assert client.get("/api/announce").json() == {
        "configured": True,
        "rooms": ["Büro"],
        "max_chars": MAX_CHARS,
    }
    sent = client.post("/api/announce", json={"room": "Büro", "text": "Alles fertig."})
    assert sent.status_code == 204
    assert FakeAifred.spoken == [{"room": "Büro", "text": "Alles fertig."}]
    # AIfred's refusals reach the browser as they are: unknown room, text too long.
    assert client.post("/api/announce", json={"room": "Küche", "text": "x"}).status_code == 404
    long_text = {"room": "Büro", "text": "x" * (MAX_CHARS + 1)}
    assert client.post("/api/announce", json=long_text).status_code == 413


def test_a_wrong_token_is_a_bad_gateway_not_an_open_door(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, aifred: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, aifred)
    (tmp_path / "config" / "agent-orc" / "announce-token").write_text("wrong", encoding="utf-8")
    assert client.get("/api/announce").status_code == 502
