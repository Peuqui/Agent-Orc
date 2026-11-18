"""Putting this machine to sleep or switching it off, when its own config allows it.

On Linux that is systemd's business. Under WSL it is Windows': systemctl there would only put the
Linux machine of WSL to sleep (18.11.2026 on Aragon: Windows ran on, WSL hung until its service was
killed), so the commands are Windows' own programs, reached through the C: drive.
"""

import asyncio
import functools
import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

PowerAction = Literal["suspend", "poweroff"]

# Fixed commands: nothing of the request goes into them. --no-ask-password keeps systemctl from
# waiting for a password nobody can type (the service has no terminal): a polkit refusal is an
# immediate error instead.
LINUX_COMMANDS: dict[PowerAction, list[str]] = {
    "suspend": ["systemctl", "--no-ask-password", "suspend"],
    "poweroff": ["systemctl", "--no-ask-password", "poweroff"],
}

# Standby (S3) through .NET: rundll32's SetSuspendState would hibernate wherever hibernation is on.
# disableWakeEvent = false keeps Wake-on-LAN working.
WINDOWS_SUSPEND = (
    "Add-Type -AssemblyName System.Windows.Forms; "
    "if (-not [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false))"
    " { exit 1 }"
)

# A command that has not ended after this long was accepted: the machine is on its way down.
# Windows' SetSuspendState returns only after waking up; a refusal (polkit, a missing program)
# shows sooner.
ACCEPTED_AFTER_SECONDS = 5

# The kernel's release names WSL ("…-microsoft-standard-WSL2"); /proc/mounts the Windows drives.
OSRELEASE = Path("/proc/sys/kernel/osrelease")
MOUNTS = Path("/proc/mounts")
WINDOWS_DRIVE_FILESYSTEMS = {"9p", "drvfs"}

_still_running: set[asyncio.Future[tuple[bytes, bytes]]] = set()


class PowerNotAllowedError(Exception):
    """This machine's config does not allow the action."""


class PowerCommandError(RuntimeError):
    """The command refused or failed (polkit, an inhibitor, Windows); its message is the text."""


def windows_commands(system32: Path) -> dict[PowerAction, list[str]]:
    powershell = system32 / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return {
        "suspend": [str(powershell), "-NoProfile", "-NonInteractive", "-Command", WINDOWS_SUSPEND],
        "poweroff": [str(system32 / "shutdown.exe"), "/s", "/t", "0"],
    }


def windows_system32(mounts: str) -> Path | None:
    """System32 on the first Windows drive WSL mounted that has one."""
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[2] in WINDOWS_DRIVE_FILESYSTEMS:
            system32 = Path(fields[1]) / "Windows" / "System32"
            if system32.is_dir():
                return system32
    return None


def commands_for(osrelease: str, mounts: str) -> dict[PowerAction, list[str]]:
    if "microsoft" not in osrelease.lower():
        return LINUX_COMMANDS
    system32 = windows_system32(mounts)
    if system32 is None:
        raise PowerCommandError("WSL without a Windows drive that has Windows\\System32 mounted")
    return windows_commands(system32)


@functools.cache
def machine_commands() -> dict[PowerAction, list[str]]:
    """The commands of this machine: Linux' or, under WSL, Windows'."""
    return commands_for(OSRELEASE.read_text(), MOUNTS.read_text())


async def run_command(argv: list[str]) -> tuple[int, str] | None:
    """Starts the command and waits for its end up to ACCEPTED_AFTER_SECONDS: its exit code and what
    it wrote to stderr, or None while it still runs (accepted; it is reaped in the background)."""
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    finished = asyncio.ensure_future(process.communicate())
    done, _ = await asyncio.wait({finished}, timeout=ACCEPTED_AFTER_SECONDS)
    if not done:
        # Held here until it ends: asyncio keeps only weak references to its tasks.
        _still_running.add(finished)
        finished.add_done_callback(_still_running.discard)
        return None
    _, stderr = finished.result()
    return process.returncode or 0, stderr.decode(errors="replace").strip()


async def power(action: PowerAction) -> None:
    """Runs the action's command. Returns once it was accepted: the machine may be gone a moment
    later."""
    argv = machine_commands()[action]
    logger.info("power: %s via %s", action, Path(argv[0]).name)
    result = await run_command(argv)
    if result is None:
        return
    code, stderr = result
    if code != 0:
        raise PowerCommandError(stderr or f"{action} failed with exit code {code}")
