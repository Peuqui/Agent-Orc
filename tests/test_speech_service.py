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


def row(
    engine: str,
    host: str | None,
    *,
    cloud: bool = False,
    browser: bool = False,
    unit: str = "sentence",
) -> dict[str, Any]:
    return {
        "engine": engine,
        "host": host,
        "label": {"de": engine.title(), "en": engine.title()},
        "unit_default": unit,
        "cloud": cloud,
        "needs_gpu": False,
        "browser": browser,
        "status": "stopped",
        "installed": True,
        "start_hint": None,
        "deactivated": False,
        "vram_mib": {},
    }


# The service's catalog: an engine on two machines, a cloud engine, the browser's voice.
ENGINES = [
    row("qwen3local", None),
    row("qwen3local", "Aragon"),
    row("edge", None, cloud=True),
    row("piper", None),
    row("dashscope_audio3", None, cloud=True, unit="whole"),
    row("browser", None, browser=True),
]


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
        if self.path == "/engines":
            self._answer(200, json.dumps(ENGINES).encode(), "application/json")
            return
        assert self.path.startswith("/voices?engine=")
        engine = self.path.removeprefix("/voices?engine=")
        voices = {"edge": [{"name": "Katja", "label": "Katja (DE)"}], "piper": []}[engine]
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
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
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


def entry(
    engine: str, host: str | None = None, unit: str = "sentence", enabled: bool = True
) -> dict[str, Any]:
    return {"engine": engine, "host": host, "unit": unit, "enabled": enabled}


def choose(
    client: TestClient, *entries: dict[str, Any], voices: dict[str, str] | None = None
) -> None:
    """The user's choice: these entries in this order, with these voices."""
    chosen = {"entries": list(entries), "voices": voices or {}}
    assert client.put("/api/tts/choices", json=chosen).status_code == 204


def test_without_a_section_in_the_config_there_is_no_service(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, url=None)
    assert client.get("/api/tts").json() == {"configured": False, "label": ""}
    assert client.post("/api/tts/speak", json={"text": "Hi", "language": "en"}).status_code == 404


def test_the_service_is_known_by_its_label(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    assert client.get("/api/tts").json() == {"configured": True, "label": "TTS-Suite"}


def test_the_catalog_has_every_engine_on_every_machine_and_not_the_browser(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    rows = client.get("/api/tts/catalog").json()
    assert [(each["engine"], each["host"]) for each in rows] == [
        ("qwen3local", None),
        ("qwen3local", "Aragon"),
        ("edge", None),
        ("piper", None),
        ("dashscope_audio3", None),
    ]
    assert rows[2] == {
        "engine": "edge",
        "host": None,
        "label": {"de": "Edge", "en": "Edge"},
        "unit_default": "sentence",
        "cloud": True,
        "needs_gpu": False,
        "status": "stopped",
        "installed": True,
    }


def test_the_voices_of_an_engine_are_asked_of_the_service(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    assert client.get("/api/tts/voices", params={"engine": "edge"}).json() == [
        {"id": "Katja", "label": "Katja (DE)"}
    ]
    assert client.get("/api/tts/voices", params={"engine": "piper"}).json() == []


def test_before_anything_is_chosen_every_catalog_row_is_listed_and_off(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    chosen = client.get("/api/tts/choices").json()
    assert [
        (each["engine"], each["host"], each["unit"], each["enabled"]) for each in chosen["entries"]
    ] == [
        ("qwen3local", None, "sentence", False),
        ("qwen3local", "Aragon", "sentence", False),
        ("edge", None, "sentence", False),
        ("piper", None, "sentence", False),
        ("dashscope_audio3", None, "whole", False),
    ]
    assert chosen["voices"] == {}


def test_the_choice_is_kept_and_nothing_is_removed_when_the_catalog_changes(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    choose(
        client,
        entry("piper", unit="paragraph"),
        entry("gone"),
        entry("edge", enabled=False),
        voices={"piper": "Thorsten", "gone": "X", "edge": "Katja"},
    )
    chosen = client.get("/api/tts/choices").json()
    assert [
        (each["engine"], each["host"], each["unit"], each["enabled"], each["offered"])
        for each in chosen["entries"]
    ] == [
        ("piper", None, "paragraph", True, True),
        # No longer in the catalog: stays, marked, with its settings.
        ("gone", None, "sentence", True, False),
        ("edge", None, "sentence", False, True),
        # Newly in the catalog: at the end, switched off, in the unit the engine recommends.
        ("qwen3local", None, "sentence", False, True),
        ("qwen3local", "Aragon", "sentence", False, True),
        ("dashscope_audio3", None, "whole", False, True),
    ]
    assert chosen["voices"] == {"piper": "Thorsten", "gone": "X", "edge": "Katja"}


def test_an_entry_the_service_does_not_offer_is_never_sent(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    choose(client, entry("gone"), entry("piper"), voices={})
    client.post("/api/tts/speak", json={"text": "Hello.", "language": "en"})
    assert [each["engine"] for each in FakeSpeechService.heard[0]["engines"]] == ["piper"]


def test_an_engine_listed_twice_on_one_machine_is_refused(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    twice = {"entries": [entry("edge"), entry("edge")], "voices": {}}
    assert client.put("/api/tts/choices", json=twice).status_code == 422
    elsewhere = {"entries": [entry("qwen3local"), entry("qwen3local", "Aragon")], "voices": {}}
    assert client.put("/api/tts/choices", json=elsewhere).status_code == 204


def test_an_entry_needs_a_known_unit(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    wrong = {"entries": [entry("edge", unit="line")], "voices": {}}
    assert client.put("/api/tts/choices", json=wrong).status_code == 422


def test_the_frames_of_the_service_come_back_unchanged(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    choose(client, entry("piper"))
    answer = client.post("/api/tts/speak", json={"text": "Hello.", "language": "en", "speed": 1.2})
    assert answer.status_code == 200
    assert answer.headers["content-type"] == "application/x-tts-frames"
    assert answer.content == FRAMES
    assert FakeSpeechService.heard == [
        {
            "text": "Hello.",
            "language": "en",
            "engines": [{"engine": "piper", "unit": "sentence", "host": None}],
            "voices": {},
            "speed": 1.2,
        }
    ]


def test_a_reading_names_the_entries_switched_on_in_order_with_unit_host_and_voices(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    choose(
        client,
        entry("edge", unit="whole"),
        entry("qwen3local", "Aragon", unit="paragraph"),
        entry("qwen3local", enabled=False),
        entry("piper"),
        voices={"edge": "Katja", "qwen3local": "Codine", "piper": ""},
    )
    client.post("/api/tts/speak", json={"text": "Hello.", "language": "en"})
    assert FakeSpeechService.heard == [
        {
            "text": "Hello.",
            "language": "en",
            "engines": [
                {"engine": "edge", "unit": "whole", "host": None},
                {"engine": "qwen3local", "unit": "paragraph", "host": "Aragon"},
                {"engine": "piper", "unit": "sentence", "host": None},
            ],
            "voices": {"edge": {"voice": "Katja"}, "qwen3local": {"voice": "Codine"}},
        }
    ]


def test_without_a_choice_nothing_is_read_and_the_user_is_told_where_to_choose(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    answer = client.post("/api/tts/speak", json={"text": "Hello.", "language": "en"})
    assert answer.status_code == 422 and "choose them in the settings" in answer.text
    assert FakeSpeechService.heard == []


def test_with_every_engine_switched_off_nothing_is_asked_of_the_service(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    client.put(
        "/api/tts/choices", json={"engines": [{"engine": "edge", "enabled": False, "voice": ""}]}
    )
    answer = client.post("/api/tts/speak", json={"text": "Hello.", "language": "en"})
    assert answer.status_code == 422 and "switched on" in answer.text
    assert FakeSpeechService.heard == []


def test_a_service_that_refuses_is_a_bad_gateway_with_its_reason(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, service)
    choose(client, entry("piper"))
    answer = client.post("/api/tts/speak", json={"text": "fail", "language": "en"})
    assert answer.status_code == 502
    assert "503: nobody can speak" in answer.text


def test_a_service_that_is_not_there_is_a_bad_gateway(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, "http://127.0.0.1:1")
    choose(client, entry("piper"))
    assert client.post("/api/tts/speak", json={"text": "Hi", "language": "en"}).status_code == 502
    assert client.get("/api/tts/catalog").status_code == 502


def test_the_token_goes_to_the_service_only_when_configured(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: str
) -> None:
    make_client(clock, tmp_path, monkeypatch, service).get("/api/tts/catalog")
    assert FakeSpeechService.asked_with == [None]
    FakeSpeechService.asked_with = []
    other = tmp_path / "other"
    other.mkdir()
    make_client(clock, other, monkeypatch, service, token_file="tts-token").get("/api/tts/catalog")
    assert FakeSpeechService.asked_with == [f"Bearer {TOKEN}"]
