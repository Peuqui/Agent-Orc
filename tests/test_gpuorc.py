"""Freeing the graphics cards through GPU-Orc (gpuorc.py), against a fake GPU-Orc over HTTP."""

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from agent_orc import cli
from agent_orc.config import GpuOrcConfig, default_config_text
from agent_orc.gpuorc import free_for_model, gpu_orc_url, report


class FakeGpuOrc(HTTPServer):
    """Answers /health and /free; /free with what the test set (status and body)."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), GpuOrcHandler)
        self.requests: list[tuple[str, str | None, Any]] = []
        self.free_status = 200
        self.free_answer: Any = {"already_running": True}


class GpuOrcHandler(BaseHTTPRequestHandler):
    server: FakeGpuOrc

    def do_GET(self) -> None:  # noqa: N802
        self.server.requests.append((self.path, self.headers.get("Authorization"), None))
        self.answer(200, {"status": "ok", "free_timeout_s": 660, "caller_timeout_s": 690})

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append((self.path, self.headers.get("Authorization"), body))
        self.answer(self.server.free_status, self.server.free_answer)

    def answer(self, status: int, body: Any) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *arguments: Any) -> None:  # noqa: A002
        pass


@pytest.fixture
def gpu_orc() -> Iterator[FakeGpuOrc]:
    server = FakeGpuOrc()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def test_gpu_orc_is_asked_beside_the_model_server() -> None:
    assert gpu_orc_url("http://10.0.0.1:11435", 5070) == "http://10.0.0.1:5070"
    assert gpu_orc_url("http://127.0.0.1:11435/upstream", 5070) == "http://127.0.0.1:5070"


def test_a_running_model_needs_nothing_said() -> None:
    assert report({"already_running": True, "actions": [], "free": True}, "m") == []


def test_what_went_wrong_is_marked_and_what_went_right_told() -> None:
    answer = {
        "already_running": False,
        "actions": [
            {"consumer": "stt-suite", "item": "gpu-worker", "outcome": "released_forced"},
            {"consumer": "tts-suite", "item": "xtts", "outcome": "refused_busy", "detail": "reads"},
            {"consumer": "llama-swap", "item": "embed", "outcome": "not_freed"},
        ],
        "free": False,
    }
    assert report(answer, "big-model") == [
        "stt-suite gpu-worker: released_forced",
        "problem: tts-suite xtts: refused_busy (reads)",
        "problem: llama-swap embed: not_freed",
        "problem: the cards for big-model are not free, it may fail to load",
    ]


def test_the_request_names_the_model_its_server_and_carries_the_token(
    gpu_orc: FakeGpuOrc, tmp_path: Path
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("secret\n")
    config = GpuOrcConfig(
        port=gpu_orc.server_port, model_server="llama-swap", token_file=token_file
    )

    assert free_for_model(config, "http://127.0.0.1:11435", "big-model") == []

    (health, free) = gpu_orc.requests
    assert health[:2] == ("/health", "Bearer secret")
    assert free[:2] == ("/free", "Bearer secret")
    assert free[2]["model"] == "big-model"
    assert free[2]["model_server"] == "llama-swap"
    assert free[2]["reason"].startswith("Agent-Orc: ")


def test_a_refusal_is_told_with_gpu_orcs_own_words(gpu_orc: FakeGpuOrc) -> None:
    gpu_orc.free_status = 400
    gpu_orc.free_answer = {"error": "unknown model: big-model"}
    config = GpuOrcConfig(port=gpu_orc.server_port)

    (line,) = free_for_model(config, "http://127.0.0.1:11435", "big-model")
    assert line.startswith("problem: GPU-Orc at http://127.0.0.1:")
    assert "(400)" in line and "unknown model: big-model" in line


@pytest.fixture
def silent_port() -> Iterator[int]:
    """A port nothing listens on: bound, but never listening."""
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        yield bound.getsockname()[1]


def test_gpu_orc_that_does_not_answer_is_told(silent_port: int) -> None:
    config = GpuOrcConfig(port=silent_port)
    (line,) = free_for_model(config, "http://127.0.0.1:11435", "big-model")
    assert line.startswith(f"problem: GPU-Orc at http://127.0.0.1:{silent_port} did not free")


def write_config(directory: Path, gpu_orc_port: int) -> None:
    text = default_config_text() + (
        "\nbackends:\n  local:\n    label: Local\n    base_urls: [http://127.0.0.1:11435]\n"
        f"    key: no-key\n    gpu_orc: {{port: {gpu_orc_port}}}\n"
        "    models:\n      big-model: {}\n"
    )
    (directory / "agent-orc").mkdir()
    (directory / "agent-orc" / "config.yaml").write_text(text, encoding="utf-8")


def test_the_input_hook_shows_what_gpu_orc_did(
    gpu_orc: FakeGpuOrc,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_config(tmp_path, gpu_orc.server_port)
    monkeypatch.setenv("AGENT_ORC_BACKEND", "local")
    monkeypatch.setenv("AGENT_ORC_BACKEND_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("AGENT_ORC_BACKEND_MODEL", "big-model")
    gpu_orc.free_answer = {
        "already_running": False,
        "actions": [{"consumer": "llama-swap", "item": "embed", "outcome": "released"}],
        "free": True,
    }

    cli.agent_free_cards()

    shown = json.loads(capsys.readouterr().out)
    assert shown == {"systemMessage": "GPU-Orc: llama-swap embed: released"}


def test_the_input_hook_is_silent_for_a_running_model_and_off_a_backend(
    gpu_orc: FakeGpuOrc,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_config(tmp_path, gpu_orc.server_port)
    monkeypatch.delenv("AGENT_ORC_BACKEND", raising=False)

    cli.agent_free_cards()
    assert gpu_orc.requests == []

    monkeypatch.setenv("AGENT_ORC_BACKEND", "local")
    monkeypatch.setenv("AGENT_ORC_BACKEND_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("AGENT_ORC_BACKEND_MODEL", "big-model")
    cli.agent_free_cards()
    assert [path for path, _, _ in gpu_orc.requests] == ["/health", "/free"]
    assert capsys.readouterr().out == ""
