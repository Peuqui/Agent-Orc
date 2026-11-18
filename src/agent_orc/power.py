"""Putting this machine to sleep or switching it off, when its own config allows it."""

import asyncio
import logging
from typing import Literal

logger = logging.getLogger(__name__)

PowerAction = Literal["suspend", "poweroff"]

# Fixed commands: nothing of the request goes into them. --no-ask-password keeps systemctl from
# waiting for a password nobody can type (the service has no terminal): a polkit refusal is an
# immediate error instead.
POWER_COMMANDS: dict[PowerAction, list[str]] = {
    "suspend": ["systemctl", "--no-ask-password", "suspend"],
    "poweroff": ["systemctl", "--no-ask-password", "poweroff"],
}

# systemctl returns once logind has accepted the request (or refused it), which is quick.
COMMAND_TIMEOUT_SECONDS = 15


class PowerNotAllowedError(Exception):
    """This machine's config does not allow the action."""


class PowerCommandError(RuntimeError):
    """systemctl refused or failed (polkit, an inhibitor); the message is what it said."""


async def run_command(argv: list[str]) -> tuple[int, str]:
    """Runs the command to its end; returns its exit code and what it wrote to stderr."""
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), COMMAND_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise PowerCommandError(
            f"{argv[1:]} did not finish in {COMMAND_TIMEOUT_SECONDS} s"
        ) from None
    return process.returncode or 0, stderr.decode(errors="replace").strip()


async def power(action: PowerAction) -> None:
    """Runs the action's command. Returns when logind has accepted it: the machine may be gone a
    moment later."""
    logger.info("power: running systemctl %s", action)
    code, stderr = await run_command(POWER_COMMANDS[action])
    if code != 0:
        raise PowerCommandError(stderr or f"systemctl {action} failed with exit code {code}")
