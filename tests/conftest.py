import base64
import json
import os
import subprocess
import threading
import uuid
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import http_ece
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


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
        def do_GET(self) -> None:
            assert self.path == "/status"
            status = {
                "engine": "parakeet",
                "engines": ["whisper", "parakeet"],
                "gpu_quality": "fp32",
                "cpu_quality": "int8",
                "gpu_model": "large-v3",
                "cpu_model": "medium",
            }
            body = json.dumps(status).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakePushService:
    """Stands in for a browser vendor's push service: keeps what arrives, answers as told."""

    def __init__(self) -> None:
        self.received: list[tuple[str, dict[str, str], bytes]] = []
        self.status_by_path: dict[str, int] = {}
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                # Header names are case-insensitive; kept in lower case.
                headers = {name.lower(): value for name, value in self.headers.items()}
                service.received.append((self.path, headers, body))
                self.send_response(service.status_by_path.get(self.path, 201))
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"


@pytest.fixture
def push_service() -> Iterator[FakePushService]:
    service = FakePushService()
    thread = threading.Thread(target=service.server.serve_forever, daemon=True)
    thread.start()
    yield service
    service.server.shutdown()


class Device:
    """A subscribed browser: its own key pair and auth secret, as the Push API creates them."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        public = self.private_key.public_key().public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )
        self.subscription = {
            "endpoint": endpoint,
            "keys": {"p256dh": b64url(public), "auth": b64url(self.auth)},
        }

    def decrypt(self, body: bytes) -> dict[str, Any]:
        plain = http_ece.decrypt(body, private_key=self.private_key, auth_secret=self.auth)
        message: dict[str, Any] = json.loads(plain)
        return message


TOKEN = "secret-token"
MAX_CHARS = 50


class FakeAifred(BaseHTTPRequestHandler):
    """Knows one room, "testraum"; keeps what it was asked to say."""

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
            self._answer(200, {"rooms": ["testraum"]})

    def do_POST(self) -> None:  # noqa: N802
        if not self._allowed():
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body["room"] not in ("testraum", "*"):
            self._answer(404, {"detail": "unknown room"})
        elif any(len(text) > MAX_CHARS for text in body["texts"]):
            self._answer(413, {"detail": "too long"})
        else:
            self.spoken.append(body)
            self._answer(200, {"success": True, "rooms": ["testraum"]})

    def log_message(self, *arguments: Any) -> None:
        pass


@pytest.fixture
def aifred() -> Iterator[str]:
    FakeAifred.spoken = []
    server = HTTPServer(("127.0.0.1", 0), FakeAifred)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/api"
    server.shutdown()
