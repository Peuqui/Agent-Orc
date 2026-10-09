"""Reading along in AI-Connect and writing to its agents, against a stand-in for its program."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_orc import peers
from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.config import Config, PeersConfig, default_config_text
from tests.conftest import FakeClock

PASSWORD = "richtig-langes-passwort"
USER_TOKEN = "user-token-123"

# Behaves like AI-Connect's program for JSON lines: "observe" prints the peers, one past message
# and the end of the history, then ends as when the bridge closes; "send" keeps what came on stdin
# (and its arguments) next to it and answers like the bridge.
FAKE_PROGRAM = """
import json, sys, time
from pathlib import Path

def emit(line):
    print(json.dumps(line, ensure_ascii=False), flush=True)

here = Path(sys.argv[0]).parent
if sys.argv[1] == "observe":
    time.sleep(float((here / "pause").read_text()) if (here / "pause").exists() else 0)
    emit({"event": "peers", "peers": [{"name": "Mini:A"}], "arguments": sys.argv[2:]})
    emit({"event": "message", "id": 1, "from": "Mini:A", "to": "Mini:B", "content": "Hallo",
          "context": None, "timestamp": "2026-10-09T20:00:00"})
    emit({"event": "history_end"})
    emit({"event": "error", "kind": "closed"})
    sys.exit(1)
request = json.loads(sys.stdin.read())
(here / "sent.json").write_text(json.dumps({"request": request, "arguments": sys.argv[1:]}))
if request["token"] != "USER_TOKEN":
    emit({"error": "token_refused"})
    sys.exit(1)
if "Mini:offline" in request["to"]:
    emit({"error": "bridge", "message": "unknown peer"})
    sys.exit(1)
emit({"sent": [{"to": to, "id": 7, "online": True} for to in request["to"]]})
""".replace("USER_TOKEN", USER_TOKEN)


def peers_config(tmp_path: Path) -> PeersConfig:
    program = tmp_path / "program" / "fake_jsonl.py"
    program.parent.mkdir()
    program.write_text(FAKE_PROGRAM, encoding="utf-8")
    return PeersConfig(
        command=[sys.executable, str(program)],
        directory=tmp_path,
        hours=24,
        limit=50,
        user_name="Ada",
    )


def make_client(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configured: bool
) -> TestClient:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["server"]["cookie_secure"] = False  # TestClient talks plain HTTP
    raw["files"]["base_dir"] = str(tmp_path)
    if configured:
        raw["peers"] = peers_config(tmp_path).model_dump(mode="json")
    credentials = new_credentials(PASSWORD)
    app = create_app(Config.model_validate(raw), credentials, static_dir=None, clock=clock)
    client = TestClient(app)
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 204
    return client


def test_without_a_section_in_the_config_there_is_no_ai_connect(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, configured=False)
    assert client.get("/api/peers").json() == {"configured": False, "user_name": ""}
    assert client.get("/api/peers/events").status_code == 404
    message = {"token": USER_TOKEN, "to": ["Mini:A"], "content": "Hallo"}
    assert client.post("/api/peers/message", json=message).status_code == 404


def test_the_stream_hands_on_the_programs_lines_until_it_ends(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, configured=True)
    assert client.get("/api/peers").json() == {"configured": True, "user_name": "Ada"}
    with client.stream("GET", "/api/peers/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = [json.loads(line[len("data: ") :]) for line in response.iter_lines() if line]
    assert lines[0] == {
        "event": "peers",
        "peers": [{"name": "Mini:A"}],
        "arguments": ["--hours", "24.0", "--limit", "50"],
    }
    assert [line["event"] for line in lines[1:]] == ["message", "history_end", "error"]
    assert lines[1]["content"] == "Hallo"
    # The last line says why the stream ended; the page decides whether to connect again.
    assert lines[-1] == {"event": "error", "kind": "closed"}


def test_a_quiet_program_gives_room_for_a_keep_alive(tmp_path: Path) -> None:
    config = peers_config(tmp_path)
    (tmp_path / "program" / "pause").write_text("0.5", encoding="utf-8")

    async def first_two() -> list[str | None]:
        lines = []
        async for line in peers.observe(config, quiet_seconds=0.1):
            lines.append(line)
            if line is not None:
                return lines
        return lines

    lines = asyncio.run(first_two())
    assert lines[0] is None
    assert lines[-1] is not None and json.loads(lines[-1])["event"] == "peers"


def test_a_message_goes_out_as_the_user_with_the_token_on_stdin(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, configured=True)
    message = {"token": USER_TOKEN, "to": ["Mini:A", "Mini:B"], "content": "Wie weit?"}
    sent = client.post("/api/peers/message", json=message)
    assert sent.json() == {
        "sent": [
            {"to": "Mini:A", "id": 7, "online": True},
            {"to": "Mini:B", "id": 7, "online": True},
        ]
    }
    received = json.loads((tmp_path / "program" / "sent.json").read_text(encoding="utf-8"))
    assert received == {
        "request": {"token": USER_TOKEN, "as": "Ada", "to": ["Mini:A", "Mini:B"],
                    "content": "Wie weit?"},
        "arguments": ["send"],
    }  # fmt: skip


def test_the_bridges_refusals_reach_the_page(
    clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(clock, tmp_path, monkeypatch, configured=True)
    wrong = {"token": "falsch", "to": ["Mini:A"], "content": "x"}
    # 403, not 401: the page stays logged in, only the token is wrong.
    assert client.post("/api/peers/message", json=wrong).status_code == 403
    offline = {"token": USER_TOKEN, "to": ["Mini:offline"], "content": "x"}
    refused = client.post("/api/peers/message", json=offline)
    assert (refused.status_code, refused.json()["detail"]) == (502, "unknown peer")
