"""The TTS-Suite endpoints against a stand-in for the service."""

import json
import struct
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

PASSWORD = "richtig-langes-passwort"
TOKEN = "service-token"


def frame(header: dict[str, Any], body: bytes = b"") -> bytes:
    head = json.dumps({**header, "bytes": len(body)}).encode()
    return struct.pack(">I", len(head)) + head + body


FRAMES = frame({"kind": "audio", "engine": "xtts"}, b"RIFF1") + frame({"kind": "summary"}, b"{}")


class FakeSpeechService(BaseHTTPRequestHandler):
    heard: list[dict[str, Any]] = []
    asked_with: list[str | None] = []

    def log_message(self, *_: object) -> None:
        pass

    def _answer(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        FakeSpeechService.asked_with.append(self.headers.get("Authorization"))
        voices = [{"name": "Alice", "label": "Alice"}, {"name": "Bob", "label": "Bob (EN)"}]
        self._answer(200, json.dumps(voices).encode(), "application/json")

    def do_POST(self) -> None:
        FakeSpeechService.asked_with.append(self.headers.get("Authorization"))
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeSpeechService.heard.append(body)
        if body["text"] == "fail":
            error = {"error": "no_engine", "detail": "nobody can speak"}
            self._answer(503, json.dumps(error).encode(), "application/json")
        else:
            self._answer(200, FRAMES, "application/x-tts-frames")


@pytest.fixture
def service() -> Iterator[str]:
    FakeSpeechService.heard = []
    FakeSpeechService.asked_with = []
    server = HTTPServer(("127.0.0.1", 0), FakeSpeechService)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    thread.join()


def make_client(
    clock: FakeClock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    url: str | None,
    token_file: str | None = None,
) -> TestClient:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    directory = tmp_path / "config" / "agent-orc"
    directory.mkdir(parents=True)
    (directory / "tts-token").write_text(TOKEN + "\n", encoding="utf-8")
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["server"]["cookie_secure"] = False  # TestClient talks plain HTTP
    raw["files"]["base_dir"] = str(tmp_path)
    if url is not None:
        raw["tts_suite"] = {"url": url, "timeout_seconds": 5, "label": "TTS-Suite"}
        if token_file is not None:
            raw["tts_suite"]["token_file"] = token_file
    app = create_app(
        Config.model_validate(raw), new_credentials(PASSWORD), static_dir=None, clock=clock
    )
    client = TestClient(app)
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 204
    return client


def test_without_a_section_in_the_config_there_is_no_service(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, url=None)
    assert client.get("/api/tts").json() == {"configured": False, "label": "", "voices": []}
    assert client.post("/api/tts/speak", json={"text": "Hi", "language": "en"}).status_code == 404


def test_the_voices_of_the_service_are_offered(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    assert client.get("/api/tts").json() == {
        "configured": True,
        "label": "TTS-Suite",
        "voices": [{"id": "Alice", "label": "Alice"}, {"id": "Bob", "label": "Bob (EN)"}],
    }


def test_the_frames_of_the_service_come_back_unchanged(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    answer = client.post(
        "/api/tts/speak", json={"text": "Hello.", "language": "en", "voice": "Alice", "speed": 1.2}
    )
    assert answer.status_code == 200
    assert answer.headers["content-type"] == "application/x-tts-frames"
    assert answer.content == FRAMES
    assert FakeSpeechService.heard == [
        {"text": "Hello.", "language": "en", "voice": "Alice", "speed": 1.2}
    ]


def test_an_unset_voice_and_speed_are_left_to_the_service(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    client.post("/api/tts/speak", json={"text": "Hello.", "language": "en", "voice": ""})
    assert FakeSpeechService.heard == [{"text": "Hello.", "language": "en"}]


def test_a_service_that_refuses_is_a_bad_gateway_with_its_reason(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    answer = client.post("/api/tts/speak", json={"text": "fail", "language": "en"})
    assert answer.status_code == 502
    assert "503: nobody can speak" in answer.text


def test_a_service_that_is_not_there_is_a_bad_gateway(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, "http://127.0.0.1:1")
    assert client.post("/api/tts/speak", json={"text": "Hi", "language": "en"}).status_code == 502
    assert client.get("/api/tts").status_code == 502


def test_the_token_goes_to_the_service_only_when_configured(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    make_client(clock, tmp_path, monkeypatch, service).get("/api/tts")
    assert FakeSpeechService.asked_with == [None]
    FakeSpeechService.asked_with = []
    other = tmp_path / "other"
    other.mkdir()
    make_client(clock, other, monkeypatch, service, token_file="tts-token").get("/api/tts")
    assert FakeSpeechService.asked_with == [f"Bearer {TOKEN}"]
