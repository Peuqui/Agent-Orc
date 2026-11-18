"""The card gate: a small server in front of llama-swap for the local sessions of Agent-Orc.

See docs/PLAN-2026-11-14-kartentor.md. Claude Code talks to it instead of llama-swap (the address
is http://127.0.0.1:<port>/<backend>), and llama-swap loads a model on request, onto cards that
GPU-Orc's hold keeps for somebody else. So a request that would load a model is turned away while
the hold lasts, with the reason, in the format of Anthropic's API; everything else goes through as
it is. The session is remembered, so Agent-Orc can wake it once the cards are free.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from agent_orc.backends import (
    CHECK_SECONDS,
    LOCAL_ADDRESS,
    RUNNING_PATH,
    BackendError,
    fetch_json,
    model_is_ready,
    reachable_base_url,
    resolve_key,
)
from agent_orc.config import BackendConfig, Config
from agent_orc.events import SHUTDOWN_GRACE_SECONDS
from agent_orc.gate_token import token_session
from agent_orc.gpu_orc_client import GpuOrcError
from agent_orc.gpuorc import held
from agent_orc.hosts import chunks, request_headers, response_headers

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
# The headers that carry the session's mark; they must not reach llama-swap.
MARK_HEADERS = {"x-api-key", "authorization"}
BEARER_PREFIX = "bearer "
API_KEY_HEADER = "x-api-key"
API_KEY_VARIABLE = "ANTHROPIC_API_KEY"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Turned:
    """A session whose request was turned away."""

    backend: str
    reason: str
    at: datetime = field(default_factory=datetime.now)


class TurnedAway:
    """The sessions turned away and still waiting for the cards (read by the card and the waking).
    No lock: the gate's loop writes, and a copy of a dict is whole even when read from a thread."""

    def __init__(self) -> None:
        self._sessions: dict[str, Turned] = {}

    def add(self, session_id: str, backend: str, reason: str) -> None:
        self._sessions[session_id] = Turned(backend, reason)

    def waiting(self) -> dict[str, Turned]:
        return dict(self._sessions)

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class GpuOrcSilentError(RuntimeError):
    """GPU-Orc does not tell whether the cards are held."""


def error_response(status: int, kind: str, message: str) -> JSONResponse:
    """An error as Anthropic's API words it, which Claude Code understands."""
    return JSONResponse(
        {"type": "error", "error": {"type": kind, "message": message}}, status_code=status
    )


def mark_of(request: Request) -> str | None:
    """Claude Code sends the key as x-api-key (ANTHROPIC_API_KEY) or as a bearer token
    (ANTHROPIC_AUTH_TOKEN)."""
    key = request.headers.get(API_KEY_HEADER)
    if key:
        return key
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith(BEARER_PREFIX):
        return authorization[len(BEARER_PREFIX) :]
    return None


def backend_auth_header(backend: BackendConfig, key: str) -> tuple[str, str]:
    """The backend's own key, in the header its key_variable stands for."""
    if backend.key_variable == API_KEY_VARIABLE:
        return API_KEY_HEADER, key
    return "authorization", f"Bearer {key}"


def requested_model(body: bytes) -> str | None:
    """The model a JSON body asks for; None for a body without one (nothing is loaded then)."""
    try:
        document = json.loads(body)
    except ValueError:
        return None
    model = document.get("model") if isinstance(document, dict) else None
    return model if isinstance(model, str) else None


async def get_json(session: aiohttp.ClientSession, url: str, headers: dict[str, str]) -> Any:
    timeout = aiohttp.ClientTimeout(total=CHECK_SECONDS)
    async with session.get(url, headers=headers, timeout=timeout) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


async def model_runs(
    session: aiohttp.ClientSession, base_url: str, auth: tuple[str, str], model: str
) -> bool:
    """Whether llama-swap has the model loaded (a failed check says: not loaded)."""
    try:
        listing = await get_json(session, base_url + RUNNING_PATH, dict([auth]))
        return model_is_ready(listing, model)
    except (aiohttp.ClientError, OSError, TimeoutError, KeyError, TypeError, ValueError):
        return False


async def hold_of(backend: BackendConfig, base_url: str) -> dict[str, str] | None:
    """GPU-Orc's hold of the cards, None when there is none. Raises GpuOrcSilentError when GPU-Orc
    does not answer: without knowing, nothing may be loaded."""
    assert backend.gpu_orc is not None
    try:
        return await asyncio.to_thread(held, backend.gpu_orc, base_url)
    except (GpuOrcError, OSError) as error:
        raise GpuOrcSilentError(str(error)) from error


def create_gate_app(config: Config, turned_away: TurnedAway) -> FastAPI:
    assert config.card_gate is not None
    gate = config.card_gate
    backends = config.backends or {}
    sessions: dict[str, aiohttp.ClientSession] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # No total timeout: a model loads for minutes and an answer streams for as long as it takes.
        # Not decompressed here: the answer goes on as the client asked for it.
        sessions["upstream"] = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None), auto_decompress=False
        )
        yield
        await sessions["upstream"].close()

    app = FastAPI(
        title="Agent-Orc card gate",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    async def turn_away(
        session: aiohttp.ClientSession,
        name: str,
        backend: BackendConfig,
        base_url: str,
        auth: tuple[str, str],
        session_id: str,
        body: bytes,
    ) -> Response | None:
        """The answer that turns the request away, None when it may go through."""
        model = requested_model(body)
        if model is None or backend.gpu_orc is None:
            return None
        if await model_runs(session, base_url, auth, model):
            return None
        try:
            hold = await hold_of(backend, base_url)
        except GpuOrcSilentError as error:
            # Remembered as well: the waking asks GPU-Orc again and wakes the session once it
            # answers without a hold.
            reason = f"{error}; nothing is loaded without it"
            turned_away.add(session_id, name, reason)
            logger.warning("card gate: %s turned away for %s: %s", session_id, model, reason)
            return error_response(503, "overloaded_error", reason)
        if hold is None:
            return None
        turned_away.add(session_id, name, hold["reason"])
        logger.info("card gate: %s turned away for %s: held: %s", session_id, model, hold["reason"])
        return error_response(
            503, "overloaded_error", gate.refusal.format(reason=hold["reason"], since=hold["since"])
        )

    @app.api_route("/{backend}/{path:path}", methods=METHODS)
    async def pass_through(request: Request, backend: str, path: str) -> Response:
        mark = mark_of(request)
        session_id = token_session(mark) if mark else None
        if session_id is None:
            return error_response(401, "authentication_error", "no valid session mark")
        backend_config = backends.get(backend)
        if backend_config is None:
            return error_response(404, "not_found_error", f"unknown backend {backend}")
        session = sessions["upstream"]
        try:
            key = resolve_key(backend_config)
            base_url = await asyncio.to_thread(reachable_base_url, backend_config, key, fetch_json)
        except BackendError as error:
            return error_response(502, "api_error", str(error))
        auth = backend_auth_header(backend_config, key)
        body = await request.body()
        refusal = await turn_away(
            session, backend, backend_config, base_url, auth, session_id, body
        )
        if refusal is not None:
            return refusal
        headers = [
            (name, value) for name, value in request_headers(request) if name not in MARK_HEADERS
        ]
        headers.append(auth)
        query = f"?{request.url.query}" if request.url.query else ""
        try:
            upstream = await session.request(
                request.method,
                f"{base_url}{backend_config.anthropic_path}/{path}{query}",
                headers=headers,
                data=body or None,
                allow_redirects=False,
            )
        except (aiohttp.ClientError, OSError, TimeoutError) as error:
            return error_response(
                502, "api_error", f"{backend_config.label} does not answer: {error}"
            )
        return StreamingResponse(
            chunks(upstream),
            status_code=upstream.status,
            headers=response_headers(upstream.headers.items()),
        )

    return app


class GateServer(uvicorn.Server):
    """uvicorn's server beside the app's own: it must not take over the signals (the app's server
    handles them, and ends this one through should_exit)."""

    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


def create_gate_server(config: Config, turned_away: TurnedAway) -> GateServer:
    assert config.card_gate is not None
    server_config = uvicorn.Config(
        create_gate_app(config, turned_away),
        host=LOCAL_ADDRESS,
        port=config.card_gate.port,
        loop="asyncio",
        timeout_graceful_shutdown=SHUTDOWN_GRACE_SECONDS,
    )
    return GateServer(server_config)
