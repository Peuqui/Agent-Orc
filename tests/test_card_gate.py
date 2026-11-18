import asyncio
import json
import socket
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
import pytest
import yaml
from aiohttp import web
from fastapi.testclient import TestClient

from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.card_gate import TurnedAway, create_gate_server
from agent_orc.config import Config, default_config_text, parse_config
from agent_orc.gate_token import session_token

BACKEND_KEY = "backend-secret"
SESSION = "horarium-a1b2c3"
MODEL = "glm-x"
HOLD = {"since": "2026-11-14T20:55:00+01:00", "reason": "vllm-research Messung"}
MESSAGE = {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_until_listening(port: int, timeout_s: float = 10) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return
        except ConnectionRefusedError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.01)


@dataclass
class Fake:
    """llama-swap and GPU-Orc as far as the gate asks them."""

    running: list[dict[str, str]] = field(default_factory=list)
    held: dict[str, str] | None = None
    seen: list[web.Request] = field(default_factory=list)
    messages: int = 0


@asynccontextmanager
async def served(app: web.Application, port: int) -> AsyncIterator[None]:
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    try:
        yield
    finally:
        await runner.cleanup()


def llama_swap_app(fake: Fake) -> web.Application:
    async def models(request: web.Request) -> web.Response:
        fake.seen.append(request)
        return web.json_response({"data": [{"id": MODEL}]})

    async def running(request: web.Request) -> web.Response:
        fake.seen.append(request)
        return web.json_response({"running": fake.running})

    async def messages(request: web.Request) -> web.StreamResponse:
        fake.seen.append(request)
        fake.messages += 1
        answer = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await answer.prepare(request)
        for index in range(3):
            await answer.write(f"data: part{index}\n\n".encode())
            await asyncio.sleep(0.2)
        return answer

    app = web.Application()
    app.router.add_get("/v1/models", models)
    app.router.add_get("/running", running)
    app.router.add_post("/v1/messages", messages)
    return app


def gpu_orc_app(fake: Fake) -> web.Application:
    async def loading(request: web.Request) -> web.Response:
        return web.json_response({"loading": [], "held": fake.held})

    app = web.Application()
    app.router.add_get("/loading", loading)
    return app


def gate_config(llama_swap_port: int, gpu_orc_port: int | None, gate_port: int) -> Config:
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["backends"] = {
        "local": {
            "label": "Local",
            "base_urls": [f"http://127.0.0.1:{llama_swap_port}"],
            "key": BACKEND_KEY,
            "key_variable": "ANTHROPIC_API_KEY",
            **({"gpu_orc": {"port": gpu_orc_port}} if gpu_orc_port is not None else {}),
        }
    }
    raw["card_gate"] = {
        "port": gate_port,
        "refusal": "Karten gehalten: {reason} (seit {since}).",
        "resume_prompt": "weiter",
        "check_seconds": 30,
    }
    return parse_config(yaml.safe_dump(raw))


Scenario = Callable[[str, Fake, TurnedAway, aiohttp.ClientSession], Awaitable[None]]


def run_gate(
    scenario: Scenario, *, gpu_orc_answers: bool = True, with_gpu_orc: bool = True
) -> None:
    async def run() -> None:
        fake = Fake()
        turned_away = TurnedAway()
        swap_port, orc_port, gate_port = free_port(), free_port(), free_port()
        config = gate_config(swap_port, orc_port if with_gpu_orc else None, gate_port)
        server = create_gate_server(config, turned_away)
        orc = served(gpu_orc_app(fake), orc_port) if gpu_orc_answers else _nothing()
        async with served(llama_swap_app(fake), swap_port), orc:
            task = asyncio.create_task(server.serve())
            while not server.started:
                await asyncio.sleep(0.01)
            try:
                async with aiohttp.ClientSession() as client:
                    await scenario(f"http://127.0.0.1:{gate_port}/local", fake, turned_away, client)
            finally:
                server.should_exit = True
                await task

    asyncio.run(run())


@asynccontextmanager
async def _nothing() -> AsyncIterator[None]:
    yield


def api_key() -> dict[str, str]:
    return {"x-api-key": session_token(SESSION)}


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))


def test_a_false_or_missing_mark_is_refused_with_401() -> None:
    async def scenario(
        base: str, fake: Fake, turned: TurnedAway, client: aiohttp.ClientSession
    ) -> None:
        for headers in ({}, {"x-api-key": "sk-no-key-required"}, {"authorization": "Bearer x.y"}):
            async with client.post(f"{base}/v1/messages", json=MESSAGE, headers=headers) as answer:
                assert answer.status == 401
                body = await answer.json()
                assert body["type"] == "error"
                assert body["error"]["type"] == "authentication_error"
        assert fake.messages == 0

    run_gate(scenario)


def test_a_running_model_goes_through_streamed_with_the_backends_key() -> None:
    async def scenario(
        base: str, fake: Fake, turned: TurnedAway, client: aiohttp.ClientSession
    ) -> None:
        fake.running = [{"model": MODEL, "state": "ready"}]
        fake.held = HOLD  # no matter: the model is loaded already
        loop = asyncio.get_running_loop()
        # The mark as a bearer token (ANTHROPIC_AUTH_TOKEN) is as good.
        headers = {"authorization": f"Bearer {session_token(SESSION)}"}
        async with client.post(f"{base}/v1/messages", json=MESSAGE, headers=headers) as answer:
            assert answer.status == 200
            arrivals = []
            async for chunk in answer.content.iter_any():
                arrivals.append((loop.time(), chunk))
        assert b"".join(chunk for _, chunk in arrivals) == b"".join(
            f"data: part{index}\n\n".encode() for index in range(3)
        )
        assert len(arrivals) >= 3
        assert arrivals[-1][0] - arrivals[0][0] > 0.2  # not held back until the end
        sent = fake.seen[-1]
        assert sent.headers["x-api-key"] == BACKEND_KEY
        assert "authorization" not in sent.headers
        assert session_token(SESSION) not in json.dumps(dict(sent.headers))
        assert turned.waiting() == {}

    run_gate(scenario)


def test_a_model_that_does_not_run_under_a_hold_is_turned_away_and_remembered() -> None:
    async def scenario(
        base: str, fake: Fake, turned: TurnedAway, client: aiohttp.ClientSession
    ) -> None:
        fake.running = [{"model": "other", "state": "ready"}]
        fake.held = HOLD
        async with client.post(f"{base}/v1/messages", json=MESSAGE, headers=api_key()) as answer:
            assert answer.status == 503
            body = await answer.json()
        assert body["type"] == "error"
        assert body["error"]["type"] == "overloaded_error"
        assert (
            body["error"]["message"] == f"Karten gehalten: {HOLD['reason']} (seit {HOLD['since']})."
        )
        assert fake.messages == 0
        waiting = turned.waiting()
        assert list(waiting) == [SESSION]
        assert (waiting[SESSION].backend, waiting[SESSION].reason) == ("local", HOLD["reason"])
        turned.clear(SESSION)
        assert turned.waiting() == {}

    run_gate(scenario)


def test_a_model_that_does_not_run_without_a_hold_goes_through() -> None:
    async def scenario(
        base: str, fake: Fake, turned: TurnedAway, client: aiohttp.ClientSession
    ) -> None:
        async with client.post(f"{base}/v1/messages", json=MESSAGE, headers=api_key()) as answer:
            assert answer.status == 200
            await answer.read()
        assert fake.messages == 1
        assert turned.waiting() == {}

    run_gate(scenario)


def test_a_backend_without_gpu_orc_is_not_checked() -> None:
    async def scenario(
        base: str, fake: Fake, turned: TurnedAway, client: aiohttp.ClientSession
    ) -> None:
        async with client.post(f"{base}/v1/messages", json=MESSAGE, headers=api_key()) as answer:
            assert answer.status == 200
            await answer.read()
        assert fake.messages == 1

    run_gate(scenario, with_gpu_orc=False)


def test_a_silent_gpu_orc_turns_the_request_away_and_loads_nothing() -> None:
    async def scenario(
        base: str, fake: Fake, turned: TurnedAway, client: aiohttp.ClientSession
    ) -> None:
        async with client.post(f"{base}/v1/messages", json=MESSAGE, headers=api_key()) as answer:
            assert answer.status == 503
            body = await answer.json()
        assert body["error"]["type"] == "overloaded_error"
        assert "GPU-Orc" in body["error"]["message"]
        assert fake.messages == 0

    run_gate(scenario, gpu_orc_answers=False)


def test_a_request_without_a_model_goes_through_unchecked() -> None:
    async def scenario(
        base: str, fake: Fake, turned: TurnedAway, client: aiohttp.ClientSession
    ) -> None:
        fake.held = HOLD
        async with client.get(f"{base}/v1/models", headers=api_key()) as answer:
            assert answer.status == 200
            assert (await answer.json())["data"][0]["id"] == MODEL
        # The last request llama-swap saw is the handed-on one (the probe of the address is Bearer).
        assert fake.seen[-1].headers["x-api-key"] == BACKEND_KEY
        assert session_token(SESSION) not in json.dumps(dict(fake.seen[-1].headers))
        assert turned.waiting() == {}

    run_gate(scenario)


def test_an_unknown_backend_is_404() -> None:
    async def scenario(
        base: str, fake: Fake, turned: TurnedAway, client: aiohttp.ClientSession
    ) -> None:
        url = base.removesuffix("/local") + "/nowhere/v1/messages"
        async with client.post(url, json=MESSAGE, headers=api_key()) as answer:
            assert answer.status == 404
            body = await answer.json()
        assert body["type"] == "error"
        assert body["error"]["type"] == "not_found_error"

    run_gate(scenario)


def test_the_app_runs_the_gate_beside_itself_and_ends_it(tmp_path: Path) -> None:
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["files"]["base_dir"] = str(tmp_path)
    raw["tmux"]["socket_name"] = f"gate-test-{free_port()}"
    raw["card_gate"] = {
        "port": free_port(),
        "refusal": "r",
        "resume_prompt": "p",
        "check_seconds": 1,
    }
    config = parse_config(yaml.safe_dump(raw))
    assert config.card_gate is not None
    url = f"http://127.0.0.1:{config.card_gate.port}/local/v1/messages"

    def ask() -> int:
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=b"{}"))
        except urllib.error.HTTPError as error:
            return error.code
        raise AssertionError("the gate let a request without a mark through")

    with TestClient(create_app(config, new_credentials("a-long-enough-password"), static_dir=None)):
        # The app starts the gate as a task and does not wait for its socket: the test does.
        wait_until_listening(config.card_gate.port)
        assert ask() == 401
    with pytest.raises(urllib.error.URLError):
        ask()
