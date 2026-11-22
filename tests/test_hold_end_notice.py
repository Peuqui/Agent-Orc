"""The owner of a GPU-Orc hold is told in its session that a person asked for the end
(hold_end_notice.py)."""

import asyncio
import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.config import Config, HoldEndNoticeConfig, default_config_text
from agent_orc.context import store_activity
from agent_orc.gpu_orc_client import GpuOrcError, Hold, TrafficLight
from agent_orc.hold_end_notice import HoldEndNotice
from agent_orc.sessions import AgentSession, SessionManager

MINI = "http://mini:5070"
ARAGON = "http://aragon:5070"
PASSWORD = "a-long-enough-password"
OWNER = "vllm-research"
NOTICE = HoldEndNoticeConfig(text="{machine}: {by} asked {owner} for the end.", check_seconds=0.05)
ACTIVE = Hold(OWNER, "Messung", None, None, "2026-11-20T09:00:00+01:00", "active", None, None, None)
ASKED = replace(ACTIVE, end_requested_by="Peuqui")


class FakeGpuOrcs:
    """The GPU-Orcs by the address the client is made for, each answering /loading with its hold."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.holds: dict[str, Hold | None] = {}
        self.down: set[str] = set()
        monkeypatch.setattr("agent_orc.gpuorc.GpuOrc", lambda url, token=None: Bound(self, url))
        # The address of a backend is its first address here: nothing is probed.
        monkeypatch.setattr("agent_orc.holds.reachable_base_url", lambda b, *_: b.base_urls[0])


class Bound:
    def __init__(self, orcs: FakeGpuOrcs, url: str) -> None:
        self.orcs = orcs
        self.url = url

    def loading(self) -> TrafficLight:
        if self.url in self.orcs.down:
            raise GpuOrcError(f"GPU-Orc not reachable at {self.url}")
        hold = self.orcs.holds.get(self.url)
        requested = hold is not None and hold.state == "requested"
        return TrafficLight((), None if requested else hold, hold if requested else None)


def backend(label: str, url: str) -> dict[str, Any]:
    return {
        "label": label,
        "base_urls": [url],
        "key": "k",
        "key_variable": "ANTHROPIC_API_KEY",
        "gpu_orc": {"port": 5070},
    }


@pytest.fixture
def notice_config(tmp_path: Path, socket_name: str) -> Config:
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["server"]["cookie_secure"] = False
    raw["files"]["base_dir"] = str(tmp_path)
    raw["tmux"]["socket_name"] = socket_name
    raw["backends"] = {
        "local": backend("Mini", "http://mini:8080"),
        "far": backend("Aragon", "http://aragon:8080"),
    }
    raw["agents"] = {"shell": {"label": "S", "start": ["sh"], "resume": ["sh"], "settings": {}}}
    raw["hold_end_notice"] = NOTICE.model_dump()
    return Config.model_validate(raw)


class Sessions:
    """The sessions of the tests and what was typed into them; `start` can mark a session as
    working the way the agent's hook does."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        self.listed: list[AgentSession] = []
        self.typed: list[tuple[str, str]] = []

    def start(
        self, folder: str, busy: bool = False, running: bool = True, terminal: bool = False
    ) -> str:
        session_id = f"session-{len(self.listed)}"
        self.listed.append(
            AgentSession(
                session_id, "p", Path("/x") / folder, running, None, 0.0, terminal, None, None
            )
        )
        store_activity(session_id, busy)
        return session_id

    def type_line(self, session_id: str, line: str) -> None:
        self.typed.append((session_id, line))


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Sessions:
    return Sessions(monkeypatch, tmp_path)


@pytest.fixture
def orcs(monkeypatch: pytest.MonkeyPatch) -> FakeGpuOrcs:
    return FakeGpuOrcs(monkeypatch)


def watcher(config: Config, sessions: Sessions) -> HoldEndNotice:
    return HoldEndNotice(
        config, NOTICE, lambda *_: None, lambda: sessions.listed, sessions.type_line
    )


def test_the_owners_session_is_told_once_with_the_placeholders_filled(
    notice_config: Config, sessions: Sessions, orcs: FakeGpuOrcs
) -> None:
    orcs.holds[ARAGON] = ASKED
    sessions.start("other")
    session_id = sessions.start(OWNER)
    notices = watcher(notice_config, sessions)
    notices.notify_once()
    notices.notify_once()
    # {machine} is the label of the backend that names the GPU-Orc.
    assert sessions.typed == [(session_id, f"Aragon: Peuqui asked {OWNER} for the end.")]


def test_a_requested_hold_or_one_nobody_asked_the_end_of_is_not_told(
    notice_config: Config, sessions: Sessions, orcs: FakeGpuOrcs
) -> None:
    sessions.start(OWNER)
    orcs.holds[MINI] = replace(ASKED, state="requested")
    orcs.holds[ARAGON] = ACTIVE
    watcher(notice_config, sessions).notify_once()
    assert sessions.typed == []


def test_a_working_session_is_told_at_once(
    notice_config: Config, sessions: Sessions, orcs: FakeGpuOrcs
) -> None:
    orcs.holds[ARAGON] = ASKED
    session_id = sessions.start(OWNER, busy=True)
    notices = watcher(notice_config, sessions)
    notices.notify_once()
    notices.notify_once()
    # Claude Code queues what is typed during a turn: no waiting for the session to rest.
    assert [typed[0] for typed in sessions.typed] == [session_id]


def test_a_new_hold_of_the_same_owner_is_told_anew(
    notice_config: Config, sessions: Sessions, orcs: FakeGpuOrcs
) -> None:
    session_id = sessions.start(OWNER)
    notices = watcher(notice_config, sessions)
    orcs.holds[ARAGON] = ASKED
    notices.notify_once()
    # The hold ends, a new one of the same owner starts later and gets an end request, too.
    orcs.holds[ARAGON] = None
    notices.notify_once()
    orcs.holds[ARAGON] = replace(ASKED, since="2026-11-21T09:00:00+01:00")
    notices.notify_once()
    assert [typed[0] for typed in sessions.typed] == [session_id, session_id]


def test_what_is_still_pending_is_not_told_again_while_it_stays(
    notice_config: Config, sessions: Sessions, orcs: FakeGpuOrcs
) -> None:
    sessions.start(OWNER)
    notices = watcher(notice_config, sessions)
    orcs.holds[ARAGON] = ASKED
    for _ in range(3):
        notices.notify_once()
    assert len(sessions.typed) == 1


def test_without_a_running_session_of_the_owner_nothing_is_typed(
    notice_config: Config, sessions: Sessions, orcs: FakeGpuOrcs
) -> None:
    orcs.holds[ARAGON] = ASKED
    sessions.start("someone-else")
    sessions.start(OWNER, running=False)
    watcher(notice_config, sessions).notify_once()
    assert sessions.typed == []


def test_the_folders_plain_terminal_is_never_typed_into(
    notice_config: Config, sessions: Sessions, orcs: FakeGpuOrcs
) -> None:
    orcs.holds[ARAGON] = ASKED
    sessions.start(OWNER, terminal=True)
    agent = sessions.start(OWNER)
    watcher(notice_config, sessions).notify_once()
    assert [typed[0] for typed in sessions.typed] == [agent]


def test_a_gpu_orc_that_does_not_answer_is_no_reason_to_type(
    notice_config: Config, sessions: Sessions, orcs: FakeGpuOrcs
) -> None:
    orcs.holds[ARAGON] = ASKED
    orcs.down.add(ARAGON)
    sessions.start(OWNER)
    watcher(notice_config, sessions).notify_once()
    assert sessions.typed == []


def test_the_loop_goes_on_after_a_failing_round_and_tells_in_a_later_one(
    notice_config: Config,
    sessions: Sessions,
    orcs: FakeGpuOrcs,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    orcs.holds[ARAGON] = ASKED
    sessions.start(OWNER)
    failures = [True]

    def type_line(session_id: str, line: str) -> None:
        if failures:
            failures.pop()
            raise RuntimeError("tmux is gone")
        sessions.type_line(session_id, line)

    notices = HoldEndNotice(
        notice_config, NOTICE, lambda *_: None, lambda: sessions.listed, type_line
    )

    async def scenario() -> None:
        task = asyncio.create_task(notices.run())
        while not sessions.typed:
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    with caplog.at_level(logging.ERROR):
        asyncio.run(asyncio.wait_for(scenario(), 10))
    assert len(sessions.typed) == 1
    assert [r for r in caplog.records if "end request failed" in r.getMessage()]


def test_the_app_tells_the_owner_only_with_the_block_in_the_config(
    notice_config: Config, tmp_path: Path, orcs: FakeGpuOrcs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    typed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        SessionManager, "type_line", lambda _self, sid, line: typed.append((sid, line))
    )
    orcs.holds[ARAGON] = ASKED
    owner_folder = tmp_path / OWNER
    owner_folder.mkdir()
    # Sessions of the profile run `cat`.
    raw = notice_config.model_dump(mode="json")
    raw["agents"]["shell"] = {
        "label": "S",
        "start": ["sh", "-c", "exec cat"],
        "resume": ["sh"],
        "settings": {},
    }
    body = {
        "profile": "shell",
        "path": str(owner_folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
    }

    def run_app(with_block: bool) -> list[tuple[str, str]]:
        typed.clear()
        raw["hold_end_notice"] = NOTICE.model_dump() if with_block else None
        app = create_app(Config.model_validate(raw), new_credentials(PASSWORD), static_dir=None)
        with TestClient(app) as client:
            client.post("/api/login", json={"password": PASSWORD})
            session_id = client.post("/api/sessions", json=body).json()["id"]
            for _ in range(30):
                if typed:
                    break
                time.sleep(0.1)
            client.delete(f"/api/sessions/{session_id}")
        return list(typed)

    assert run_app(with_block=False) == []
    told = run_app(with_block=True)
    assert len(told) == 1 and "Peuqui asked vllm-research" in told[0][1]
