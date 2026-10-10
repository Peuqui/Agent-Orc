"""Other machines' Agent-Orc, reached through SSH tunnels and handed on under /hosts/<name>/.

Every machine runs an Agent-Orc of its own that listens on a socket without a login (see
listen.py). This one keeps an SSH tunnel to each socket open and passes requests for
/hosts/<name>/... on to it as they are: the other machine's whole app (pages, API, live streams,
terminals) is then reachable through this one's login, which is the only one there is.
"""

import asyncio
import logging
import os
import signal
import time
from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from fastapi import Request, WebSocket
from fastapi.responses import Response, StreamingResponse
from starlette.websockets import WebSocketState

from agent_orc.config import HostConfig
from agent_orc.listen import SocketFolderError, prepare_socket

logger = logging.getLogger(__name__)

# The address the other Agent-Orc is asked at; only the socket decides where it goes.
UPSTREAM = "http://host/"
# The pause between attempts to open a tunnel doubles from the first to the last.
RECONNECT_FIRST_SECONDS = 2.0
RECONNECT_LAST_SECONDS = 30.0
# ssh gives up a tunnel whose machine stays silent for this long times three.
ALIVE_INTERVAL_SECONDS = 15
# ssh watches a standing tunnel, not one that is still being made (a machine that took the
# connection but never answers keeps it for ever): the local socket must show within this time.
TUNNEL_SETUP_SECONDS = 20.0
TUNNEL_SETUP_POLL_SECONDS = 0.2
CONNECT_TIMEOUT_SECONDS = 5
ONLINE_CHECK_SECONDS = 3
WS_CLOSE_UNREACHABLE = 1011
# Close codes that only say how a connection ended and must not be sent.
WS_CLOSE_RESERVED = {1005, 1006, 1015}
# Of the headers, those that belong to one connection only.
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
# Not handed on to the other machine: where the request was addressed, the login here (nothing
# there is asked for), and the length (the body is sent whole, aiohttp counts it).
NOT_FORWARDED = HOP_BY_HOP | {"host", "cookie", "content-length"}


class HostUnreachableError(RuntimeError):
    """The tunnel to the machine is down or its Agent-Orc does not answer."""


class UnknownHostError(LookupError):
    """No machine of this name is configured."""


def tunnel_command(local_socket: Path, config: HostConfig) -> list[str]:
    return [
        "ssh",
        "-N",
        "-o", "BatchMode=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-o", f"ServerAliveInterval={ALIVE_INTERVAL_SECONDS}",
        "-o", "ServerAliveCountMax=3",
        "-o", "StreamLocalBindUnlink=yes",
        "-L", f"{local_socket}:{config.socket}",
        *config.ssh,
    ]  # fmt: skip


def end_orphan_tunnels(command: list[str]) -> list[int]:
    """Ends the processes that run exactly this command and are not ours: tunnels of an earlier
    Agent-Orc, which a restart of the service leaves behind (systemd ends only its main process).
    The whole command is compared and only the user's own processes are looked at, so nothing
    else is touched; the ones ended are returned."""
    ended: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            arguments = (entry / "cmdline").read_bytes().rstrip(b"\0").decode().split("\0")
            parent = next(
                int(line.split()[1])
                for line in (entry / "status").read_text().splitlines()
                if line.startswith("PPid:")
            )
        except (OSError, StopIteration):  # gone while looked at
            continue
        if arguments == command and parent != os.getpid():
            os.kill(int(entry.name), signal.SIGTERM)
            ended.append(int(entry.name))
    return ended


async def end_unless_listening(process: asyncio.subprocess.Process, local_socket: Path) -> None:
    """Ends the tunnel's ssh when its local socket stays away, so the next try can start."""
    deadline = time.monotonic() + TUNNEL_SETUP_SECONDS
    while time.monotonic() < deadline:
        if local_socket.exists():
            return
        await asyncio.sleep(TUNNEL_SETUP_POLL_SECONDS)
    logger.warning("host tunnel: no socket after %s s, ending ssh", TUNNEL_SETUP_SECONDS)
    process.terminate()


async def keep_tunnel_open(name: str, local_socket: Path, config: HostConfig) -> None:
    """Runs the tunnel to the machine, and again whenever it ends, until cancelled."""
    delay = RECONNECT_FIRST_SECONDS
    for orphan in end_orphan_tunnels(tunnel_command(local_socket, config)):
        logger.warning("host %s: ended tunnel %s of an earlier run", name, orphan)
    while True:
        try:
            prepare_socket(local_socket)
        except SocketFolderError as error:
            logger.error("host %s: %s", name, error)
            return
        started = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                *tunnel_command(local_socket, config),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as error:
            logger.error("host %s: ssh does not start: %s", name, error)
        else:
            setup_watch = asyncio.create_task(end_unless_listening(process, local_socket))
            try:
                _, errors = await process.communicate()
            finally:
                setup_watch.cancel()
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
            logger.warning(
                "host %s: tunnel ended (exit %s): %s",
                name,
                process.returncode,
                errors.decode(errors="replace").strip(),
            )
            if time.monotonic() - started > RECONNECT_LAST_SECONDS:
                delay = RECONNECT_FIRST_SECONDS  # it held for a while: begin again quickly
        await asyncio.sleep(delay)
        delay = min(delay * 2, RECONNECT_LAST_SECONDS)


class HostLink:
    """The way to one machine's Agent-Orc: HTTP over the local end of its tunnel."""

    def __init__(self, name: str, local_socket: Path) -> None:
        self.name = name
        self.local_socket = local_socket
        self._session: aiohttp.ClientSession | None = None

    def session(self) -> aiohttp.ClientSession:
        # Made on first use, inside the running loop. A connection is not kept after its request:
        # a tunnel that came up again would leave a kept one dead.
        if self._session is None:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.UnixConnector(path=str(self.local_socket), force_close=True),
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=CONNECT_TIMEOUT_SECONDS),
                # Handed on as it came, with its Content-Encoding.
                auto_decompress=False,
            )
        return self._session

    async def is_online(self) -> bool:
        check = aiohttp.ClientTimeout(total=ONLINE_CHECK_SECONDS)
        try:
            async with self.session().get(f"{UPSTREAM}api/me", timeout=check) as response:
                return response.status == 200
        except (aiohttp.ClientError, OSError, TimeoutError):
            return False

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


def _upstream_url(path: str, query: str) -> str:
    return f"{UPSTREAM}{path}" + (f"?{query}" if query else "")


def _relative_location(location: str, path: str, prefix: str) -> str:
    """A redirect of the other machine's app, as it is to be followed through this one.

    Its static files send "/dir" on to "/dir/"; that becomes the last part of the address with a
    slash, which holds wherever this app itself is served."""
    target = urlsplit(location)
    if target.path == f"/{path}/":
        return f"{path.rsplit('/', 1)[-1]}/" + (f"?{target.query}" if target.query else "")
    return f"{prefix}{target.path}" + (f"?{target.query}" if target.query else "")


def _response_headers(headers: Iterable[tuple[str, str]], path: str, prefix: str) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for name, value in headers:
        if name.lower() in HOP_BY_HOP:
            continue
        forwarded[name] = (
            _relative_location(value, path, prefix) if name.lower() == "location" else value
        )
    return forwarded


async def _chunks(upstream: aiohttp.ClientResponse) -> AsyncIterator[bytes]:
    try:
        async for chunk in upstream.content.iter_any():
            yield chunk
    finally:
        upstream.close()


async def forward(request: Request, link: HostLink, path: str) -> Response:
    """The request for /hosts/<name>/<path> as the other machine's Agent-Orc answers it; its
    answer is streamed back, so live streams (server-sent events) arrive as they are sent."""
    headers = [
        (name, value) for name, value in request.headers.items() if name not in NOT_FORWARDED
    ]
    body = await request.body()
    try:
        upstream = await link.session().request(
            request.method,
            _upstream_url(path, request.url.query),
            headers=headers,
            data=body or None,
            allow_redirects=False,
        )
    except (aiohttp.ClientError, OSError, TimeoutError) as error:
        raise HostUnreachableError(link.name) from error
    prefix = f"/hosts/{link.name}"
    return StreamingResponse(
        _chunks(upstream),
        status_code=upstream.status,
        headers=_response_headers(upstream.headers.items(), path, prefix),
    )


def _close_code(code: int | None) -> int:
    return WS_CLOSE_UNREACHABLE if code is None or code in WS_CLOSE_RESERVED else code


async def forward_websocket(websocket: WebSocket, link: HostLink, path: str) -> None:
    """Joins the browser's WebSocket to the other machine's, message for message; when one ends
    the other is closed with the same code (the app tells a gone session from a restart by it)."""
    await websocket.accept()
    try:
        upstream = await link.session().ws_connect(
            _upstream_url(path, websocket.url.query), max_msg_size=0
        )
    except (aiohttp.ClientError, OSError, TimeoutError):
        await websocket.close(WS_CLOSE_UNREACHABLE)
        return

    async def to_upstream() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("text") is not None:
                await upstream.send_str(message["text"])
            elif message.get("bytes") is not None:
                await upstream.send_bytes(message["bytes"])

    async def to_client() -> None:
        async for message in upstream:
            if message.type == aiohttp.WSMsgType.TEXT:
                await websocket.send_text(message.data)
            elif message.type == aiohttp.WSMsgType.BINARY:
                await websocket.send_bytes(message.data)
            else:
                return

    tasks = [asyncio.create_task(to_upstream()), asyncio.create_task(to_client())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        code = upstream.close_code
        await upstream.close()
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(_close_code(code))
