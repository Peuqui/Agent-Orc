"""Agent-Orc tells GPU-Orc while sessions on its backends work (work_report.py)."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.backends import backend_of_profile
from agent_orc.config import Config, default_config_text
from agent_orc.context import store_activity
from agent_orc.gpu_orc_client import GpuOrcError
from agent_orc.sessions import AgentSession
from agent_orc.work_report import WorkReporter, work_owner

MINI = "http://mini:5070"
ARAGON = "http://aragon:5070"
PASSWORD = "a-long-enough-password"


class FakeGpuOrcs:
    """The GPU-Orcs by the address the client is made for; `events` holds what they were told:
    (address, "begin" or "end", owner, reason, ttl_s)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.events: list[tuple[str, str, str, str | None, float | None]] = []
        self.down: set[str] = set()
        monkeypatch.setattr("agent_orc.gpuorc.GpuOrc", lambda url, token=None: Bound(self, url))
        # The address of a backend is its first address here: nothing is probed.
        monkeypatch.setattr("agent_orc.holds.reachable_base_url", lambda b, *_: b.base_urls[0])

    def begins(self, address: str) -> list[tuple[str, str | None, float | None]]:
        return [(e[2], e[3], e[4]) for e in self.events if e[:2] == (address, "begin")]

    def ends(self, address: str) -> int:
        return sum(1 for e in self.events if e[:2] == (address, "end"))


class Bound:
    def __init__(self, orcs: FakeGpuOrcs, url: str) -> None:
        self.orcs = orcs
        self.url = url

    def work_begin(self, owner: str, reason: str, ttl_s: float) -> None:
        self._check()
        self.orcs.events.append((self.url, "begin", owner, reason, ttl_s))

    def work_end(self, owner: str) -> None:
        self._check()
        self.orcs.events.append((self.url, "end", owner, None, None))

    def _check(self) -> None:
        if self.url in self.orcs.down:
            raise GpuOrcError(f"GPU-Orc not reachable at {self.url}")


def agent(start: list[str]) -> dict[str, Any]:
    return {"label": "A", "start": start, "resume": start, "settings": {}}


def backend(url: str, gpu_orc: bool = True) -> dict[str, Any]:
    return {
        "label": url,
        "base_urls": [url],
        "key": "k",
        "key_variable": "ANTHROPIC_API_KEY",
        "gpu_orc": {"port": 5070} if gpu_orc else None,
    }


def run_on(name: str) -> list[str]:
    return ["agent-orc", "backend", "run", name, "{model}"]


@pytest.fixture
def work_config(tmp_path: Path, socket_name: str) -> Config:
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["server"]["cookie_secure"] = False
    raw["files"]["base_dir"] = str(tmp_path)
    raw["tmux"]["socket_name"] = socket_name
    raw["gpu_orc_work_poll_seconds"] = 0.1
    raw["backends"] = {
        "local": backend("http://mini:8080"),
        "vllm": backend("http://mini:8000"),  # the same GPU-Orc as "local"
        "far": backend("http://aragon:8080"),
        "cloud": backend("https://cloud", gpu_orc=False),
    }
    raw["agents"] = {
        "claude-local": agent(run_on("local")),
        "claude-vllm": agent(run_on("vllm")),
        "claude-far": agent(run_on("far")),
        "claude-cloud": agent(run_on("cloud")),
        "shell": agent(["sh"]),
    }
    return Config.model_validate(raw)


class Sessions:
    """The sessions of the tests; `busy` marks them as working the way the agent's hook does."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        self.listed: list[AgentSession] = []
        self.waiting: set[str] = set()

    def start(self, profile: str, busy: bool = True) -> str:
        session_id = f"{profile}-{len(self.listed)}"
        self.listed.append(
            AgentSession(session_id, profile, Path("/x"), True, None, 0.0, False, None, None)
        )
        store_activity(session_id, busy)
        return session_id

    def rest(self, session_id: str) -> None:
        store_activity(session_id, busy=False)


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Sessions:
    return Sessions(monkeypatch, tmp_path)


def reporter(config: Config, sessions: Sessions) -> WorkReporter:
    return WorkReporter(config, lambda *_: None, lambda: sessions.listed, lambda: sessions.waiting)


def test_a_working_session_is_reported_to_the_gpu_orc_of_its_backend(
    work_config: Config, sessions: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    orcs = FakeGpuOrcs(monkeypatch)
    sessions.start("claude-far")
    sessions.start("claude-local", busy=False)
    reporter(work_config, sessions).report_once()
    assert orcs.begins(ARAGON) == [(work_owner(), "Agent-Orc: 1 working session(s)", 60)]
    assert orcs.begins(MINI) == []


def test_the_report_ends_once_when_the_last_session_rests(
    work_config: Config, sessions: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    orcs = FakeGpuOrcs(monkeypatch)
    session_id = sessions.start("claude-local")
    work = reporter(work_config, sessions)
    work.report_once()
    sessions.rest(session_id)
    work.report_once()
    work.report_once()
    assert len(orcs.begins(MINI)) == 1
    assert orcs.ends(MINI) == 1


def test_a_session_turned_away_by_the_gate_and_waiting_is_no_work(
    work_config: Config, sessions: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    orcs = FakeGpuOrcs(monkeypatch)
    sessions.waiting.add(sessions.start("claude-local"))
    reporter(work_config, sessions).report_once()
    assert orcs.events == []


def test_backends_on_the_same_gpu_orc_make_one_report(
    work_config: Config, sessions: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    orcs = FakeGpuOrcs(monkeypatch)
    sessions.start("claude-local")
    sessions.start("claude-vllm")
    reporter(work_config, sessions).report_once()
    assert [reason for _, reason, _ in orcs.begins(MINI)] == ["Agent-Orc: 2 working session(s)"]
    assert len(orcs.events) == 1


def test_a_session_on_a_backend_without_gpu_orc_or_on_none_is_no_work(
    work_config: Config, sessions: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    orcs = FakeGpuOrcs(monkeypatch)
    sessions.start("claude-cloud")
    sessions.start("shell")
    reporter(work_config, sessions).report_once()
    assert orcs.events == []


def test_a_gpu_orc_that_does_not_answer_is_logged_once_and_nothing_breaks(
    work_config: Config,
    sessions: Sessions,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    orcs = FakeGpuOrcs(monkeypatch)
    orcs.down.add(MINI)
    sessions.start("claude-local")
    sessions.start("claude-far")
    work = reporter(work_config, sessions)
    with caplog.at_level(logging.INFO):
        work.report_once()
        work.report_once()
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert MINI in warnings[0].getMessage()
        orcs.down.clear()
        work.report_once()
    # The other GPU-Orc was told all the time; this one as soon as it answered.
    assert len(orcs.begins(ARAGON)) == 3
    assert len(orcs.begins(MINI)) == 1
    assert [r for r in caplog.records if "answers again" in r.getMessage()]


def test_stopping_the_reporter_ends_the_report(
    work_config: Config, sessions: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    orcs = FakeGpuOrcs(monkeypatch)
    sessions.start("claude-local")

    async def scenario() -> None:
        task = asyncio.create_task(reporter(work_config, sessions).run())
        while not orcs.begins(MINI):
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
    assert orcs.ends(MINI) == 1


def test_the_owner_names_the_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_orc.catalog.socket.gethostname", lambda: "mini")
    assert work_owner() == "agent-orc@mini"


def test_the_profile_names_its_backend() -> None:
    assert backend_of_profile(Config.model_validate(_raw_profile()).agents["a"]) == "local"
    assert backend_of_profile(Config.model_validate(_raw_profile(["sh"])).agents["a"]) is None


def _raw_profile(start: list[str] | None = None) -> dict[str, Any]:
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["agents"] = {"a": agent(start or run_on("local"))}
    return raw


def test_the_app_reports_working_sessions_and_ends_the_report_as_it_stops(
    work_config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    (tmp_path / "projects").mkdir()
    orcs = FakeGpuOrcs(monkeypatch)
    # Sessions of the profile run `cat` (the arguments after -c are the profile's start command).
    raw = work_config.model_dump(mode="json")
    raw["agents"]["claude-local"] = agent(["sh", "-c", "exec cat", "backend", "run", "local"])
    with TestClient(
        create_app(Config.model_validate(raw), new_credentials(PASSWORD), static_dir=None)
    ) as client:
        client.post("/api/login", json={"password": PASSWORD})
        body = {
            "profile": "claude-local",
            "path": str(tmp_path / "projects"),
            "resume": False,
            "effort": None,
            "ultracode": False,
            "conversation": None,
        }
        session_id = client.post("/api/sessions", json=body).json()["id"]
        store_activity(session_id, busy=True)
        for _ in range(50):
            if orcs.begins(MINI):
                break
            time.sleep(0.1)
        assert orcs.begins(MINI)
        assert orcs.ends(MINI) == 0
    assert orcs.ends(MINI) == 1
