"""Reading along in AI-Connect and writing to its agents as the user.

AI-Connect is no package of Agent-Orc and brings its own dependencies, so it runs as a program of
its own that speaks JSON lines (the "peers" section of the config names it): one process per open
page reads along, one process per message sends it. The user token is handed on from the browser
and never stored; it reaches the program on stdin, not in its arguments, where ps would show it.
"""

import asyncio
import json
import subprocess
from collections.abc import AsyncIterator
from typing import Any

from agent_orc.config import PeersConfig

# A message carries the file a peer attached, so a line may be far longer than asyncio's 64 KiB.
MAX_LINE_BYTES = 16 * 1024 * 1024


class PeerSendError(RuntimeError):
    """The bridge refused the message or cannot be reached."""


class UserTokenRefusedError(PeerSendError):
    """The bridge does not know the user token."""


async def observe(config: PeersConfig, quiet_seconds: float) -> AsyncIterator[str | None]:
    """The program's lines as they come (peers, past messages, then live events), and None after
    `quiet_seconds` without one. Ends with the program, whose last line then says why."""
    arguments = ["observe", "--hours", str(config.hours), "--limit", str(config.limit)]
    process = await asyncio.create_subprocess_exec(
        *config.command,
        *arguments,
        cwd=config.directory,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        limit=MAX_LINE_BYTES,
    )
    assert process.stdout is not None
    try:
        while True:
            try:
                line = await asyncio.wait_for(process.stdout.readline(), quiet_seconds)
            except TimeoutError:
                yield None
                continue
            if not line:
                return
            yield line.decode().rstrip("\n")
    finally:
        if process.returncode is None:
            process.terminate()
        await process.wait()


def send(config: PeersConfig, token: str, recipients: list[str], content: str) -> list[Any]:
    """Sends `content` as User:<user_name> to each recipient ("*" for every peer online); per
    recipient the message id and whether it was online."""
    request = {"token": token, "as": config.user_name, "to": recipients, "content": content}
    result = subprocess.run(
        [*config.command, "send"],
        cwd=config.directory,
        input=json.dumps(request),
        capture_output=True,
        text=True,
    )
    reply: dict[str, Any] = json.loads(result.stdout)
    if result.returncode == 0:
        return list(reply["sent"])
    if reply["error"] == "token_refused":
        raise UserTokenRefusedError("user token refused")
    raise PeerSendError(reply.get("message") or reply["error"])
