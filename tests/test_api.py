"""End-to-end tests of the HTTP API with a real tmux server and a throwaway home."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from ai_orc.api import create_app
from ai_orc.auth import new_credentials
from ai_orc.config import Config, default_config_text
from tests.conftest import FakeClock

PASSWORD = "richtig-langes-passwort"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    (home / "private").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    return home


@pytest.fixture
def config(home: Path, socket_name: str) -> Config:
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["server"]["cookie_secure"] = False  # TestClient talks plain HTTP
    raw["files"]["base_dir"] = str(home / "projects")
    raw["tmux"]["socket_name"] = socket_name
    raw["agents"] = {
        "sleeper": {"label": "Sleeper", "start": ["sleep", "60"], "resume": ["true"]},
        "shell": {
            "label": "Shell",
            "start": ["sh", "-c", "echo READY; exec cat"],
            "resume": ["true"],
        },
    }
    return Config.model_validate(raw)


@pytest.fixture
def anonymous(config: Config, clock: FakeClock) -> TestClient:
    return TestClient(create_app(config, new_credentials(PASSWORD), static_dir=None, clock=clock))


@pytest.fixture
def client(anonymous: TestClient) -> TestClient:
    assert anonymous.post("/api/login", json={"password": PASSWORD}).status_code == 204
    return anonymous


def test_everything_requires_login(anonymous: TestClient) -> None:
    for method, url in [
        ("GET", "/api/me"),
        ("GET", "/api/sessions"),
        ("GET", "/api/files?path=/"),
        ("GET", "/api/trash"),
        ("DELETE", "/api/trash"),
    ]:
        assert anonymous.request(method, url).status_code == 401, url


def test_login_cookie_is_http_only_and_strict(anonymous: TestClient) -> None:
    response = anonymous.post("/api/login", json={"password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert anonymous.get("/api/me").json() == {"authenticated": True}


def test_logout(client: TestClient) -> None:
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_lockout_after_failed_logins(anonymous: TestClient, clock: FakeClock) -> None:
    for _ in range(5):
        assert anonymous.post("/api/login", json={"password": "wrong"}).status_code == 401
    locked = anonymous.post("/api/login", json={"password": PASSWORD})
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    clock.advance(15 * 60 + 1)
    assert anonymous.post("/api/login", json={"password": PASSWORD}).status_code == 204


def test_session_expires(client: TestClient, clock: FakeClock) -> None:
    clock.advance(31 * 86400)
    assert client.get("/api/me").status_code == 401


def test_folder_session_and_trash_flow(client: TestClient, home: Path) -> None:
    projects = home / "projects"
    created = client.post("/api/files/folder", json={"parent": str(projects), "name": "demo"})
    assert created.status_code == 200
    demo = Path(created.json()["path"])
    assert demo == projects / "demo"

    session = client.post(
        "/api/sessions", json={"profile": "sleeper", "path": str(demo), "resume": False}
    )
    assert session.status_code == 200
    assert session.json()["running"] is True
    assert [s["path"] for s in client.get("/api/sessions").json()] == [str(demo)]

    # A folder with a running agent can neither be trashed nor renamed.
    assert client.post("/api/files/trash", json={"path": str(demo)}).status_code == 409
    rename = client.post("/api/files/rename", json={"path": str(demo), "new_name": "x"})
    assert rename.status_code == 409

    assert client.delete(f"/api/sessions/{session.json()['id']}").status_code == 204
    trashed = client.post("/api/files/trash", json={"path": str(demo)})
    assert trashed.status_code == 200
    assert not demo.exists()

    entries = client.get("/api/trash").json()
    assert [entry["original_path"] for entry in entries] == [str(demo)]
    restored = client.post("/api/trash/restore", json={"id": entries[0]["id"]})
    assert restored.status_code == 200
    assert demo.is_dir()


def test_second_agent_in_same_folder_is_refused(client: TestClient, home: Path) -> None:
    body = {"profile": "sleeper", "path": str(home / "projects"), "resume": False}
    assert client.post("/api/sessions", json=body).status_code == 200
    assert client.post("/api/sessions", json=body).status_code == 409


def test_unknown_profile_and_missing_folder(client: TestClient, home: Path) -> None:
    unknown = {"profile": "nope", "path": str(home / "projects"), "resume": False}
    assert client.post("/api/sessions", json=unknown).status_code == 404
    missing = {"profile": "sleeper", "path": str(home / "projects" / "missing"), "resume": False}
    assert client.post("/api/sessions", json=missing).status_code == 400


def test_base_dir_and_home_cannot_be_trashed(client: TestClient, home: Path) -> None:
    assert client.post("/api/files/trash", json={"path": str(home / "projects")}).status_code == 403


def test_outside_scope_until_unlocked(client: TestClient, home: Path, clock: FakeClock) -> None:
    private = str(home / "private")
    assert client.get("/api/files", params={"path": private}).status_code == 403

    assert client.post("/api/scope/unlock", json={"password": "wrong"}).status_code == 401
    unlocked = client.post("/api/scope/unlock", json={"password": PASSWORD})
    assert unlocked.json()["root"] == str(home)
    assert unlocked.json()["unlock_minutes"] == 10
    assert client.get("/api/files", params={"path": private}).status_code == 200

    clock.advance(10 * 60 + 1)
    assert client.get("/api/files", params={"path": private}).status_code == 403


def test_restore_outside_scope_needs_unlock(client: TestClient, home: Path) -> None:
    client.post("/api/scope/unlock", json={"password": PASSWORD})
    (home / "private" / "note.txt").write_text("x")
    client.post("/api/files/trash", json={"path": str(home / "private" / "note.txt")})
    client.post("/api/scope/lock")
    entry_id = client.get("/api/trash").json()[0]["id"]
    assert client.post("/api/trash/restore", json={"id": entry_id}).status_code == 403


def test_editor_roundtrip_with_conflict(client: TestClient, home: Path) -> None:
    path = str(home / "projects" / "notes.md")
    created = client.put(
        "/api/files/content", json={"path": path, "content": "eins", "expected_modified_ns": None}
    )
    assert created.status_code == 200
    loaded = client.get("/api/files/content", params={"path": path}).json()
    assert loaded["content"] == "eins"

    stale = loaded["modified_ns"] - 1
    conflict = client.put(
        "/api/files/content", json={"path": path, "content": "zwei", "expected_modified_ns": stale}
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "FileConflictError"

    saved = client.put(
        "/api/files/content",
        json={"path": path, "content": "zwei", "expected_modified_ns": loaded["modified_ns"]},
    )
    assert saved.status_code == 200
    assert Path(path).read_text() == "zwei"


def test_list_files_and_invalid_name(client: TestClient, home: Path) -> None:
    (home / "projects" / "a.txt").write_text("x")
    listing = client.get("/api/files", params={"path": str(home / "projects")}).json()
    assert [entry["name"] for entry in listing] == ["a.txt"]
    bad = client.post("/api/files/folder", json={"parent": str(home / "projects"), "name": "../x"})
    assert bad.status_code == 422


def test_empty_trash(client: TestClient, home: Path) -> None:
    (home / "projects" / "a.txt").write_text("x")
    client.post("/api/files/trash", json={"path": str(home / "projects" / "a.txt")})
    assert client.delete("/api/trash").status_code == 204
    assert client.get("/api/trash").json() == []


def test_serves_pwa_next_to_api(config: Config, clock: FakeClock, tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<title>AI-Orc</title>")
    app = create_app(config, new_credentials(PASSWORD), static_dir=static, clock=clock)
    client = TestClient(app)
    assert "AI-Orc" in client.get("/").text
    assert client.get("/api/me").status_code == 401


ORIGIN = {"origin": "http://testserver"}
MAX_TERMINAL_FRAMES = 500


def start_shell(client: TestClient, home: Path) -> str:
    body = {"profile": "shell", "path": str(home / "projects"), "resume": False}
    session_id: str = client.post("/api/sessions", json=body).json()["id"]
    return session_id


def read_until(terminal: WebSocketTestSession, text: str) -> str:
    received = ""
    for _ in range(MAX_TERMINAL_FRAMES):
        received += terminal.receive_bytes().decode(errors="replace")
        if text in received:
            return received
    raise AssertionError(f"{text!r} not seen in terminal output")


def refused_code(client: TestClient, session_id: str, headers: dict[str, str]) -> int:
    url = f"/api/sessions/{session_id}/terminal"
    connect = client.websocket_connect(url, headers=headers)
    with pytest.raises(WebSocketDisconnect) as refused, connect:
        pass
    code: int = refused.value.code
    return code


def test_terminal_refuses_anonymous_foreign_origin_and_unknown_session(
    anonymous: TestClient, home: Path
) -> None:
    assert refused_code(anonymous, "x", ORIGIN) == 4401
    anonymous.post("/api/login", json={"password": PASSWORD})
    session_id = start_shell(anonymous, home)
    assert refused_code(anonymous, session_id, {"origin": "https://evil.example"}) == 4403
    assert refused_code(anonymous, "unknown", ORIGIN) == 4404


def tmux_client_size(socket_name: str) -> str:
    return subprocess.run(
        ["tmux", "-L", socket_name, "list-clients", "-F", "#{client_width}x#{client_height}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


def test_terminal_roundtrip_resize_and_detach(
    client: TestClient, home: Path, socket_name: str
) -> None:
    session_id = start_shell(client, home)
    with client.websocket_connect(f"/api/sessions/{session_id}/terminal", headers=ORIGIN) as term:
        read_until(term, "READY")
        term.send_text(json.dumps({"type": "input", "data": "hallo-orc\r"}))
        read_until(term, "hallo-orc")

        term.send_text(json.dumps({"type": "resize", "cols": 101, "rows": 31}))
        # tmux redraws after the resize, so each received frame is a chance to re-check.
        for _ in range(MAX_TERMINAL_FRAMES):
            if tmux_client_size(socket_name) == "101x31":
                break
            term.receive_bytes()
        assert tmux_client_size(socket_name) == "101x31"

    # Closing the terminal only detaches: the agent keeps running.
    assert client.get("/api/sessions").json()[0]["running"] is True


def test_terminal_closes_when_session_stops(client: TestClient, home: Path) -> None:
    session_id = start_shell(client, home)
    with client.websocket_connect(f"/api/sessions/{session_id}/terminal", headers=ORIGIN) as term:
        read_until(term, "READY")
        client.delete(f"/api/sessions/{session_id}")
        with pytest.raises(WebSocketDisconnect):
            for _ in range(MAX_TERMINAL_FRAMES):
                term.receive_bytes()
