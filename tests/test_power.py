from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_orc import power
from agent_orc.config import PowerConfig, default_config_text, parse_config
from agent_orc.power import (
    LINUX_COMMANDS,
    PowerCommandError,
    commands_for,
    run_command,
    windows_commands,
    windows_system32,
)

LINUX_RELEASE = "6.8.0-45-generic"
WSL_RELEASE = "6.6.87.2-microsoft-standard-WSL2"


def test_linux_uses_systemctl_with_fixed_commands() -> None:
    assert commands_for(LINUX_RELEASE, "") == LINUX_COMMANDS == {
        "suspend": ["systemctl", "--no-ask-password", "suspend"],
        "poweroff": ["systemctl", "--no-ask-password", "poweroff"],
    }


def test_wsl_switches_windows_and_not_its_own_linux(tmp_path: Path) -> None:
    # 18.11.2026: systemctl suspend under WSL put only WSL to sleep, Windows ran on.
    (tmp_path / "c" / "Windows" / "System32").mkdir(parents=True)
    mounts = f"none /usr/lib/wsl/drivers 9p ro 0 0\nC:\\ {tmp_path / 'c'} 9p rw 0 0\n"
    system32 = tmp_path / "c" / "Windows" / "System32"
    commands = commands_for(WSL_RELEASE, mounts)
    assert commands == windows_commands(system32)
    assert commands["poweroff"] == [str(system32 / "shutdown.exe"), "/s", "/t", "0"]
    suspend = commands["suspend"]
    assert suspend[0] == str(system32 / "WindowsPowerShell" / "v1.0" / "powershell.exe")
    # Standby, not hibernation, and Wake-on-LAN stays allowed (disableWakeEvent false).
    assert "SetSuspendState('Suspend', $false, $false)" in suspend[-1]
    assert all("systemctl" not in part for argv in commands.values() for part in argv)


def test_wsl_without_a_windows_drive_is_a_clear_error() -> None:
    assert windows_system32("tmpfs /tmp tmpfs rw 0 0\n") is None
    with pytest.raises(PowerCommandError, match="Windows"):
        commands_for(WSL_RELEASE, "tmpfs /tmp tmpfs rw 0 0\n")


def test_the_power_setting_is_read_and_off_by_default() -> None:
    assert parse_config(default_config_text()).power is None
    config = parse_config(default_config_text() + "\npower: {suspend: true}\n")
    assert config.power == PowerConfig(suspend=True, poweroff=False)


@pytest.mark.parametrize(
    "power_setting, message",
    [
        ("{suspend: yes please}", "suspend"),
        ("{poweroff: 3}", "poweroff"),
        ("{reboot: true}", "reboot"),
        ("true", "power"),
    ],
)
def test_a_bad_power_setting_is_refused_at_load(power_setting: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_config(default_config_text() + f"\npower: {power_setting}\n")


@pytest.mark.anyio
async def test_the_runner_reports_exit_code_and_stderr() -> None:
    # A harmless stand-in command: the real ones are never run by a test.
    assert await run_command(["sh", "-c", "echo refused >&2; exit 2"]) == (2, "refused")
    assert await run_command(["true"]) == (0, "")


@pytest.mark.anyio
async def test_a_command_still_running_counts_as_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    # Windows' SetSuspendState returns only after waking up: not an error, and not killed.
    monkeypatch.setattr(power, "ACCEPTED_AFTER_SECONDS", 0.2)
    assert await run_command(["sleep", "1"]) is None
    assert len(power._still_running) == 1
    # It is reaped in the background once it ends, and then let go.
    await next(iter(power._still_running))
    assert not power._still_running
