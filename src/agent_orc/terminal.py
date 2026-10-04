"""Bridges a browser terminal (WebSocket) to an agent's tmux session through a PTY."""

import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import termios
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from agent_orc.sessions import exact_target

TERM = "xterm-256color"
READ_SIZE = 65536
STOP_TIMEOUT_SECONDS = 5


def _make_controlling_terminal() -> None:
    # Runs in the child after setsid(): the PTY on stdin becomes its controlling terminal,
    # so window size changes reach the tmux client as SIGWINCH.
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def _set_window_size(fd: int, cols: int, rows: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


async def bridge(websocket: WebSocket, socket_name: str, session_id: str) -> None:
    """Attach a tmux client in a fresh PTY and pump bytes until either side ends.

    Client messages are JSON text frames: {"type": "input", "data": str} or
    {"type": "resize", "cols": int, "rows": int}. Terminal output goes out as binary frames.
    Closing the terminal only detaches; the agent keeps running.
    """
    master, slave = pty.openpty()
    process = await asyncio.create_subprocess_exec(
        "tmux", "-L", socket_name, "attach-session", "-t", exact_target(session_id),
        stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, "TERM": TERM},
        start_new_session=True,
        preexec_fn=_make_controlling_terminal,
    )  # fmt: skip
    os.close(slave)

    loop = asyncio.get_running_loop()
    output: asyncio.Queue[bytes] = asyncio.Queue()

    def on_readable() -> None:
        try:
            data = os.read(master, READ_SIZE)
        except OSError:
            # Linux reports EIO on the master once the tmux client has exited.
            data = b""
        output.put_nowait(data)
        if not data:
            loop.remove_reader(master)

    async def pump_output() -> None:
        while data := await output.get():
            await websocket.send_bytes(data)

    async def pump_input() -> None:
        while True:
            message: dict[str, Any] = json.loads(await websocket.receive_text())
            if message["type"] == "input":
                os.write(master, message["data"].encode())
            elif message["type"] == "resize":
                _set_window_size(master, int(message["cols"]), int(message["rows"]))
            else:
                raise ValueError(f"unknown terminal message type: {message['type']}")

    loop.add_reader(master, on_readable)
    output_task = asyncio.create_task(pump_output())
    input_task = asyncio.create_task(pump_input())
    try:
        done, _ = await asyncio.wait([output_task, input_task], return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (output_task, input_task):
            task.cancel()
        await asyncio.gather(output_task, input_task, return_exceptions=True)
        loop.remove_reader(master)
        if process.returncode is None:
            process.send_signal(signal.SIGHUP)
            await asyncio.wait_for(process.wait(), STOP_TIMEOUT_SECONDS)
        os.close(master)

    for task in done:
        error = task.exception()
        # A browser disconnect is the normal way out; anything else is a real error.
        if isinstance(error, WebSocketDisconnect):
            return
        if error is not None:
            raise error
    # The tmux client ended (session stopped or agent gone): tell the browser.
    await websocket.close()
