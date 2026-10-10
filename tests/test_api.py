"""End-to-end tests of the HTTP API with a real tmux server and a throwaway home."""

import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import uvicorn
import yaml
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from agent_orc.api import BUILD_ID_FILE, BUILD_ID_HEADER, create_app
from agent_orc.approvals import open_request, wait_for_decision
from agent_orc.auth import new_credentials
from agent_orc.config import Config, DictationConfig, HostConfig, ServerConfig, default_config_text
from agent_orc.context import store_activity, store_status
from agent_orc.effort import agent_settings_file
from agent_orc.events import ChangeNotifier
from agent_orc.handover import write_auto
from agent_orc.history import claude_project_dir
from agent_orc.listen import prepare_socket
from agent_orc.schedule import mark_limited, read_scheduled
from agent_orc.sessions import SESSION_ENV
from agent_orc.state import state_dir
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
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    return home


# Asks for a confirmation after "/model ...", as Claude does for a conversation with content.
SWAPPER_SCRIPT = (
    'echo "{start}"; while read line; do case "$line" in '
    '/model*) echo "Switch model?"; read answer; echo "confirmed";; esac; done'
)


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
            "settings": {},
            "effort": {
                "levels": ["low", "high"],
                "default": "low",
                "ultracode": True,
            },
            "permission": {
                "modes": ["default", "plan"],
                "default": "default",
            },
        },
        # Switches its reasoning in place, like Claude with /effort.
        "switcher": {
            "label": "Switcher",
            "start": ["sleep", "60"],
            "resume": ["sleep", "61"],
            "settings": {},
            "effort": {
                "levels": ["low", "high"],
                "default": "low",
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
        # Two models with different levels: "wide" takes low/high/max, "narrow" low/medium only.
        "narrow": {
            "label": "Narrow",
            "models": ["printf", "wide\\nnarrow\\n"],
            "start": ["sh", "-c", "echo started {model}; exec cat"],
            "resume": ["sh", "-c", "echo resumed {model}; exec cat"],
            "settings": {},
            "effort": {
                "levels": ["low", "medium", "high", "max"],
                "default": "high",
                "levels_command": [
                    "sh",
                    "-c",
                    "[ {model} = wide ] && echo low high max || echo low medium",
                ],
            },
        },
        # Keeps its conversations where "talker" does: switching between them resumes.
        "talker_too": {
            "label": "Talker too",
            "start": ["sleep", "63"],
            "resume": ["sleep", "62"],
            "conversations": {"source": "claude", "resume": ["sleep", "64"]},
        },
        # Offers models, "thinker" with a note: it takes two levels, "plain" none (lclaude --levels)
        "chooser": {
            "label": "Chooser",
            "hint": "Stop the other model first.",
            "models": ["printf", "thinker\\tfree until Friday\\nplain\\n"],
            "start": ["sh", "-c", 'echo "started {model} [$ORC_EFFORT]"; exec cat'],
            "resume": ["sh", "-c", 'echo "resumed {model} [$ORC_EFFORT]"; exec cat'],
            "env": {"ORC_EFFORT": "{effort}"},
            "settings": {},
            "effort": {
                "levels": ["low", "medium", "high"],
                "default": "medium",
                "levels_command": ["sh", "-c", "[ {model} = thinker ] && echo low high || true"],
            },
        },
        # Like "chooser", but switches its model in place, like Claude with /model.
        "swapper": {
            "label": "Swapper",
            "models": ["printf", "thinker\\nplain\\n"],
            "start": ["sh", "-c", SWAPPER_SCRIPT.replace("{start}", "started {model}")],
            "resume": ["sh", "-c", 'echo "resumed {model}"; exec cat'],
            "clear_command": "/clear",
            "compact_command": "/compact",
            "model_live": {
                "command": "/model {model}",
                "confirm": "Switch model?",
                "protected_file": str(home / "user-settings.json"),
            },
        },
        # Shows its name and the suffix it got in its environment ("none" for a folder's first).
        "named": {
            "label": "Named",
            "start": ["sh", "-c", 'echo "named {name} [${ORC_SUFFIX-none}]"; exec cat'],
            "resume": ["true"],
            "env": {"ORC_SUFFIX": "{suffix}"},
        },
        "shell": {
            "label": "Shell",
            "start": ["sh", "-c", "echo READY; exec cat"],
            "resume": ["true"],
            "terminal": True,
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
        ("GET", "/api/conversations/all"),
        ("POST", "/api/conversations/delete"),
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


def test_the_base_directory_is_set_in_the_app_and_kept(
    client: TestClient, home: Path, config: Config, clock: FakeClock
) -> None:
    assert client.get("/api/scope").json()["password_required"] is True
    new = {"path": str(home / "private"), "password": PASSWORD}
    assert client.put("/api/scope/base-dir", json={**new, "password": "wrong"}).status_code == 401
    # No folder, or none in the home directory, cannot be it.
    assert (
        client.put("/api/scope/base-dir", json={**new, "path": str(home / "none")}).status_code
        == 422
    )
    assert client.put("/api/scope/base-dir", json={**new, "path": "/etc"}).status_code == 422
    assert client.get("/api/scope").json()["base_dir"] == str(home / "projects")

    changed = client.put("/api/scope/base-dir", json=new).json()
    assert changed["base_dir"] == str(home / "private")
    assert client.get("/api/files", params={"path": str(home / "projects")}).status_code == 403

    # A restart reads it from the state, not from the config.
    restarted = TestClient(
        create_app(config, new_credentials(PASSWORD), static_dir=None, clock=clock)
    )
    restarted.post("/api/login", json={"password": PASSWORD})
    assert restarted.get("/api/scope").json()["base_dir"] == str(home / "private")


def test_on_a_socket_the_base_directory_needs_no_password(trusted: TestClient, home: Path) -> None:
    assert trusted.get("/api/scope").json()["password_required"] is False
    changed = trusted.put(
        "/api/scope/base-dir", json={"path": str(home / "private"), "password": ""}
    )
    assert changed.json()["base_dir"] == str(home / "private")


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


def test_a_file_is_uploaded_and_a_taken_name_gets_a_number(client: TestClient, home: Path) -> None:
    folder = home / "projects"
    params = {"folder": str(folder), "name": "Aufnahme 1.wav"}
    first = client.post("/api/files/upload", params=params, content=b"eins")
    second = client.post("/api/files/upload", params=params, content=b"zwei")
    assert first.status_code == second.status_code == 200
    # The name stays as it is; the second one does not overwrite the first.
    assert Path(first.json()["path"]) == folder / "Aufnahme 1.wav"
    assert Path(second.json()["path"]) == folder / "Aufnahme 1-2.wav"
    assert (folder / "Aufnahme 1.wav").read_bytes() == b"eins"
    assert (folder / "Aufnahme 1-2.wav").read_bytes() == b"zwei"
    # A path in the name does not leave the folder.
    sneaky = client.post(
        "/api/files/upload", params={"folder": str(folder), "name": "../../x.txt"}, content=b"x"
    )
    assert Path(sneaky.json()["path"]) == folder / "x.txt"
    # Without the login it is refused (a client of its own: this one's cookie is the login).
    stranger = TestClient(client.app)
    assert stranger.post("/api/files/upload", params=params, content=b"x").status_code == 401


def test_an_upload_goes_through_the_other_machines_app_without_being_held(
    mini: TestClient, home: Path
) -> None:
    folder = home / "projects"

    def chunks() -> Iterator[bytes]:
        # No length is known: the body is handed on in chunks.
        for number in range(8):
            yield bytes([number]) * 100_000

    params = {"folder": str(folder), "name": ".env local"}
    unknown_length = mini.post("/hosts/Aragon/api/files/upload", params=params, content=chunks())
    known_length = mini.post("/hosts/Aragon/api/files/upload", params=params, content=b"x" * 5)
    assert unknown_length.status_code == known_length.status_code == 200
    assert Path(unknown_length.json()["path"]) == folder / ".env local"
    assert (folder / ".env local").stat().st_size == 800_000
    assert (folder / ".env local-2").read_bytes() == b"x" * 5


def test_a_dropped_folder_keeps_its_structure(
    client: TestClient, home: Path, tmp_path: Path
) -> None:
    folder = home / "projects"
    params = {"folder": str(folder), "name": "main.py", "subfolder": "proj/src/app"}
    stored = client.post("/api/files/upload", params=params, content=b"print()")
    assert Path(stored.json()["path"]) == folder / "proj" / "src" / "app" / "main.py"
    assert (folder / "proj" / "src" / "app" / "main.py").read_bytes() == b"print()"
    # Into the same folder again: the file gets a number, the folder is not replaced.
    again = client.post("/api/files/upload", params=params, content=b"neu")
    assert Path(again.json()["path"]).name == "main-2.py"
    # Neither ".." nor a link that leads out of the scope.
    up = {"folder": str(folder), "name": "x", "subfolder": "proj/../.."}
    assert client.post("/api/files/upload", params=up, content=b"x").status_code == 422
    (folder / "link").symlink_to(tmp_path)
    out = {"folder": str(folder), "name": "x", "subfolder": "link"}
    assert client.post("/api/files/upload", params=out, content=b"x").status_code == 403
    assert not (tmp_path / "x").exists()


def test_umlauts_and_spaces_in_an_uploaded_name_stay(client: TestClient, home: Path) -> None:
    folder = home / "projects"
    for name in ("Erzählerin.mp3", "Ärger Übung ß.mp3"):
        stored = client.post(
            "/api/files/upload", params={"folder": str(folder), "name": name}, content=b"x"
        )
        assert Path(stored.json()["path"]).name == name
        assert (folder / name).read_bytes() == b"x"


def test_files_are_moved_and_copied_into_a_folder(client: TestClient, home: Path) -> None:
    projects = home / "projects"
    (projects / "ziel").mkdir()
    (projects / "a.txt").write_text("a")
    (projects / "b.txt").write_text("b")
    moved = client.post(
        "/api/files/transfer",
        json={"paths": [str(projects / "a.txt")], "folder": str(projects / "ziel")},
    )
    assert moved.json() == {"paths": [str(projects / "ziel" / "a.txt")]}
    assert not (projects / "a.txt").exists()
    copied = client.post(
        "/api/files/transfer",
        json={
            "paths": [str(projects / "b.txt")],
            "folder": str(projects / "ziel"),
            "as_copy": True,
        },
    )
    assert copied.status_code == 200
    assert (projects / "b.txt").exists() and (projects / "ziel" / "b.txt").exists()
    # A folder into itself, and into a file, are refused.
    inside = client.post(
        "/api/files/transfer",
        json={"paths": [str(projects / "ziel")], "folder": str(projects / "ziel")},
    )
    assert inside.status_code == 422
    not_a_folder = client.post(
        "/api/files/transfer",
        json={"paths": [str(projects / "b.txt")], "folder": str(projects / "b.txt")},
    )
    assert not_a_folder.status_code == 400


def test_the_base_folder_and_what_is_outside_the_scope_are_not_moved(
    client: TestClient, home: Path
) -> None:
    (home / "projects" / "ziel").mkdir()
    base = client.post(
        "/api/files/transfer",
        json={"paths": [str(home / "projects")], "folder": str(home / "projects" / "ziel")},
    )
    assert base.status_code == 403
    outside = client.post(
        "/api/files/transfer",
        json={"paths": [str(home / "elsewhere.txt")], "folder": str(home / "projects" / "ziel")},
    )
    assert outside.status_code == 403


def test_a_folder_with_a_running_agent_is_not_moved_but_may_be_copied(
    client: TestClient, home: Path
) -> None:
    (home / "projects" / "ziel").mkdir()
    agent_folder = home / "projects" / "agent"
    agent_folder.mkdir()
    start_in(client, agent_folder, "sleeper")
    request = {"paths": [str(agent_folder)], "folder": str(home / "projects" / "ziel")}
    assert client.post("/api/files/transfer", json=request).status_code == 409
    copied = client.post("/api/files/transfer", json={**request, "as_copy": True})
    assert copied.status_code == 200
    assert agent_folder.exists()


def test_an_empty_folder_is_made_with_the_ones_on_the_way(
    client: TestClient, home: Path, tmp_path: Path
) -> None:
    folder = home / "projects"
    made = client.post(
        "/api/files/directory", json={"folder": str(folder), "subfolder": "proj/src/leer"}
    )
    assert made.status_code == 200
    assert (folder / "proj" / "src" / "leer").is_dir()
    # Again, with a file in it: nothing is touched.
    (folder / "proj" / "src" / "leer" / "a.txt").write_text("x")
    again = client.post(
        "/api/files/directory", json={"folder": str(folder), "subfolder": "proj/src/leer"}
    )
    assert again.status_code == 200
    assert (folder / "proj" / "src" / "leer" / "a.txt").read_text() == "x"
    up = {"folder": str(folder), "subfolder": "proj/../.."}
    assert client.post("/api/files/directory", json=up).status_code == 422
    (folder / "link").symlink_to(tmp_path)
    out = {"folder": str(folder), "subfolder": "link/neu"}
    assert client.post("/api/files/directory", json=out).status_code == 403
    assert not (tmp_path / "neu").exists()


def test_an_upload_needs_a_folder_in_scope(client: TestClient, home: Path) -> None:
    outside = client.post(
        "/api/files/upload", params={"folder": str(home), "name": "a.txt"}, content=b"x"
    )
    assert outside.status_code == 403
    (home / "projects" / "a.txt").write_text("x")
    not_a_folder = client.post(
        "/api/files/upload",
        params={"folder": str(home / "projects" / "a.txt"), "name": "b.txt"},
        content=b"x",
    )
    assert not_a_folder.status_code == 400


def test_folders_and_files_may_have_spaces_and_umlauts(client: TestClient, home: Path) -> None:
    projects = home / "projects"
    created = client.post(
        "/api/files/folder", json={"parent": str(projects), "name": "Mein Ärger-Projekt"}
    )
    assert created.status_code == 200
    assert (projects / "Mein Ärger-Projekt").is_dir()
    (projects / "a.txt").write_text("x")
    renamed = client.post(
        "/api/files/rename", json={"path": str(projects / "a.txt"), "new_name": "Übung 1 (neu).txt"}
    )
    assert Path(renamed.json()["path"]) == projects / "Übung 1 (neu).txt"
    refused = client.post(
        "/api/files/rename", json={"path": str(projects / "Übung 1 (neu).txt"), "new_name": "a/b"}
    )
    assert refused.status_code == 422


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


@pytest.fixture
def trusted(config: Config, home: Path, clock: FakeClock) -> TestClient:
    """The server on a socket: nobody logs in."""
    on_socket = config.model_copy(update={"server": ServerConfig(socket=home / "run" / "orc.sock")})
    return TestClient(create_app(on_socket, None, static_dir=None, clock=clock))


def test_on_a_socket_nothing_asks_for_a_login(trusted: TestClient, home: Path) -> None:
    assert trusted.get("/api/me").json() == {"authenticated": True}
    assert trusted.get("/api/sessions").status_code == 200
    assert trusted.post("/api/login", json={"password": "x"}).status_code == 404
    # Unlocking the files outside the project folder needs no password either.
    assert trusted.post("/api/scope/unlock", json={"password": ""}).status_code == 200


def test_a_socket_and_a_login_belong_together(config: Config, home: Path) -> None:
    on_socket = config.model_copy(update={"server": ServerConfig(socket=home / "orc.sock")})
    with pytest.raises(ValueError, match="exactly when"):
        create_app(on_socket, new_credentials(PASSWORD), static_dir=None)
    with pytest.raises(ValueError, match="exactly when"):
        create_app(config, None, static_dir=None)


ORIGIN = {"origin": "http://testserver"}
MAX_TERMINAL_FRAMES = 500


def start_shell(client: TestClient, folder: Path, workspace: str | None = None) -> str:
    folder.mkdir(exist_ok=True)
    body = {
        "profile": "shell",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
        "workspace": workspace,
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


def end_from_the_server(terminal: WebSocketTestSession, socket_name: str) -> int:
    """Ends the open terminal the way a restart of Agent-Orc does (the tmux client goes while its
    session lives on) and returns the close code the browser gets.

    A test that simply leaves its `with` cancels the app at once, while it still winds the tmux
    client down, and now and then that cancellation comes out as a CancelledError of the test.
    Once the server has ended the terminal itself, there is nothing left to cancel."""
    client_pid = subprocess.run(
        ["tmux", "-L", socket_name, "list-clients", "-F", "#{client_pid}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    os.kill(int(client_pid), signal.SIGTERM)
    with pytest.raises(WebSocketDisconnect) as closed:
        for _ in range(MAX_TERMINAL_FRAMES):
            terminal.receive_bytes()
    code: int = closed.value.code
    return code


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
        # Ended by the server (the tmux client goes, the session lives on), see end_from_the_server.
        end_from_the_server(term, socket_name)

    # Closing the terminal only detaches: the agent keeps running.
    assert client.get("/api/sessions").json()[0]["running"] is True


def test_terminal_input_of_a_long_text_arrives_whole(
    client: TestClient, home: Path, socket_name: str
) -> None:
    session_id = start_shell(client, home / "projects")
    text = "".join(f"{number:04d}-" for number in range(120))
    with client.websocket_connect(terminal_url(session_id), headers=ORIGIN) as term:
        read_until(term, "READY")
        term.send_text(json.dumps({"type": "input", "data": text + "\r"}))
        # cat prints the line again once it is submitted: the echo and its output.
        for _ in range(50):
            if client.get(f"/api/sessions/{session_id}/text").json()["text"].count(text) == 2:
                break
            time.sleep(0.1)
        end_from_the_server(term, socket_name)
    assert client.get(f"/api/sessions/{session_id}/text").json()["text"].count(text) == 2


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
        closed = end_from_the_server(term, socket_name)
    assert closed == WS_CLOSE_SERVICE_RESTART
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


def test_effort_is_stored_for_each_agent(client: TestClient, home: Path) -> None:
    folder = home / "projects"
    folder_settings = folder / ".claude" / "settings.local.json"
    folder_settings.parent.mkdir()
    folder_settings.write_text(json.dumps({"effortLevel": "max", "ultracode": True}))
    query = {"profile": "sleeper", "path": str(folder)}
    # An agent without a level of its own shows the configured one.
    assert client.get("/api/effort", params=query).json() == {"effort": "low", "ultracode": False}

    start = {
        "profile": "sleeper",
        "path": str(folder),
        "resume": False,
        "effort": "high",
        "ultracode": False,
        "conversation": None,
    }
    first = client.post("/api/sessions", json=start).json()["id"]
    review = client.post("/api/sessions", json={**start, "effort": None, "suffix": "Review"}).json()
    # Each agent gets its own values, stated in full over the folder's older ones.
    assert agent_settings(first) == {
        "effortLevel": "high",
        "ultracode": False,
        "permissions": {"defaultMode": "default"},
    }
    assert agent_settings(review["id"])["effortLevel"] == "low"
    # Agent-Orc leaves the folder's own settings alone.
    assert json.loads(folder_settings.read_text()) == {"effortLevel": "max", "ultracode": True}
    assert client.get("/api/effort", params=query).json() == {"effort": "high", "ultracode": False}
    reviewer = {**query, "suffix": "Review"}
    assert client.get("/api/effort", params=reviewer).json() == {
        "effort": "low",
        "ultracode": False,
    }


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
    with client.websocket_connect(terminal_url(session_id), headers=ORIGIN) as terminal:
        changed = client.post(f"/api/sessions/{session_id}/effort", json=change)
        # Restarted in its own session: the open terminal stays attached to the same id.
        assert tmux_client_size(socket_name) == f"{START_COLS}x{START_ROWS}"
        end_from_the_server(terminal, socket_name)
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
    assert agent_settings(session_id) == {
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
    assert agents["swapper"]["model_live"] is True
    assert agents["chooser"]["model_live"] is False


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
    # Not applied yet: the agent keeps the level it started with.
    assert agent_settings(session_id)["effortLevel"] == "low"

    # A wrong level is refused right away, not only when the change would be applied.
    wrong = client.post(url, json={"effort": "ultra", "ultracode": False, "immediately": False})
    assert wrong.status_code == 422

    assert client.delete(url).status_code == 204
    assert client.get("/api/sessions").json()[0]["effort_pending"] is False

    # "Immediately" ignores the busy state on purpose.
    assert client.post(
        url, json={"effort": "high", "ultracode": False, "immediately": True}
    ).json() == {"applied": True}
    assert agent_settings(session_id) == {
        "effortLevel": "high",
        "ultracode": False,
        "permissions": {"defaultMode": "default"},
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
    with client.websocket_connect(terminal_url(session_id), headers=ORIGIN) as terminal:
        restarted = client.post(f"/api/sessions/{session_id}/restart")
        # Restarted in its own session: the open terminal stays attached to the same id.
        assert tmux_client_size(socket_name) == f"{START_COLS}x{START_ROWS}"
        end_from_the_server(terminal, socket_name)
    assert restarted.json()["id"] == session_id
    command = subprocess.run(
        ["tmux", "-L", socket_name, "display-message", "-p", "-t", f"={session_id}:",
         "#{pane_start_command}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    assert command == "sleep 61"
    listed = client.get("/api/sessions").json()[0]
    assert (listed["busy"], listed["effort_pending"]) == (False, False)
    assert agent_settings(session_id)["effortLevel"] == "high"

    assert client.post("/api/sessions/unknown/restart").status_code == 404


def test_restart_goes_on_with_the_agents_own_conversation(
    client: TestClient, home: Path, socket_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    start = {
        "profile": "talker_too",
        "path": str(home / "projects"),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
    session_id = client.post("/api/sessions", json=start).json()["id"]
    transcript = home / "conversation-0001.jsonl"
    transcript.write_text("{}\n")
    store_status(session_id, {"model": {"display_name": "M"}, "transcript_path": str(transcript)})
    client.post(f"/api/sessions/{session_id}/restart")
    command = subprocess.run(
        ["tmux", "-L", socket_name, "display-message", "-p", "-t", f"={session_id}:",
         "#{pane_start_command}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    # Its own conversation by id (the profile's conversations.resume), not the folder's last.
    assert command == "sleep 64"


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
        assert agent_settings(session_id)["effortLevel"] == "low"


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
        "service": {"engine": "parakeet", "gpu": "fp32", "cpu": "int8"},
    }
    assert dictate("cpu").json() == {"text": "Hallo Welt"}
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


def test_permission_mode_is_stored_for_the_agent(client: TestClient, home: Path) -> None:
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
    # An agent without a mode of its own starts in the configured default.
    assert client.get("/api/sessions").json()[0]["permission_mode"] == "default"
    assert agent_settings(session_id)["permissions"] == {"defaultMode": "default"}
    url = f"/api/sessions/{session_id}/permission-mode"
    assert client.put(url, json={"mode": "plan"}).status_code == 204
    assert client.get("/api/sessions").json()[0]["permission_mode"] == "plan"
    # It takes effect at the next start.
    client.post(f"/api/sessions/{session_id}/restart")
    assert agent_settings(session_id)["permissions"] == {"defaultMode": "plan"}
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


def report_context(session_id: str, tokens: int, transcript: Path | None = None) -> None:
    status: dict[str, Any] = {
        "model": {"display_name": "Opus"},
        "context_window": {
            "context_window_size": 1000,
            "current_usage": {"input_tokens": tokens},
        },
    }
    if transcript is not None:
        status["transcript_path"] = str(transcript)
    store_status(session_id, status)


def answered_at(transcript: Path, at: float) -> Path:
    """A transcript whose last answer came at `at` and wrote to the cache for an hour."""
    stamp = datetime.fromtimestamp(at, UTC).isoformat().replace("+00:00", "Z")
    usage = {"cache_creation": {"ephemeral_1h_input_tokens": 500, "ephemeral_5m_input_tokens": 0}}
    entry = {"type": "assistant", "timestamp": stamp, "message": {"usage": usage}}
    transcript.write_text(json.dumps(entry) + "\n")
    return transcript


def test_handover_is_due_shortly_before_the_cache_expires(
    client: TestClient,
    clock: FakeClock,
    home: Path,
    socket_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    session_id = start_shell(client, home / "projects")
    transcript = answered_at(home / "conversation.jsonl", clock())
    report_context(session_id, 400, transcript)
    store_activity(session_id, busy=False)
    listed = client.get("/api/sessions").json()[0]
    assert listed["handover"] == {"recommended": False, "due": False, "progress": None}
    lead = 10 * 60
    assert listed["cache"] == {
        "last_request": clock(),
        "window_seconds": 3600,
        "lead_seconds": lead,
    }

    report_context(session_id, 600, transcript)
    assert client.get("/api/sessions").json()[0]["handover"]["recommended"] is True
    clock.advance(49 * 60)
    assert client.get("/api/sessions").json()[0]["handover"]["due"] is False
    # Within the last ten minutes of the hour.
    clock.advance(2 * 60)
    assert client.get("/api/sessions").json()[0]["handover"]["due"] is True
    # Not into a working agent.
    store_activity(session_id, busy=True)
    assert client.get("/api/sessions").json()[0]["handover"]["due"] is False

    assert client.post(f"/api/sessions/{session_id}/handover").status_code == 204
    screen = subprocess.run(
        ["tmux", "-L", socket_name, "capture-pane", "-p", "-t", f"={session_id}:"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    assert "handover document" in screen
    assert client.get("/api/sessions").json()[0]["handover"]["progress"] == "asked"


def test_automatic_handover_runs_once_per_rest(
    config: Config, clock: FakeClock, home: Path, socket_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    monkeypatch.setattr("agent_orc.api.AGENT_CHECK_SECONDS", 0.1)
    write_auto(True)
    with TestClient(
        create_app(config, new_credentials(PASSWORD), static_dir=None, clock=clock)
    ) as client:
        client.post("/api/login", json={"password": PASSWORD})
        session_id = start_shell(client, home / "projects")
        # Resting for 55 minutes with a large context: due.
        report_context(session_id, 600, answered_at(home / "conversation.jsonl", clock() - 55 * 60))
        store_activity(session_id, busy=False)

        def progress_becomes(wanted: str | None) -> bool:
            for _ in range(30):
                if client.get("/api/sessions").json()[0]["handover"]["progress"] == wanted:
                    return True
                time.sleep(0.1)
            return False

        assert progress_becomes("asked")
        assert wait_for_text(client, session_id, "handover document")
        store_activity(session_id, busy=True)
        assert progress_becomes("working")
        # Written: the agent warmed its cache doing so, but it is not asked again.
        report_context(session_id, 600, answered_at(home / "conversation.jsonl", clock() - 55 * 60))
        store_activity(session_id, busy=False)
        assert progress_becomes("done")
        time.sleep(0.5)
        assert client.get("/api/sessions").json()[0]["handover"]["progress"] == "done"
        # The user's next input ends it.
        store_activity(session_id, busy=True)
        assert progress_becomes(None)


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


def start_agents(client: TestClient, home: Path, count: int) -> list[str]:
    (home / "projects").mkdir(exist_ok=True)
    return [start_shell(client, home / "projects" / f"agent{number}") for number in range(count)]


def test_workspaces_are_kept_and_deleted(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    a, b, c = start_agents(client, home, 3)
    empty = {"tabs": [], "visible": 1, "widths": {}, "active": None}
    # Agents in no workspace show in the unnamed one.
    assert client.get("/api/workspaces").json() == {
        "unnamed": {**empty, "tabs": sorted([a, b, c]), "active": min(a, b, c)},
        "named": {},
    }
    left = {"tabs": [a, b], "visible": 2, "widths": {a: 0.3}, "active": b}
    assert client.put("/api/workspaces/Links", json=left).status_code == 204
    right = {"tabs": [], "visible": 1, "widths": {}, "active": None}
    assert client.put("/api/workspaces/Rechts", json=right).status_code == 204
    loose = {"tabs": [c], "visible": 1, "widths": {}, "active": c}
    assert client.put("/api/unnamed-workspace", json=loose).status_code == 204
    assert client.get("/api/workspaces").json() == {
        "unnamed": loose,
        "named": {"Links": left, "Rechts": right},
    }
    assert client.delete("/api/workspaces/Links").status_code == 204
    assert client.get("/api/workspaces").json() == {
        "unnamed": {**loose, "tabs": [c, a, b]},
        "named": {"Rechts": right},
    }


def test_an_agent_started_for_a_workspace_joins_it_on_the_server(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    (a,) = start_agents(client, home, 1)
    right = {"tabs": [], "visible": 1, "widths": {}, "active": None}
    assert client.put("/api/workspaces/Rechts", json=right).status_code == 204
    folder = home / "projects" / "joined"
    joined = start_shell(client, folder, workspace="Rechts")
    shown = client.get("/api/workspaces").json()
    assert shown["named"]["Rechts"]["tabs"] == [joined]
    assert shown["unnamed"]["tabs"] == [a]


def test_starting_for_an_unknown_workspace_starts_nothing(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    folder = home / "projects" / "nowhere"
    folder.mkdir()
    body = {
        "profile": "shell",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
        "workspace": "Gibt-es-nicht",
    }
    assert client.post("/api/sessions", json=body).status_code == 404
    assert client.get("/api/sessions").json() == []


def test_an_agent_is_moved_between_workspaces(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    a, b = start_agents(client, home, 2)
    left = {"tabs": [a, b], "visible": 2, "widths": {}, "active": a}
    assert client.put("/api/workspaces/Links", json=left).status_code == 204
    assert client.put(f"/api/sessions/{b}/workspace", json={"workspace": ""}).status_code == 204
    shown = client.get("/api/workspaces").json()
    assert shown["named"]["Links"]["tabs"] == [a]
    assert shown["unnamed"]["tabs"] == [b]
    moved = client.put(f"/api/sessions/{b}/workspace", json={"workspace": "Links"})
    assert moved.status_code == 204
    shown = client.get("/api/workspaces").json()
    assert shown["named"]["Links"]["tabs"] == [a, b]
    assert shown["unnamed"]["tabs"] == []
    unknown = client.put(f"/api/sessions/{b}/workspace", json={"workspace": "Gibt-es-nicht"})
    assert unknown.status_code == 404
    gone = client.put("/api/sessions/gone-123456/workspace", json={"workspace": ""})
    assert gone.status_code == 404


def test_deleting_a_workspace_moves_its_agents_to_the_unnamed_one(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    a, b, c = start_agents(client, home, 3)
    left = {"tabs": [a, b], "visible": 2, "widths": {}, "active": a}
    loose = {"tabs": [c], "visible": 1, "widths": {}, "active": c}
    client.put("/api/workspaces/Links", json=left)
    client.put("/api/unnamed-workspace", json=loose)
    assert client.delete("/api/workspaces/Links").status_code == 204
    shown = client.get("/api/workspaces").json()
    assert shown["named"] == {}
    assert shown["unnamed"]["tabs"] == [c, a, b]


def test_an_agent_lives_in_one_workspace(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    a, b = start_agents(client, home, 2)
    left = {"tabs": [a, b], "visible": 2, "widths": {a: 0.3, b: 0.7}, "active": a}
    assert client.put("/api/workspaces/Links", json=left).status_code == 204
    moved = {"tabs": [a], "visible": 1, "widths": {}, "active": a}
    assert client.put("/api/unnamed-workspace", json=moved).status_code == 204
    shown = client.get("/api/workspaces").json()
    assert shown["unnamed"] == moved
    assert shown["named"]["Links"] == {
        "tabs": [b],
        "visible": 2,
        "widths": {b: 0.7},
        "active": b,
    }


def test_a_workspace_shows_no_agent_that_no_longer_exists(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    (a,) = start_agents(client, home, 1)
    stored = {
        "tabs": ["gone-123456", a],
        "visible": 2,
        "widths": {"gone-123456": 0.4},
        "active": "gone-123456",
    }
    assert client.put("/api/workspaces/Links", json=stored).status_code == 204
    assert client.get("/api/workspaces").json()["named"]["Links"] == {
        "tabs": [a],
        "visible": 2,
        "widths": {},
        "active": a,
    }


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


def agent_settings(session_id: str) -> dict[str, Any]:
    """The settings file the agent got at its last start."""
    settings: dict[str, Any] = json.loads(agent_settings_file(session_id).read_text())
    return settings


def wait_for_text(client: TestClient, session_id: str, text: str, count: int = 1) -> bool:
    for _ in range(50):
        if client.get(f"/api/sessions/{session_id}/text").json()["text"].count(text) >= count:
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


def test_a_further_agent_in_a_folder_needs_a_suffix_and_gets_it(
    client: TestClient, home: Path
) -> None:
    folder = home / "projects" / "a"
    folder.mkdir()
    body = {
        "profile": "named",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
    first = client.post("/api/sessions", json=body).json()
    assert wait_for_text(client, first["id"], "named a [none]")
    # The folder has its agent: another one needs a suffix, of allowed characters.
    assert client.post("/api/sessions", json=body).status_code == 409
    assert client.post("/api/sessions", json={**body, "suffix": "a.b"}).status_code == 422
    review = client.post("/api/sessions", json={**body, "suffix": "Review"}).json()
    assert review["id"] != first["id"]
    assert wait_for_text(client, review["id"], "named a-Review [Review]")
    listed = {s["id"]: s["name"] for s in client.get("/api/sessions").json()}
    assert (listed[first["id"]], listed[review["id"]]) == ("a", "a-Review")
    assert client.post("/api/sessions", json={**body, "suffix": "Review"}).status_code == 409


def test_answers_seen_only_go_forward_and_show_on_every_device(
    config: Config, clock: FakeClock, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    # As a context manager the client keeps one event loop, as the server has (uvicorn).
    with TestClient(
        create_app(config, new_credentials(PASSWORD), static_dir=None, clock=clock)
    ) as client:
        client.post("/api/login", json={"password": PASSWORD})
        session_id = start_shell(client, home / "projects")
        assert client.get("/api/sessions").json()[0]["answers_seen"] == ""
        url = f"/api/sessions/{session_id}/answers-seen"
        assert client.put(url, json={"time": "2026-10-09T18:00:00.000Z"}).status_code == 204
        # A device that saw less (an older answer) changes nothing.
        assert client.put(url, json={"time": "2026-10-09T17:00:00.000Z"}).status_code == 204
        seen = client.get("/api/sessions").json()[0]["answers_seen"]
        assert seen == "2026-10-09T18:00:00.000Z"
        # Several marks at once (a page marks every answer it shows): the latest time stays.
        times = [f"2026-10-09T19:{minute:02d}:00.000Z" for minute in range(30)]
        with ThreadPoolExecutor() as pool:
            list(pool.map(lambda time: client.put(url, json={"time": time}), times))
        assert client.get("/api/sessions").json()[0]["answers_seen"] == times[-1]
        unknown = {"time": "2026-10-09T18:00:00.000Z"}
        assert client.put("/api/sessions/gone/answers-seen", json=unknown).status_code == 404


def test_message_is_submitted_after_a_long_text(client: TestClient, home: Path) -> None:
    session = start_shell(client, home / "projects" / "a")
    assert wait_for_text(client, session, "READY")
    # Longer than several typed pieces: the Enter must still come after the whole text.
    text = "word " * 200 + "END"
    response = client.post(f"/api/sessions/{session}/message", json={"text": text})
    assert response.status_code == 204
    # cat prints a line only once it is submitted: the echo plus cat's own copy.
    assert wait_for_text(client, session, "END", count=2)
    assert client.post("/api/sessions/gone/message", json={"text": "x"}).status_code == 404


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


def test_broadcast_can_leave_the_text_unsent(client: TestClient, home: Path) -> None:
    session = start_shell(client, home / "projects" / "a")
    assert wait_for_text(client, session, "READY")
    response = client.post(
        "/api/broadcast", json={"sessions": [session], "text": "draft note", "submit": False}
    )
    assert response.status_code == 204
    assert wait_for_text(client, session, "draft note")
    time.sleep(0.3)
    # cat prints a line only once it is submitted: only the terminal's own echo is on screen.
    assert client.get(f"/api/sessions/{session}/text").json()["text"].count("draft note") == 1


def test_raw_file_is_served_without_running_its_scripts(client: TestClient, home: Path) -> None:
    picture = home / "projects" / "logo.svg"
    picture.write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
    shown = client.get("/api/files/raw", params={"path": str(picture)})
    assert shown.status_code == 200
    assert shown.content == picture.read_bytes()
    assert shown.headers["content-type"].startswith("image/svg+xml")
    assert shown.headers["content-security-policy"] == "sandbox"
    assert shown.headers["content-disposition"].startswith("inline")
    saved = client.get("/api/files/raw", params={"path": str(picture), "download": True})
    assert saved.headers["content-disposition"].startswith("attachment")
    assert client.get("/api/files/raw", params={"path": str(home / "projects")}).status_code == 404
    secret = home / "private" / "secret.txt"
    secret.write_text("x")
    assert client.get("/api/files/raw", params={"path": str(secret)}).status_code == 403


def test_existing_paths_of_an_agents_output(client: TestClient, home: Path) -> None:
    project = home / "projects" / "demo"
    (project / "src").mkdir(parents=True)
    (project / "src" / "main.py").write_text("print()")
    (home / "private" / "secret.txt").write_text("x")
    candidates = [
        "src/main.py",
        "src",
        str(project / "src" / "main.py"),
        "missing.py",
        # Exists, but outside the scope: not offered.
        "~/private/secret.txt",
    ]
    found = client.post(
        "/api/files/existing", json={"base": str(project), "candidates": candidates}
    ).json()
    main = {"path": str(project / "src" / "main.py"), "kind": "file"}
    assert found == {
        "src/main.py": main,
        "src": {"path": str(project / "src"), "kind": "folder"},
        str(project / "src" / "main.py"): main,
    }


def test_a_terminal_opens_next_to_the_folders_agent(client: TestClient, home: Path) -> None:
    folder = home / "projects"
    agent = {
        "profile": "sleeper",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
    agent_id = client.post("/api/sessions", json=agent).json()["id"]
    terminal_id = start_shell(client, folder)
    listed = {s["id"]: s["terminal"] for s in client.get("/api/sessions").json()}
    assert listed == {agent_id: False, terminal_id: True}
    agents = {a["name"]: a["terminal"] for a in client.get("/api/agents").json()}
    assert agents["shell"] is True and agents["sleeper"] is False
    # A second agent stays refused, the terminal is only one per folder as well.
    assert client.post("/api/sessions", json=agent).status_code == 409
    assert client.post("/api/sessions", json={**agent, "profile": "shell"}).status_code == 409


def test_extra_keys_arranged_for_every_device(
    client: TestClient, config: Config, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    default = client.get("/api/terminal").json()
    assert default["keys_arranged"] is False
    assert default["keys"][0][0]["label"] == config.terminal.keys[0][0].label

    rows = [
        [{"label": "^C", "send": "\x03"}, {"label": "Ctrl", "modifier": "ctrl"}],
        # A text key: Enter follows the text.
        [{"label": "compact", "send": "/compact", "submit": True}],
    ]
    assert client.put("/api/terminal/keys", json=rows).status_code == 204
    arranged = client.get("/api/terminal").json()
    assert arranged["keys_arranged"] is True
    assert [[k["label"] for k in row] for row in arranged["keys"]] == [["^C", "Ctrl"], ["compact"]]
    assert arranged["keys"][1][0] == {
        "label": "compact",
        "send": "/compact",
        "modifier": None,
        "submit": True,
    }
    # A text key needs its text; a key is either a sequence or a modifier.
    broken = [[{"label": "x", "modifier": "ctrl", "submit": True}]]
    assert client.put("/api/terminal/keys", json=broken).status_code == 422

    assert client.delete("/api/terminal/keys").status_code == 204
    assert client.get("/api/terminal").json() == default


def test_a_chosen_model_gets_its_levels_and_environment(client: TestClient, home: Path) -> None:
    assert client.get("/api/agents/chooser/models").json() == [
        {"name": "thinker", "note": "free until Friday"},
        {"name": "plain", "note": None},
    ]
    assert client.get("/api/agents/chooser/levels", params={"model": "thinker"}).json() == [
        "low",
        "high",
    ]
    assert client.get("/api/agents/chooser/levels", params={"model": "plain"}).json() == []
    agents = {a["name"]: a for a in client.get("/api/agents").json()}
    assert agents["chooser"]["models"] is True and agents["sleeper"]["models"] is False
    assert agents["chooser"]["hint"] == "Stop the other model first."
    assert agents["sleeper"]["hint"] is None

    def start(folder: Path, model: str | None, effort: str | None) -> Any:
        folder.mkdir()
        body = {
            "profile": "chooser",
            "path": str(folder),
            "model": model,
            "resume": False,
            "effort": effort,
            "ultracode": False,
            "conversation": None,
        }
        return client.post("/api/sessions", json=body)

    thinker = start(home / "projects" / "a", "thinker", "high").json()
    assert thinker["chosen_model"] == "thinker"
    assert wait_for_text(client, thinker["id"], "started thinker [high]")
    plain = start(home / "projects" / "b", "plain", None).json()
    # No levels for this model: no level stored and no effort in the environment.
    assert wait_for_text(client, plain["id"], "started plain []")
    listed = {s["id"]: s["effort_levels"] for s in client.get("/api/sessions").json()}
    assert listed == {thinker["id"]: ["low", "high"], plain["id"]: []}

    # A level the model does not take, a model the profile does not offer, or none at all.
    assert start(home / "projects" / "c", "thinker", "medium").status_code == 422
    assert start(home / "projects" / "d", "other", None).status_code == 422
    assert start(home / "projects" / "e", None, None).status_code == 422

    # A restart keeps the model and gives the folder's level again.
    client.post(f"/api/sessions/{thinker['id']}/restart")
    assert wait_for_text(client, thinker["id"], "resumed thinker [high]")


def test_an_agent_without_a_stored_model_is_restarted_with_a_chosen_one(
    client: TestClient, home: Path, socket_name: str
) -> None:
    folder = home / "projects" / "old"
    folder.mkdir()
    body = {
        "profile": "chooser",
        "path": str(folder),
        "model": "thinker",
        "resume": False,
        "effort": "high",
        "ultracode": False,
        "conversation": None,
    }
    session = client.post("/api/sessions", json=body).json()["id"]
    assert wait_for_text(client, session, "started thinker [high]")
    # Started before the choice of models existed: tmux holds no model for it.
    subprocess.run(
        ["tmux", "-L", socket_name, "set-option", "-t", f"={session}:", "@orc_model", ""],
        check=True,
    )
    restart = f"/api/sessions/{session}/restart"
    assert client.post(restart).status_code == 422
    assert client.post(restart, json={"model": "other"}).status_code == 422
    chosen = client.post(restart, json={"model": "thinker"})
    assert chosen.status_code == 200
    assert chosen.json()["chosen_model"] == "thinker"
    assert wait_for_text(client, session, "resumed thinker [high]")
    # From now on the restart keeps it.
    client.post(restart)
    assert client.get("/api/sessions").json()[0]["chosen_model"] == "thinker"


def start_with_model(
    client: TestClient, home: Path, profile: str, model: str, effort: str | None = None
) -> str:
    body = {
        "profile": profile,
        "path": str(home / "projects"),
        "model": model,
        "resume": False,
        "effort": effort,
        "ultracode": False,
        "conversation": None,
    }
    session_id: str = client.post("/api/sessions", json=body).json()["id"]
    return session_id


def pane_process(socket_name: str, session_id: str) -> str:
    target = f"={session_id}:"
    return subprocess.run(
        ["tmux", "-L", socket_name, "display-message", "-p", "-t", target, "#{pane_pid}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


def test_model_switches_in_place_where_the_agent_can(
    client: TestClient, home: Path, socket_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("agent_orc.effort.PROTECT_SECONDS", 0.3)
    session_id = start_with_model(client, home, "swapper", "thinker")
    assert wait_for_text(client, session_id, "started thinker")
    process = pane_process(socket_name, session_id)
    url = f"/api/sessions/{session_id}/model"
    assert client.post(url, json={"model": "other"}).status_code == 422
    # Typing into a busy agent would mix with its work: the change waits for the end of the answer.
    store_activity(session_id, busy=True)
    assert client.post(url, json={"model": "plain"}).json() == {"applied": False}
    assert client.get("/api/sessions").json()[0]["pending_model"] == "plain"
    assert client.delete(url).status_code == 204
    assert client.get("/api/sessions").json()[0]["pending_model"] is None
    store_activity(session_id, busy=False)
    assert client.post(url, json={"model": "plain"}).json() == {"applied": True}
    assert client.get("/api/sessions").json()[0]["chosen_model"] == "plain"
    # Typed into the running agent (the terminal echoes it), which keeps running, and its
    # question was answered.
    assert wait_for_text(client, session_id, "/model plain")
    assert wait_for_text(client, session_id, "confirmed")
    assert pane_process(socket_name, session_id) == process


def test_context_is_cleared_or_shrunk_in_place_for_an_idle_agent(
    client: TestClient, home: Path, socket_name: str
) -> None:
    session_id = start_with_model(client, home, "swapper", "thinker")
    assert wait_for_text(client, session_id, "started thinker")
    process = pane_process(socket_name, session_id)
    clear = f"/api/sessions/{session_id}/context/clear"
    store_activity(session_id, busy=True)
    assert client.post(clear).status_code == 409
    store_activity(session_id, busy=False)
    assert client.post(clear).status_code == 204
    assert client.post(f"/api/sessions/{session_id}/context/compact").status_code == 204
    # Typed into the running agent (the terminal echoes it), which keeps running.
    assert wait_for_text(client, session_id, "/clear")
    assert wait_for_text(client, session_id, "/compact")
    assert pane_process(socket_name, session_id) == process
    assert client.post(f"/api/sessions/{session_id}/context/other").status_code == 422
    agents = {agent["name"]: agent for agent in client.get("/api/agents").json()}
    assert agents["swapper"]["context_actions"] == ["clear", "compact"]
    assert agents["chooser"]["context_actions"] == []


def test_context_of_an_agent_without_the_command_is_left_alone(
    client: TestClient, home: Path
) -> None:
    session_id = start_with_model(client, home, "chooser", "thinker", effort="high")
    assert client.post(f"/api/sessions/{session_id}/context/clear").status_code == 422
    assert client.post(f"/api/sessions/{session_id}/context/compact").status_code == 422


def test_pending_model_is_typed_in_when_the_agent_is_done(
    config: Config, clock: FakeClock, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    monkeypatch.setattr("agent_orc.api.AGENT_CHECK_SECONDS", 0.1)
    monkeypatch.setattr("agent_orc.effort.PROTECT_SECONDS", 0.3)
    # The context manager runs the app's lifespan, i.e. the background watcher.
    with TestClient(
        create_app(config, new_credentials(PASSWORD), static_dir=None, clock=clock)
    ) as client:
        client.post("/api/login", json={"password": PASSWORD})
        session_id = start_with_model(client, home, "swapper", "thinker")
        store_activity(session_id, busy=True)
        client.post(f"/api/sessions/{session_id}/model", json={"model": "plain"})
        time.sleep(0.5)
        assert client.get("/api/sessions").json()[0]["pending_model"] == "plain"

        store_activity(session_id, busy=False)
        assert wait_for_text(client, session_id, "/model plain")
        # The model is noted once the agent's rewrite of the protected file has been undone.
        for _ in range(30):
            if client.get("/api/sessions").json()[0]["chosen_model"] == "plain":
                break
            time.sleep(0.1)
        assert client.get("/api/sessions").json()[0]["chosen_model"] == "plain"
        assert client.get("/api/sessions").json()[0]["pending_model"] is None


def test_model_change_restarts_an_agent_that_cannot_switch_in_place(
    client: TestClient, home: Path, socket_name: str
) -> None:
    session_id = start_with_model(client, home, "chooser", "thinker", effort="high")
    assert wait_for_text(client, session_id, "started thinker")
    process = pane_process(socket_name, session_id)
    switched = client.post(f"/api/sessions/{session_id}/model", json={"model": "plain"})
    assert switched.json() == {"applied": True}
    assert client.get("/api/sessions").json()[0]["chosen_model"] == "plain"
    assert wait_for_text(client, session_id, "resumed plain")
    assert pane_process(socket_name, session_id) != process


def test_change_notifier_wakes_listeners_from_other_threads() -> None:
    async def scenario() -> list[str]:
        notifier = ChangeNotifier()
        stream = notifier.stream()
        received = [await anext(stream)]
        await asyncio.to_thread(notifier.notify)
        received.append(await anext(stream))
        await stream.aclose()
        assert not notifier._listeners
        return received

    assert asyncio.run(scenario()) == [": connected\n\n", "data: changed\n\n"]


def test_notebooks_are_kept_renamed_and_deleted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert client.get("/api/notebooks").json() == {}
    ideas = {
        "notes": [{"title": "Link", "text": "https://example.org"}],
        "folders": [{"name": "Code", "notes": [{"title": "Snippet", "text": "```\nls\n```"}]}],
    }
    empty: dict[str, list[object]] = {"notes": [], "folders": []}
    assert client.put("/api/notebooks/Ideen", json=ideas).status_code == 204
    assert client.put("/api/notebooks/Arbeit", json=empty).status_code == 204
    assert client.get("/api/notebooks").json() == {"Ideen": ideas, "Arbeit": empty}
    renamed = client.put("/api/notebooks/Ideen/name", json={"name": "Einfälle"})
    assert renamed.status_code == 204
    # The tab keeps its position.
    assert list(client.get("/api/notebooks").json()) == ["Einfälle", "Arbeit"]
    taken = client.put("/api/notebooks/Einfälle/name", json={"name": "Arbeit"})
    assert taken.status_code == 409
    assert client.put("/api/notebooks/Gibt-es-nicht/name", json={"name": "X"}).status_code == 404
    assert client.delete("/api/notebooks/Arbeit").status_code == 204
    assert client.delete("/api/notebooks/Arbeit").status_code == 404
    assert list(client.get("/api/notebooks").json()) == ["Einfälle"]


def test_a_note_file_is_stored_served_and_refused_outside_its_folder(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    stored = client.post("/api/notes/files", params={"name": "plan.pdf"}, content=b"%PDF-1.4")
    url = stored.json()["url"]
    assert url.startswith("api/notes/files/") and url.endswith("-plan.pdf")
    shown = client.get("/" + url)
    assert shown.status_code == 200 and shown.content == b"%PDF-1.4"
    # A PDF is for the browser's viewer, which the sandbox of other files would block.
    assert "content-security-policy" not in shown.headers
    picture = client.post("/api/notes/files", params={"name": "a.svg"}, content=b"<svg/>")
    assert client.get("/" + picture.json()["url"]).headers["content-security-policy"] == "sandbox"
    assert client.get("/api/notes/files/nope.png").status_code == 404
    assert client.get("/api/notes/files/..%2Fnotebooks.json").status_code == 404


def test_sending_a_note_brings_its_files_into_the_agents_folder(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    session = start_shell(client, home / "projects" / "a")
    assert wait_for_text(client, session, "READY")
    url = client.post("/api/notes/files", params={"name": "foto.png"}, content=b"png").json()["url"]
    text = f"Schau dir das an: ![Foto]({url}) und [Plan]({url})"
    response = client.post(
        "/api/broadcast", json={"sessions": [session], "text": text, "submit": False}
    )
    assert response.status_code == 204
    assert wait_for_text(client, session, "Schau dir das an: @.agent-orc/uploads/")
    copies = list((home / "projects" / "a" / ".agent-orc" / "uploads").glob("*foto*.png"))
    # One copy per link, each with the file's content.
    assert len(copies) == 2 and all(copy.read_bytes() == b"png" for copy in copies)


def test_answers_come_from_the_transcript_the_agent_reports(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    session_id = start_shell(client, home / "projects" / "a")
    answers = f"/api/sessions/{session_id}/answers"
    # Before the agent has reported where its transcript is: nothing.
    assert client.get(answers).json() == []
    transcript = home / ".claude" / "projects" / "-a" / "conversation.jsonl"
    transcript.parent.mkdir(parents=True)
    # Claude reports the path at start but creates the file with the first message only.
    store_status(session_id, {"model": {"display_name": "M"}, "transcript_path": str(transcript)})
    assert client.get(answers).json() == []
    lines = [
        {
            "type": "user",
            "uuid": "u1",
            "timestamp": "2026-10-06T10:00:00Z",
            "message": {"content": "Frage"},
        },
        {
            "type": "assistant",
            "uuid": "a2",
            "timestamp": "2026-10-06T10:00:05Z",
            "message": {"content": [{"type": "text", "text": "Antwort"}]},
        },
    ]
    transcript.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    turns = client.get(answers).json()
    shown = [(t["prompt"], [x["text"] for x in t["texts"]]) for t in turns]
    assert shown == [("Frage", ["Antwort"])]
    # A path outside Claude's own transcripts is not read, whatever the status says.
    outside = home / "projects" / "secret.jsonl"
    outside.write_text(transcript.read_text(encoding="utf-8"), encoding="utf-8")
    store_status(session_id, {"model": {"display_name": "M"}, "transcript_path": str(outside)})
    assert client.get(answers).json() == []
    assert client.get("/api/sessions/nope/answers").status_code == 404


def test_a_picture_of_a_request_is_served_from_the_transcript(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    session_id = start_shell(client, home / "projects" / "a")
    picture = {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "cG5nLWJ5dGVz"},
    }
    line = {
        "type": "user",
        "uuid": "u1",
        "timestamp": "2026-10-06T10:00:00Z",
        "message": {"content": [{"type": "text", "text": "Schau"}, picture]},
    }
    transcript = home / ".claude" / "projects" / "-a" / "conversation.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps(line), encoding="utf-8")
    url = f"/api/sessions/{session_id}/images/u1/0"
    assert client.get(url).status_code == 404  # the agent has not reported its transcript yet
    store_status(session_id, {"model": {"display_name": "M"}, "transcript_path": str(transcript)})
    shown = client.get(url)
    assert shown.status_code == 200 and shown.content == b"png-bytes"
    assert shown.headers["content-type"] == "image/png"
    assert client.get(f"/api/sessions/{session_id}/images/u1/1").status_code == 404
    assert client.get(f"/api/sessions/{session_id}/images/nope/0").status_code == 404
    assert client.get("/api/sessions/nope/images/u1/0").status_code == 404


def test_a_picture_attached_for_an_agent_is_served_by_its_name(
    client: TestClient, home: Path
) -> None:
    folder = home / "projects" / "a"
    session_id = start_shell(client, folder)
    stored = client.post(
        f"/api/sessions/{session_id}/attachments", params={"name": "shot.png"}, content=b"png-bytes"
    ).json()["path"]
    name = Path(stored).name
    shown = client.get(f"/api/sessions/{session_id}/uploads/{name}")
    assert shown.status_code == 200 and shown.content == b"png-bytes"
    # Only pictures of the uploads folder: no other files, no paths out of it, no unknown agents.
    document = client.post(
        f"/api/sessions/{session_id}/attachments", params={"name": "plan.pdf"}, content=b"%PDF"
    ).json()["path"]
    base = f"/api/sessions/{session_id}/uploads"
    assert client.get(f"{base}/{Path(document).name}").status_code == 404
    assert client.get(f"{base}/..%2F..%2Fsecret.png").status_code == 404
    assert client.get(f"{base}/nope.png").status_code == 404
    assert client.get(f"/api/sessions/nope/uploads/{name}").status_code == 404


def test_a_sound_can_be_played_and_sought_in_the_browser(client: TestClient, home: Path) -> None:
    sound = home / "projects" / "ding.wav"
    sound.write_bytes(b"RIFF" + bytes(range(60)))
    whole = client.get("/api/files/raw", params={"path": str(sound)})
    assert whole.status_code == 200 and whole.headers["content-type"] == "audio/x-wav"
    assert whole.headers["accept-ranges"] == "bytes"
    # A player seeks by asking for a part of the file.
    part = client.get("/api/files/raw", params={"path": str(sound)}, headers={"Range": "bytes=4-7"})
    assert part.status_code == 206 and part.content == bytes([0, 1, 2, 3])
    assert part.headers["content-range"] == "bytes 4-7/64"


def test_conversations_are_cleaned_up_within_the_access_scope(
    client: TestClient, home: Path, clock: FakeClock
) -> None:
    def write_conversation(folder: Path, conversation_id: str, age: float) -> Path:
        directory = claude_project_dir(home, folder)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{conversation_id}.jsonl"
        path.write_text(
            json.dumps({"type": "user", "cwd": str(folder), "message": {"content": "Hi"}})
        )
        os.utime(path, (clock.now - age, clock.now - age))
        return path

    inside = write_conversation(
        home / "projects" / "a", "1b0c8f2e-0000-4000-8000-000000000001", 86400
    )
    outside = write_conversation(home / "private", "1b0c8f2e-0000-4000-8000-000000000002", 86400)

    def listed() -> list[str]:
        return [p["folder"] for p in client.get("/api/conversations/all").json()]

    def delete(path: Path) -> Any:
        ref = {"directory": path.parent.name, "id": path.stem}
        return client.post("/api/conversations/delete", json={"conversations": [ref]})

    # The base directory only, until the safety switch widens the scope.
    assert listed() == [str(home / "projects" / "a")]
    assert delete(outside).status_code == 403
    client.post("/api/scope/unlock", json={"password": PASSWORD})
    assert sorted(listed()) == sorted([str(home / "projects" / "a"), str(home / "private")])
    # Deleted for good, and it says what that freed.
    size = inside.stat().st_size
    assert delete(inside).json() == {"deleted": 1, "freed_bytes": size}
    assert not inside.exists()
    assert delete(outside).status_code == 200 and not outside.exists()
    assert delete(inside).status_code == 404


def pane_command(socket_name: str, session_id: str) -> str:
    return subprocess.run(
        ["tmux", "-L", socket_name, "display-message", "-p", "-t", f"={session_id}:",
         "#{pane_start_command}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


def start_in(client: TestClient, folder: Path, profile: str) -> str:
    body = {
        "profile": profile,
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }
    session_id: str = client.post("/api/sessions", json=body).json()["id"]
    return session_id


def test_agent_switches_to_another_profile_in_its_session(
    client: TestClient, home: Path, socket_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    session_id = start_in(client, home / "projects", "sleeper")
    url = f"/api/sessions/{session_id}/profile"
    # Without conversations of its own the old agent has nothing to continue: a fresh start.
    switched = client.post(url, json={"profile": "talker_too"})
    assert switched.json()["id"] == session_id and switched.json()["profile"] == "talker_too"
    assert pane_command(socket_name, session_id) == "sleep 63"
    # Profiles keeping their conversations in the same place go on with the folder's last one.
    client.post(url, json={"profile": "talker"})
    assert client.post(url, json={"profile": "talker_too"}).status_code == 200
    assert pane_command(socket_name, session_id) == "sleep 62"
    assert client.get("/api/sessions").json()[0]["profile"] == "talker_too"


def test_profile_switch_refuses_what_makes_no_sense(client: TestClient, home: Path) -> None:
    session_id = start_in(client, home / "projects", "sleeper")
    url = f"/api/sessions/{session_id}/profile"
    assert client.post(url, json={"profile": "sleeper"}).status_code == 422  # already that
    assert client.post(url, json={"profile": "shell"}).status_code == 422  # a terminal
    assert client.post(url, json={"profile": "nope"}).status_code == 404
    assert client.post(url, json={"profile": "chooser"}).status_code == 422  # needs a model
    assert client.post(url, json={"profile": "chooser", "model": "plain"}).status_code == 200
    assert client.post("/api/sessions/nope/profile", json={"profile": "sleeper"}).status_code == 404


def test_agents_tell_where_they_keep_their_conversations(client: TestClient) -> None:
    kept = {a["name"]: a["conversations"] for a in client.get("/api/agents").json()}
    assert kept["talker"] == kept["talker_too"] == "claude"
    assert kept["sleeper"] is None


def start_narrow(client: TestClient, folder: Path, model: str, effort: str) -> str:
    body = {
        "profile": "narrow", "path": str(folder), "resume": False, "effort": effort,
        "ultracode": False, "conversation": None, "model": model,
    }  # fmt: skip
    session_id: str = client.post("/api/sessions", json=body).json()["id"]
    return session_id


def test_model_change_takes_the_level_chosen_for_the_new_model(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    folder = home / "projects"
    session_id = start_narrow(client, folder, "wide", "max")
    url = f"/api/sessions/{session_id}/model"
    # The folder's "max" is not one the other model takes: without a level the change fails,
    # and the agent stays as it was.
    assert client.post(url, json={"model": "narrow"}).status_code == 422
    assert client.get("/api/sessions").json()[0]["chosen_model"] == "wide"
    # With a level of the new model it goes through and the folder keeps that level.
    assert client.post(url, json={"model": "narrow", "effort": "medium"}).status_code == 200
    changed = client.get("/api/sessions").json()[0]
    assert changed["chosen_model"] == "narrow" and changed["effort"] == "medium"
    # A level the model does not take is refused.
    assert client.post(url, json={"model": "wide", "effort": "medium"}).status_code == 422
    assert client.post(url, json={"model": "wide", "effort": "max"}).status_code == 200


def test_profile_change_takes_the_level_for_the_chosen_model(
    client: TestClient, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    session_id = start_in(client, home / "projects", "sleeper")
    url = f"/api/sessions/{session_id}/profile"
    # "max" is not a level the "narrow" model takes.
    refused = client.post(url, json={"profile": "narrow", "model": "narrow", "effort": "max"})
    assert refused.status_code == 422
    assert client.get("/api/sessions").json()[0]["profile"] == "sleeper"
    switched = client.post(url, json={"profile": "narrow", "model": "narrow", "effort": "medium"})
    assert switched.status_code == 200 and switched.json()["profile"] == "narrow"
    assert client.get("/api/sessions").json()[0]["effort"] == "medium"


async def idle_tunnel(*_arguments: object) -> None:
    """Stands in for ssh: the test's "other machine" is already at the tunnel's end."""
    await asyncio.Event().wait()


@pytest.fixture
def other_machine(
    config: Config, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """A second Agent-Orc on a socket, at the end of the tunnel to host "Aragon"."""
    # A short path: a socket's address holds 107 bytes.
    state = Path(tempfile.mkdtemp(prefix="orc"))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    local_socket = state_dir() / "run" / "host-Aragon.sock"
    prepare_socket(local_socket)
    on_socket = config.model_copy(update={"server": ServerConfig(socket=local_socket)})
    app = create_app(on_socket, None, static_dir=None, clock=clock)
    server = uvicorn.Server(
        uvicorn.Config(app, uds=str(local_socket), log_level="warning", loop="asyncio")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started
    yield
    server.should_exit = True
    thread.join(10)
    shutil.rmtree(state)


@pytest.fixture
def mini(
    config: Config, clock: FakeClock, other_machine: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """This machine's Agent-Orc, logged in; its hosts: "Aragon" (up) and "Gone" (nothing there)."""
    monkeypatch.setattr("agent_orc.api.keep_tunnel_open", idle_tunnel)
    hosts = {name: HostConfig(ssh=["nowhere"], socket="unused") for name in ("Aragon", "Gone")}
    with_hosts = config.model_copy(update={"hosts": hosts})
    # Entered, so the app keeps one event loop (its HTTP sessions belong to it).
    with TestClient(
        create_app(with_hosts, new_credentials(PASSWORD), static_dir=None, clock=clock)
    ) as c:
        assert c.post("/api/login", json={"password": PASSWORD}).status_code == 204
        yield c


def test_the_hosts_and_whether_they_answer(mini: TestClient) -> None:
    listed = mini.get("/api/hosts").json()
    assert listed["self"] == socket.gethostname()
    assert listed["hosts"] == [
        {"name": "Aragon", "online": True},
        {"name": "Gone", "online": False},
    ]


def test_another_machines_app_is_handed_on_through_this_ones_login(mini: TestClient) -> None:
    assert mini.get("/hosts/Aragon/api/me").json() == {"authenticated": True}
    assert mini.get("/hosts/Aragon/api/agents").json()[0]["name"] == "sleeper"
    mini.cookies.clear()
    assert mini.get("/hosts/Aragon/api/me").status_code == 401
    assert mini.get("/api/hosts").status_code == 401


def test_a_host_without_an_answer_or_a_name_is_told_so(mini: TestClient) -> None:
    gone = mini.get("/hosts/Gone/api/me")
    assert gone.status_code == 502
    assert gone.json()["error"] == "HostUnreachableError"
    assert mini.get("/hosts/Nowhere/api/me").status_code == 404


def test_the_address_without_a_slash_goes_to_the_one_with(mini: TestClient) -> None:
    redirect = mini.get("/hosts/Aragon", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "Aragon/"


def test_what_is_sent_reaches_the_other_machine(mini: TestClient, home: Path) -> None:
    folder = home / "projects" / "far"
    folder.mkdir()
    started = mini.post(
        "/hosts/Aragon/api/sessions",
        json={
            "profile": "shell", "path": str(folder), "resume": False, "effort": None,
            "ultracode": False, "conversation": None, "workspace": None,
        },
    )  # fmt: skip
    assert started.status_code == 200
    assert [s["id"] for s in mini.get("/hosts/Aragon/api/sessions").json()] == [
        started.json()["id"]
    ]
    # An error of the other machine arrives as its own.
    assert mini.get("/hosts/Aragon/api/files?path=/no/such/place").status_code == 403


def test_a_file_arrives_as_the_other_machine_sends_it(mini: TestClient, home: Path) -> None:
    (home / "projects" / "far.txt").write_bytes(b"far away\n" * 10000)
    answer = mini.get(
        "/hosts/Aragon/api/files/raw", params={"path": str(home / "projects" / "far.txt")}
    )
    assert answer.status_code == 200
    assert answer.content == b"far away\n" * 10000
    assert answer.headers["content-type"].startswith("text/plain")


def test_a_terminal_works_through_the_tunnel(
    mini: TestClient, home: Path, socket_name: str
) -> None:
    folder = home / "projects" / "far"
    session_id = start_shell(mini, folder)  # on this machine's own server; the shell is shared
    url = f"/hosts/Aragon{terminal_url(session_id)}"
    with mini.websocket_connect(url, headers=ORIGIN) as terminal:
        read_until(terminal, "READY")
        terminal.send_text(json.dumps({"type": "input", "data": "far-away\r"}))
        read_until(terminal, "far-away")
        # Ended by the server, as in the tests above: leaving the `with` would cancel the app
        # while it still winds the tmux client down, and now and then that fails the test.
        assert end_from_the_server(terminal, socket_name) == WS_CLOSE_SERVICE_RESTART
    assert refused_code_at(mini, url, {"origin": "https://evil.example"}) == 4403
    mini.cookies.clear()
    assert refused_code_at(mini, url, ORIGIN) == 4401


def refused_code_at(client: TestClient, url: str, headers: dict[str, str]) -> int:
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        client.websocket_connect(url, headers=headers),
    ):
        pass
    code: int = refused.value.code
    return code
