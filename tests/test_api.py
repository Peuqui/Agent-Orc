"""End-to-end tests of the HTTP API with a real tmux server and a throwaway home."""

import json
import os
import signal
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
from agent_orc.approvals import open_request, wait_for_decision
from agent_orc.auth import new_credentials
from agent_orc.config import Config, DictationConfig, default_config_text
from agent_orc.context import store_activity, store_status
from agent_orc.history import claude_project_dir
from agent_orc.schedule import mark_limited, read_scheduled
from agent_orc.sessions import SESSION_ENV
from agent_orc.terminal import WS_CLOSE_SERVICE_RESTART, attach_environment
from tests.conftest import Device, FakeClock, FakePushService, FakeWhisper

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
            "resume": ["sleep", "61"],
            "effort": {
                "levels": ["low", "high"],
                "default": "low",
                "store": "claude_project",
                "ultracode": True,
            },
            "permission": {
                "modes": ["default", "plan"],
                "default": "default",
                "store": "claude_project",
            },
        },
        # Switches its reasoning in place, like Claude with /effort.
        "switcher": {
            "label": "Switcher",
            "start": ["sleep", "60"],
            "resume": ["sleep", "61"],
            "effort": {
                "levels": ["low", "high"],
                "default": "low",
                "store": "claude_project",
                "ultracode": True,
                "live": {
                    "command": "/effort {level}",
                    "ultracode_command": "/effort ultracode {state}",
                    "protected_file": str(home / "user-settings.json"),
                },
            },
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
        "ultracode": False,
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
        "ultracode": False,
        "conversation": None,
    }
    assert client.post("/api/sessions", json=body).status_code == 200
    assert client.post("/api/sessions", json=body).status_code == 409


def test_unknown_profile_and_missing_folder(client: TestClient, home: Path) -> None:
    base = {
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
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
    # An update replaced the files while the server kept running.
    (static / BUILD_ID_FILE).write_text("build-2")
    assert client.get("/api/me").headers[BUILD_ID_HEADER] == "build-2"


ORIGIN = {"origin": "http://testserver"}
MAX_TERMINAL_FRAMES = 500


def start_shell(client: TestClient, folder: Path) -> str:
    folder.mkdir(exist_ok=True)
    body = {
        "profile": "shell",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
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


START_COLS = 90
START_ROWS = 25


def terminal_url(session_id: str) -> str:
    return f"/api/sessions/{session_id}/terminal?cols={START_COLS}&rows={START_ROWS}"


def refused_code(client: TestClient, session_id: str, headers: dict[str, str]) -> int:
    url = terminal_url(session_id)
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
    session_id = start_shell(anonymous, home / "projects")
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
    session_id = start_shell(client, home / "projects")
    with client.websocket_connect(terminal_url(session_id), headers=ORIGIN) as term:
        read_until(term, "READY")
        # Attached at the size the browser sent along, before any resize message.
        assert tmux_client_size(socket_name) == f"{START_COLS}x{START_ROWS}"
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


def test_tmux_client_does_not_inherit_tmux(monkeypatch: pytest.MonkeyPatch) -> None:
    # Started by hand in a tmux window, the server inherits TMUX; passed on, tmux may take the
    # attach for nesting and refuse it (depends on reused PTY numbers, so checked directly).
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
    environment = attach_environment()
    assert "TMUX" not in environment
    assert environment["TERM"] == "xterm-256color"


def test_terminal_closes_when_session_stops(client: TestClient, home: Path) -> None:
    session_id = start_shell(client, home / "projects")
    with client.websocket_connect(terminal_url(session_id), headers=ORIGIN) as term:
        read_until(term, "READY")
        client.delete(f"/api/sessions/{session_id}")
        with pytest.raises(WebSocketDisconnect) as closed:
            for _ in range(MAX_TERMINAL_FRAMES):
                term.receive_bytes()
    # A normal close: the browser offers to reconnect but does not try by itself.
    assert closed.value.code == 1000


def test_terminal_of_a_running_agent_asks_to_reconnect(
    client: TestClient, home: Path, socket_name: str
) -> None:
    session_id = start_shell(client, home / "projects")
    with client.websocket_connect(terminal_url(session_id), headers=ORIGIN) as term:
        read_until(term, "READY")
        # The tmux client ends while its session lives on, as when Agent-Orc is restarted.
        client_pid = subprocess.run(
            ["tmux", "-L", socket_name, "list-clients", "-F", "#{client_pid}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip
        os.kill(int(client_pid), signal.SIGTERM)
        with pytest.raises(WebSocketDisconnect) as closed:
            for _ in range(MAX_TERMINAL_FRAMES):
                term.receive_bytes()
    assert closed.value.code == WS_CLOSE_SERVICE_RESTART
    assert client.get("/api/sessions").json()[0]["running"] is True


def test_sessions_report_model_and_context(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    start = {
        "profile": "sleeper",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "ultracode": False,
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
        "ultracode": False,
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
        "ultracode": False,
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
    # A folder without a level of its own shows the configured one.
    assert client.get("/api/effort", params=query).json() == {"effort": "low", "ultracode": False}

    start = {
        "profile": "sleeper",
        "path": str(folder),
        "resume": False,
        "effort": "high",
        "ultracode": False,
        "conversation": None,
    }
    assert client.post("/api/sessions", json=start).status_code == 200
    assert json.loads(settings.read_text()) == {
        "permissions": {"allow": ["Bash(ls:*)"], "defaultMode": "default"},
        "effortLevel": "high",
    }
    assert client.get("/api/effort", params=query).json() == {"effort": "high", "ultracode": False}


def test_changing_effort_resumes_the_agent(
    client: TestClient, home: Path, socket_name: str
) -> None:
    folder = home / "projects"
    start = {
        "profile": "sleeper",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    change = {"effort": "low", "ultracode": True, "immediately": False}
    with client.websocket_connect(terminal_url(session_id), headers=ORIGIN):
        changed = client.post(f"/api/sessions/{session_id}/effort", json=change)
        # Restarted in its own session: the open terminal stays attached to the same id.
        assert tmux_client_size(socket_name) == f"{START_COLS}x{START_ROWS}"
    # The agent never reported to be busy, so the change applies at once.
    assert changed.json() == {"applied": True}
    assert [s["id"] for s in client.get("/api/sessions").json()] == [session_id]
    # Resumed with the profile's resume command, still running like a real agent.
    command = subprocess.run(
        ["tmux", "-L", socket_name, "display-message", "-p", "-t", f"={session_id}:",
         "#{pane_start_command}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    assert command == "sleep 61"
    settings = json.loads((folder / ".claude" / "settings.local.json").read_text())
    assert settings == {
        "effortLevel": "low",
        "ultracode": True,
        "permissions": {"defaultMode": "default"},
    }
    assert client.get("/api/sessions").json()[0]["ultracode"] is True

    # There is no "agent's own default" any more: an agent with levels always has one.
    refused = client.post(
        f"/api/sessions/{session_id}/effort",
        json={"effort": None, "ultracode": False, "immediately": False},
    )
    assert refused.status_code == 422


def test_effort_for_agent_without_effort_setting(client: TestClient, home: Path) -> None:
    body = {
        "profile": "shell",
        "path": str(home / "projects"),
        "resume": False,
        "effort": "low",
        "ultracode": False,
        "conversation": None,
    }
    assert client.post("/api/sessions", json=body).status_code == 422
    assert not (home / "projects" / ".claude").exists()


def test_reasoning_switches_in_place_without_restart(
    client: TestClient, home: Path, socket_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("agent_orc.effort.PROTECT_SECONDS", 0.3)
    start = {
        "profile": "switcher",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    target = f"={session_id}:"

    def pane(field: str) -> str:
        return subprocess.run(
            ["tmux", "-L", socket_name, "display-message", "-p", "-t", target, field],
            capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip

    process = pane("#{pane_pid}")
    url = f"/api/sessions/{session_id}/effort"
    store_activity(session_id, busy=True)
    # A busy agent waits for the end of its answer, even when asked to switch now.
    now = {"effort": "high", "ultracode": True, "immediately": True}
    assert client.post(url, json=now).json() == {"applied": False}
    store_activity(session_id, busy=False)
    assert client.post(url, json=now).json() == {"applied": True}
    # Typed into the running agent (the terminal echoes it), which keeps running.
    screen = subprocess.run(
        ["tmux", "-L", socket_name, "capture-pane", "-p", "-t", target],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    assert "/effort high" in screen
    assert "/effort ultracode on" in screen
    assert pane("#{pane_pid}") == process
    agents = {agent["name"]: agent for agent in client.get("/api/agents").json()}
    assert agents["switcher"]["effort_live"] is True
    assert agents["sleeper"]["effort_live"] is False


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
        "ultracode": False,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    store_activity(session_id, busy=True)
    url = f"/api/sessions/{session_id}/effort"

    assert client.post(
        url, json={"effort": "high", "ultracode": False, "immediately": False}
    ).json() == {"applied": False}
    listed = client.get("/api/sessions").json()[0]
    assert listed["busy"] is True
    assert (listed["effort_pending"], listed["pending_effort"]) == (True, "high")
    # Not applied yet: the folder keeps the level it started with.
    stored = json.loads((folder / ".claude" / "settings.local.json").read_text())
    assert stored["effortLevel"] == "low"

    # A wrong level is refused right away, not only when the change would be applied.
    wrong = client.post(url, json={"effort": "ultra", "ultracode": False, "immediately": False})
    assert wrong.status_code == 422

    assert client.delete(url).status_code == 204
    assert client.get("/api/sessions").json()[0]["effort_pending"] is False

    # "Immediately" ignores the busy state on purpose.
    assert client.post(
        url, json={"effort": "high", "ultracode": False, "immediately": True}
    ).json() == {"applied": True}
    assert json.loads((folder / ".claude" / "settings.local.json").read_text()) == {
        "permissions": {"defaultMode": "default"},
        "effortLevel": "high",
    }


def test_restart_resumes_a_busy_agent_with_its_waiting_effort(
    client: TestClient, home: Path, socket_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    folder = home / "projects"
    start = {
        "profile": "sleeper",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    store_activity(session_id, busy=True)
    change = {"effort": "high", "ultracode": False, "immediately": False}
    assert client.post(f"/api/sessions/{session_id}/effort", json=change).json() == {
        "applied": False
    }
    with client.websocket_connect(terminal_url(session_id), headers=ORIGIN):
        restarted = client.post(f"/api/sessions/{session_id}/restart")
        # Restarted in its own session: the open terminal stays attached to the same id.
        assert tmux_client_size(socket_name) == f"{START_COLS}x{START_ROWS}"
    assert restarted.json()["id"] == session_id
    command = subprocess.run(
        ["tmux", "-L", socket_name, "display-message", "-p", "-t", f"={session_id}:",
         "#{pane_start_command}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    assert command == "sleep 61"
    listed = client.get("/api/sessions").json()[0]
    assert (listed["busy"], listed["effort_pending"]) == (False, False)
    stored = json.loads((folder / ".claude" / "settings.local.json").read_text())
    assert stored["effortLevel"] == "high"

    assert client.post("/api/sessions/unknown/restart").status_code == 404


def test_pending_effort_applies_when_the_agent_is_done(
    config: Config, clock: FakeClock, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    monkeypatch.setattr("agent_orc.api.AGENT_CHECK_SECONDS", 0.1)
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
            "ultracode": False,
            "conversation": None,
        }
        session_id = client.post("/api/sessions", json=start).json()["id"]
        store_activity(session_id, busy=True)
        url = f"/api/sessions/{session_id}/effort"
        client.post(url, json={"effort": "low", "ultracode": False, "immediately": False})
        time.sleep(0.5)
        assert client.get("/api/sessions").json()[0]["effort_pending"] is True

        store_activity(session_id, busy=False)
        for _ in range(30):
            if not client.get("/api/sessions").json()[0]["effort_pending"]:
                break
            time.sleep(0.1)
        assert client.get("/api/sessions").json()[0]["effort_pending"] is False
        settings = json.loads((folder / ".claude" / "settings.local.json").read_text())
        assert settings == {"permissions": {"defaultMode": "default"}, "effortLevel": "low"}


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
        "ultracode": False,
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
    session_id = start_shell(client, home / "projects")
    for _ in range(50):
        text = client.get(f"/api/sessions/{session_id}/text").json()["text"]
        if "READY" in text:
            break
        time.sleep(0.1)
    assert "READY" in text
    assert client.get("/api/sessions/unknown/text").status_code == 404


def test_dictation(config: Config, clock: FakeClock, fake_whisper: FakeWhisper) -> None:
    dictation = DictationConfig(whisper_url=fake_whisper.url, language="de", timeout_seconds=5)
    app = create_app(
        config.model_copy(update={"dictation": dictation}),
        new_credentials(PASSWORD),
        static_dir=None,
        clock=clock,
    )
    client = TestClient(app)

    def dictate(device: str) -> Any:
        return client.post(
            f"/api/dictation?device={device}",
            content=b"opus",
            headers={"Content-Type": "audio/webm"},
        )

    assert dictate("cpu").status_code == 401
    client.post("/api/login", json={"password": PASSWORD})
    assert client.get("/api/dictation").json() == {
        "language": "de",
        "whisper": True,
        "engines": ["whisper", "parakeet"],
    }
    assert dictate("cpu").json() == {"text": "Hallo Welt"}
    assert dictate("cpu&engine=parakeet").json() == {"text": "Hallo Welt"}
    assert b'name="engine"\r\n\r\nparakeet' in fake_whisper.bodies[-1]
    assert dictate("tpu").status_code == 422
    fake_whisper.status = 503
    fake_whisper.answer = {"error": "no GPU with enough VRAM"}
    full = dictate("cuda")
    assert full.status_code == 503
    assert full.json()["error"] == "GpuUnavailableError"


def test_quota_per_reporting_profile(
    config: Config, clock: FakeClock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    reporting = config.agents["sleeper"].model_copy(update={"quota": "claude"})
    agents = {**config.agents, "sleeper": reporting}
    app = create_app(
        config.model_copy(update={"agents": agents}),
        new_credentials(PASSWORD),
        static_dir=None,
        clock=clock,
    )
    client = TestClient(app)
    client.post("/api/login", json={"password": PASSWORD})
    assert client.get("/api/quota").json() == [
        {"profile": "sleeper", "label": "Sleeper", "windows": {}}
    ]
    limits = {"seven_day": {"used_percentage": 39, "resets_at": 1791554400}}
    store_status("x-1", {"model": {"display_name": "M"}, "rate_limits": limits})
    assert client.get("/api/quota").json()[0]["windows"] == limits


def test_ultracode_only_for_agents_offering_it(client: TestClient, home: Path) -> None:
    agents = {agent["name"]: agent for agent in client.get("/api/agents").json()}
    assert (agents["sleeper"]["ultracode"], agents["talker"]["ultracode"]) == (True, False)
    start = {
        "profile": "talker",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "ultracode": True,
        "conversation": None,
    }
    refused = client.post("/api/sessions", json=start)
    assert refused.status_code == 422
    assert refused.json()["error"] == "InvalidEffortError"


def test_permission_mode_is_stored_for_the_folder(client: TestClient, home: Path) -> None:
    body = {
        "profile": "sleeper",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=body).json()["id"]
    agents = {agent["name"]: agent for agent in client.get("/api/agents").json()}
    assert agents["sleeper"]["permission_modes"] == ["default", "plan"]
    # A folder without a mode of its own starts in the configured default.
    assert client.get("/api/sessions").json()[0]["permission_mode"] == "default"
    url = f"/api/sessions/{session_id}/permission-mode"
    assert client.put(url, json={"mode": "plan"}).status_code == 204
    assert client.get("/api/sessions").json()[0]["permission_mode"] == "plan"
    settings = json.loads((home / "projects/.claude/settings.local.json").read_text())
    assert settings["permissions"] == {"defaultMode": "plan"}
    refused = client.put(url, json={"mode": "bypassPermissions"})
    assert refused.status_code == 422
    assert refused.json()["error"] == "InvalidPermissionModeError"


def test_permission_request_is_answered_from_the_card(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    session_id = start_shell(client, home / "projects")
    hook = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
    request = open_request(session_id, hook)
    listed = client.get("/api/sessions").json()[0]["approvals"]
    assert [(a["id"], a["tool"], a["subject"]) for a in listed] == [
        (request.id, "Bash", "git push")
    ]
    url = f"/api/sessions/{session_id}/approval"
    assert client.post(url, json={"request": "other", "allow": True}).status_code == 404
    assert client.post(url, json={"request": request.id, "allow": False}).status_code == 204
    assert wait_for_decision(request.id) is False


def test_changes_of_an_agents_project(client: TestClient, home: Path) -> None:
    folder = home / "projects"
    for arguments in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "start"]):
        subprocess.run(
            ["git", "-C", str(folder), "-c", "user.name=T", "-c", "user.email=t@e.org", *arguments],
            check=True,
        )
    (folder / "plan.md").write_text("# Plan\n")
    session_id = start_shell(client, home / "projects")
    assert client.get(f"/api/sessions/{session_id}/changes").json() == [
        {"path": "plan.md", "status": "??"}
    ]
    diff = client.get(f"/api/sessions/{session_id}/changes/diff", params={"path": "plan.md"})
    assert diff.json() == {"text": "+# Plan\n", "truncated": False}
    other = client.get(f"/api/sessions/{session_id}/changes/diff", params={"path": "x"})
    assert other.status_code == 404


def report_context(session_id: str, tokens: int) -> None:
    store_status(
        session_id,
        {
            "model": {"display_name": "Opus"},
            "context_window": {
                "context_window_size": 1000,
                "current_usage": {"input_tokens": tokens},
            },
        },
    )


def test_handover_is_advised_from_the_threshold_on(
    client: TestClient, home: Path, socket_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    session_id = start_shell(client, home / "projects")
    report_context(session_id, 400)
    assert client.get("/api/sessions").json()[0]["handover"] == {
        "recommended": False,
        "cache_cold": False,
    }
    report_context(session_id, 600)
    store_activity(session_id, busy=False)
    assert client.get("/api/sessions").json()[0]["handover"] == {
        "recommended": True,
        "cache_cold": False,
    }
    # Two hours later, idle for longer than the cache lasts.
    later = time.time() + 2 * 3600
    monkeypatch.setattr("agent_orc.handover.time.time", lambda: later)
    assert client.get("/api/sessions").json()[0]["handover"]["cache_cold"] is True

    assert client.post(f"/api/sessions/{session_id}/handover").status_code == 204
    screen = subprocess.run(
        ["tmux", "-L", socket_name, "capture-pane", "-p", "-t", f"={session_id}:"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    assert "handover document" in screen


def test_automatic_handover_setting_is_kept(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    assert client.get("/api/handover/auto").json() == {"auto": False}
    assert client.put("/api/handover/auto", json={"auto": True}).status_code == 204
    assert client.get("/api/handover/auto").json() == {"auto": True}


def test_push_subscription_and_test_message(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    push_service: FakePushService,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert len(client.get("/api/push/key").json()["key"]) == 87
    phone = Device(f"{push_service.url}/phone")
    assert client.post("/api/push/subscriptions", json=phone.subscription).status_code == 204
    assert client.post("/api/push/test").json() == {"delivered": 1}
    assert phone.decrypt(push_service.received[0][2])["kind"] == "test"
    unsubscribe = client.delete("/api/push/subscriptions", params={"endpoint": phone.endpoint})
    assert unsubscribe.status_code == 204
    assert client.post("/api/push/test").json() == {"delivered": 0}


def test_agent_in_its_own_worktree(client: TestClient, home: Path) -> None:
    folder = home / "projects" / "app"
    folder.mkdir()
    for arguments in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "start"]):
        subprocess.run(
            ["git", "-C", str(folder), "-c", "user.name=T", "-c", "user.email=t@e.org", *arguments],
            check=True,
        )
    body = {
        "profile": "shell",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
        "worktree": "fix-xy",
    }
    started = client.post("/api/sessions", json=body).json()
    assert started["path"] == str(home / "projects" / "app.worktrees" / "fix-xy")
    [listed] = client.get("/api/sessions").json()
    assert listed["worktree"] is True
    # A running agent keeps its worktree.
    refused = client.post(f"/api/sessions/{started['id']}/remove-worktree")
    assert refused.status_code == 409
    bad = client.post("/api/sessions", json={**body, "worktree": "no spaces"})
    assert bad.status_code == 422
    # The base folder itself as the project: its worktree would leave the scope.
    subprocess.run(["git", "-C", str(home / "projects"), "init", "-q"], check=True)
    outside = client.post(
        "/api/sessions", json={**body, "path": str(home / "projects"), "worktree": "y"}
    )
    assert outside.status_code == 403
    assert not (home / "projects.worktrees").exists()


def test_prompt_templates_are_kept(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert client.get("/api/prompt-templates").json() == []
    templates = [{"label": "Tests", "text": "Run the tests and fix what fails."}]
    assert client.put("/api/prompt-templates", json=templates).status_code == 204
    assert client.get("/api/prompt-templates").json() == templates


def test_card_order_is_kept(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert client.get("/api/card-order").json() == []
    order = {"folders": ["/w/b", "/w/a"]}
    assert client.put("/api/card-order", json=order).status_code == 204
    assert client.get("/api/card-order").json() == ["/w/b", "/w/a"]


def test_named_workspaces_are_kept_and_deleted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert client.get("/api/workspaces").json() == {}
    left = {"tabs": ["a", "b"], "visible": 2, "widths": {"a": 0.3}, "active": "b"}
    assert client.put("/api/workspaces/Links", json=left).status_code == 204
    right = {"tabs": [], "visible": 1, "widths": {}, "active": None}
    assert client.put("/api/workspaces/Rechts", json=right).status_code == 204
    assert client.get("/api/workspaces").json() == {"Links": left, "Rechts": right}
    assert client.delete("/api/workspaces/Links").status_code == 204
    assert client.get("/api/workspaces").json() == {"Rechts": right}


def test_attachment_lands_in_the_agents_folder(client: TestClient, home: Path) -> None:
    session_id = start_shell(client, home / "projects")
    response = client.post(
        f"/api/sessions/{session_id}/attachments",
        params={"name": "foto.jpg"},
        content=b"jpeg",
        headers={"Content-Type": "image/jpeg"},
    )
    relative = response.json()["path"]
    assert relative.startswith(".agent-orc/uploads/")
    assert (home / "projects" / relative).read_bytes() == b"jpeg"
    missing = client.post("/api/sessions/nope/attachments", params={"name": "a"}, content=b"")
    assert missing.status_code == 404


def wait_for_text(client: TestClient, session_id: str, text: str) -> bool:
    for _ in range(50):
        if text in client.get(f"/api/sessions/{session_id}/text").json()["text"]:
            return True
        time.sleep(0.1)
    return False


def test_scheduled_prompt_waits_for_its_time_and_an_idle_agent(
    config: Config, clock: FakeClock, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    monkeypatch.setattr("agent_orc.api.AGENT_CHECK_SECONDS", 0.1)
    with TestClient(
        create_app(config, new_credentials(PASSWORD), static_dir=None, clock=clock)
    ) as client:
        client.post("/api/login", json={"password": PASSWORD})
        session_id = start_shell(client, home / "projects" / "a")
        assert wait_for_text(client, session_id, "READY")
        url = f"/api/sessions/{session_id}/scheduled"
        planned = client.post(url, json={"text": "later please", "at": clock.now + 60}).json()
        assert planned["reason"] == "user"
        listed = client.get("/api/sessions").json()[0]["scheduled"]
        assert [p["text"] for p in listed] == ["later please"]
        time.sleep(0.5)
        assert "later please" not in client.get(f"/api/sessions/{session_id}/text").json()["text"]

        # Due, but the agent is working: it waits for the end of the answer.
        store_activity(session_id, busy=True)
        clock.advance(61)
        time.sleep(0.5)
        assert client.get("/api/sessions").json()[0]["scheduled"] != []
        store_activity(session_id, busy=False)
        assert wait_for_text(client, session_id, "later please")
        assert client.get("/api/sessions").json()[0]["scheduled"] == []

        # Removed before it is due: never typed.
        removed = client.post(url, json={"text": "never", "at": clock.now + 60}).json()
        assert client.delete(f"/api/scheduled/{removed['id']}").status_code == 204
        assert client.delete(f"/api/scheduled/{removed['id']}").status_code == 404
        assert (
            client.post("/api/sessions/unknown/scheduled", json={"text": "x", "at": 0}).status_code
            == 404
        )


def test_agent_stopped_by_its_limit_resumes_after_the_reset(
    config: Config, clock: FakeClock, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    monkeypatch.setattr("agent_orc.api.AGENT_CHECK_SECONDS", 0.1)
    shell = config.agents["shell"].model_copy(update={"quota": "claude"})
    limited_config = config.model_copy(update={"agents": {**config.agents, "shell": shell}})
    with TestClient(
        create_app(limited_config, new_credentials(PASSWORD), static_dir=None, clock=clock)
    ) as client:
        client.post("/api/login", json={"password": PASSWORD})
        session_id = start_shell(client, home / "projects" / "a")
        assert wait_for_text(client, session_id, "READY")
        reset = clock.now + 3600
        store_status(
            session_id,
            {
                "model": {"display_name": "Opus"},
                "rate_limits": {
                    "five_hour": {"used_percentage": 100, "resets_at": reset},
                    "seven_day": {"used_percentage": 50, "resets_at": reset + 86400},
                },
            },
        )
        # What the StopFailure hook (agent-orc agent-limited) leaves behind.
        mark_limited(session_id)
        for _ in range(30):
            planned = client.get("/api/sessions").json()[0]["scheduled"]
            if planned:
                break
            time.sleep(0.1)
        resume = config.limit_resume
        assert [(p["reason"], p["text"], p["at"]) for p in planned] == [
            ("limit", resume.prompt, reset + resume.delay_seconds)
        ]
        clock.advance(3600 + resume.delay_seconds)
        assert wait_for_text(client, session_id, resume.prompt)

        # Stopping the agent drops what it still had planned.
        client.post(f"/api/sessions/{session_id}/scheduled", json={"text": "x", "at": 0})
        client.delete(f"/api/sessions/{session_id}")
        assert client.get("/api/sessions").json() == []
        assert read_scheduled() == []


def test_broadcast_types_into_every_chosen_agent(client: TestClient, home: Path) -> None:
    first = start_shell(client, home / "projects" / "a")
    assert wait_for_text(client, first, "READY")
    second = start_shell(client, home / "projects" / "b")
    assert wait_for_text(client, second, "READY")
    response = client.post(
        "/api/broadcast", json={"sessions": [first, second], "text": "commit and push"}
    )
    assert response.status_code == 204
    assert wait_for_text(client, first, "commit and push")
    assert wait_for_text(client, second, "commit and push")
    # An unknown agent is refused before anything is typed.
    refused = client.post("/api/broadcast", json={"sessions": [first, "gone"], "text": "nope"})
    assert refused.status_code == 404
    time.sleep(0.3)
    assert "nope" not in client.get(f"/api/sessions/{first}/text").json()["text"]
