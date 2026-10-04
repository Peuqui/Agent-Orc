"""End-to-end tests of the HTTP API with a real tmux server and a throwaway home."""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from agent_orc.api import BUILD_ID_FILE, BUILD_ID_HEADER, create_app
from agent_orc.auth import new_credentials
from agent_orc.config import Config, default_config_text
from agent_orc.context import store_activity, store_status
from agent_orc.history import claude_project_dir
from agent_orc.sessions import SESSION_ENV
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
        "sleeper": {
            "label": "Sleeper",
            "start": ["sleep", "60"],
            "resume": ["true"],
            "effort": {"levels": ["low", "high"], "store": "claude_project"},
        },
        "talker": {
            "label": "Talker",
            "start": ["sleep", "60"],
            "resume": ["sleep", "61"],
            "conversations": {
                "source": "claude",
                "resume": ["sh", "-c", "echo resumed {conversation}; sleep 60"],
            },
        },
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

    start = {
        "profile": "sleeper",
        "path": str(demo),
        "resume": False,
        "effort": None,
        "conversation": None,
    }
    session = client.post("/api/sessions", json=start)
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
    body = {
        "profile": "sleeper",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "conversation": None,
    }
    assert client.post("/api/sessions", json=body).status_code == 200
    assert client.post("/api/sessions", json=body).status_code == 409


def test_unknown_profile_and_missing_folder(client: TestClient, home: Path) -> None:
    base = {"path": str(home / "projects"), "resume": False, "effort": None, "conversation": None}
    unknown = {**base, "profile": "nope"}
    assert client.post("/api/sessions", json=unknown).status_code == 404
    missing = {**base, "profile": "sleeper", "path": str(home / "projects" / "missing")}
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
        "/api/files/content", json={"path": path, "content": "eins", "expected_version": None}
    )
    assert created.status_code == 200
    loaded = client.get("/api/files/content", params={"path": path}).json()
    assert loaded["content"] == "eins"
    # A string: a nanosecond timestamp would lose precision as a JavaScript number.
    assert isinstance(loaded["version"], str)

    stale = str(int(loaded["version"]) - 1)
    conflict = client.put(
        "/api/files/content", json={"path": path, "content": "zwei", "expected_version": stale}
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "FileConflictError"

    saved = client.put(
        "/api/files/content",
        json={"path": path, "content": "zwei", "expected_version": loaded["version"]},
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
    (static / "index.html").write_text("<title>Agent-Orc</title>")
    (static / BUILD_ID_FILE).write_text("build-1")
    app = create_app(config, new_credentials(PASSWORD), static_dir=static, clock=clock)
    client = TestClient(app)
    page = client.get("/")
    assert "Agent-Orc" in page.text
    assert page.headers[BUILD_ID_HEADER] == "build-1"
    me = client.get("/api/me")
    assert me.status_code == 401
    # Also on API answers, which an open app keeps polling.
    assert me.headers[BUILD_ID_HEADER] == "build-1"


ORIGIN = {"origin": "http://testserver"}
MAX_TERMINAL_FRAMES = 500


def start_shell(client: TestClient, home: Path) -> str:
    body = {
        "profile": "shell",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "conversation": None,
    }
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


def test_sessions_report_model_and_context(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    start = {
        "profile": "sleeper",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    listed = client.get("/api/sessions").json()[0]
    assert listed["model"] is None and listed["context_tokens"] is None

    usage = {"input_tokens": 10, "cache_creation_input_tokens": 20, "cache_read_input_tokens": 300}
    status = {
        "model": {"display_name": "Opus 5.5 (1M context)"},
        "context_window": {"context_window_size": 1_000_000, "current_usage": usage},
    }
    store_status(session_id, status)
    listed = client.get("/api/sessions").json()[0]
    assert listed["model"] == "Opus 5.5 (1M context)"
    assert listed["context_tokens"] == 330
    assert listed["context_window"] == 1_000_000


def test_agent_knows_its_session_id(client: TestClient, home: Path, socket_name: str) -> None:
    start = {
        "profile": "sleeper",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    environment = subprocess.run(
        ["tmux", "-L", socket_name, "show-environment", "-t", f"={session_id}", SESSION_ENV],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    assert environment == f"{SESSION_ENV}={session_id}"


def test_agents_list_their_effort_levels(client: TestClient) -> None:
    agents = {agent["name"]: agent for agent in client.get("/api/agents").json()}
    assert agents["sleeper"]["effort_levels"] == ["low", "high"]
    assert agents["shell"]["effort_levels"] == []


def test_invalid_effort_is_rejected(client: TestClient, home: Path) -> None:
    body = {
        "profile": "sleeper",
        "path": str(home / "projects"),
        "resume": False,
        "effort": "max",
        "conversation": None,
    }
    response = client.post("/api/sessions", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "InvalidEffortError"


def test_effort_is_stored_in_the_project(client: TestClient, home: Path) -> None:
    folder = home / "projects"
    settings = folder / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}}))
    query = {"profile": "sleeper", "path": str(folder)}
    assert client.get("/api/effort", params=query).json() == {"effort": None}

    start = {
        "profile": "sleeper",
        "path": str(folder),
        "resume": False,
        "effort": "high",
        "conversation": None,
    }
    assert client.post("/api/sessions", json=start).status_code == 200
    assert json.loads(settings.read_text()) == {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "effortLevel": "high",
    }
    assert client.get("/api/effort", params=query).json() == {"effort": "high"}


def test_changing_effort_resumes_the_agent(
    client: TestClient, home: Path, socket_name: str
) -> None:
    folder = home / "projects"
    start = {
        "profile": "sleeper",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    change = {"effort": "low", "immediately": False}
    changed = client.post(f"/api/sessions/{session_id}/effort", json=change)
    # The agent never reported to be busy, so the change applies at once.
    assert changed.json() == {"applied": True}
    # Resumed with the profile's resume command ("true" exits at once for the test agent).
    command = subprocess.run(
        ["tmux", "-L", socket_name, "display-message", "-p", "-t", f"={session_id}:",
         "#{pane_start_command}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    assert command == "true"
    settings = json.loads((folder / ".claude" / "settings.local.json").read_text())
    assert settings == {"effortLevel": "low"}

    back = client.post(
        f"/api/sessions/{session_id}/effort", json={"effort": None, "immediately": False}
    )
    assert back.json() == {"applied": True}
    assert json.loads((folder / ".claude" / "settings.local.json").read_text()) == {}


def test_effort_for_agent_without_effort_setting(client: TestClient, home: Path) -> None:
    body = {
        "profile": "shell",
        "path": str(home / "projects"),
        "resume": False,
        "effort": "low",
        "conversation": None,
    }
    assert client.post("/api/sessions", json=body).status_code == 422
    assert not (home / "projects" / ".claude").exists()


def test_effort_change_waits_for_a_busy_agent(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    folder = home / "projects"
    start = {
        "profile": "sleeper",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    store_activity(session_id, busy=True)
    url = f"/api/sessions/{session_id}/effort"

    assert client.post(url, json={"effort": "high", "immediately": False}).json() == {
        "applied": False
    }
    listed = client.get("/api/sessions").json()[0]
    assert listed["busy"] is True
    assert (listed["effort_pending"], listed["pending_effort"]) == (True, "high")
    assert not (folder / ".claude" / "settings.local.json").exists()

    # A wrong level is refused right away, not only when the change would be applied.
    wrong = client.post(url, json={"effort": "ultra", "immediately": False})
    assert wrong.status_code == 422

    assert client.delete(url).status_code == 204
    assert client.get("/api/sessions").json()[0]["effort_pending"] is False

    # "Immediately" ignores the busy state on purpose.
    assert client.post(url, json={"effort": "high", "immediately": True}).json() == {
        "applied": True
    }
    assert json.loads((folder / ".claude" / "settings.local.json").read_text()) == {
        "effortLevel": "high"
    }


def test_pending_effort_applies_when_the_agent_is_done(
    config: Config, clock: FakeClock, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    monkeypatch.setattr("agent_orc.api.PENDING_EFFORT_CHECK_SECONDS", 0.1)
    folder = home / "projects"
    # The context manager runs the app's lifespan, i.e. the background watcher.
    with TestClient(
        create_app(config, new_credentials(PASSWORD), static_dir=None, clock=clock)
    ) as client:
        client.post("/api/login", json={"password": PASSWORD})
        start = {
            "profile": "sleeper",
            "path": str(folder),
            "resume": False,
            "effort": None,
            "conversation": None,
        }
        session_id = client.post("/api/sessions", json=start).json()["id"]
        store_activity(session_id, busy=True)
        url = f"/api/sessions/{session_id}/effort"
        client.post(url, json={"effort": "low", "immediately": False})
        time.sleep(0.5)
        assert client.get("/api/sessions").json()[0]["effort_pending"] is True

        store_activity(session_id, busy=False)
        for _ in range(30):
            if not client.get("/api/sessions").json()[0]["effort_pending"]:
                break
            time.sleep(0.1)
        assert client.get("/api/sessions").json()[0]["effort_pending"] is False
        settings = json.loads((folder / ".claude" / "settings.local.json").read_text())
        assert settings == {"effortLevel": "low"}


def test_resume_a_chosen_earlier_conversation(
    client: TestClient, home: Path, socket_name: str
) -> None:
    folder = home / "projects"
    conversation_id = "1b0c8f2e-0000-4000-8000-00000000abcd"
    transcripts = claude_project_dir(home, folder)
    transcripts.mkdir(parents=True)
    title = {"type": "ai-title", "aiTitle": "Lander bauen"}
    (transcripts / f"{conversation_id}.jsonl").write_text(json.dumps(title) + "\n")

    query = {"profile": "talker", "path": str(folder)}
    listed = client.get("/api/conversations", params=query).json()
    assert [(c["id"], c["title"]) for c in listed] == [(conversation_id, "Lander bauen")]
    assert client.get("/api/conversations", params={**query, "profile": "shell"}).json() == []

    base = {
        "profile": "talker",
        "path": str(folder),
        "resume": True,
        "effort": None,
        "conversation": None,
    }
    unknown = client.post("/api/sessions", json={**base, "conversation": "not-there"})
    assert unknown.status_code == 404

    started = client.post("/api/sessions", json={**base, "conversation": conversation_id})
    assert started.status_code == 200
    target = f"={started.json()['id']}:"
    for _ in range(50):
        pane = subprocess.run(
            ["tmux", "-L", socket_name, "capture-pane", "-p", "-t", target],
            capture_output=True, text=True, check=True,
        ).stdout  # fmt: skip
        if conversation_id in pane:
            break
        time.sleep(0.1)
    assert f"resumed {conversation_id}" in pane


def test_session_text_for_copying(client: TestClient, home: Path) -> None:
    session_id = start_shell(client, home)
    for _ in range(50):
        text = client.get(f"/api/sessions/{session_id}/text").json()["text"]
        if "READY" in text:
            break
        time.sleep(0.1)
    assert "READY" in text
    assert client.get("/api/sessions/unknown/text").status_code == 404
