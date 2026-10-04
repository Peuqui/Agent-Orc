import json
import subprocess
import threading
import uuid
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def socket_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    # Socket files live in pytest's tmp dir, so nothing is left behind in /tmp/tmux-<uid>.
    monkeypatch.setenv("TMUX_TMPDIR", str(tmp_path))
    name = f"agent-orc-test-{uuid.uuid4().hex[:8]}"
    yield name
    subprocess.run(["tmux", "-L", name, "kill-server"], capture_output=True)


class FakeWhisper:
    """A stand-in for the whisper-stt service: records requests, answers as configured."""

    def __init__(self) -> None:
        self.status = 200
        self.answer: dict[str, str] = {"text": " Hallo Welt "}
        self.bodies: list[bytes] = []
        self.url = ""


@pytest.fixture
def fake_whisper() -> Iterator[FakeWhisper]:
    fake = FakeWhisper()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            assert self.path == "/transcribe"
            fake.bodies.append(self.rfile.read(int(self.headers["Content-Length"])))
            body = json.dumps(fake.answer).encode()
            self.send_response(fake.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fake.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake
    server.shutdown()
    server.server_close()
