import pytest
from pydantic import ValidationError

from agent_orc.config import PowerConfig, default_config_text, parse_config
from agent_orc.power import POWER_COMMANDS, run_command


def test_the_commands_are_fixed() -> None:
    assert POWER_COMMANDS == {
        "suspend": ["systemctl", "--no-ask-password", "suspend"],
        "poweroff": ["systemctl", "--no-ask-password", "poweroff"],
    }


def test_the_power_setting_is_read_and_off_by_default() -> None:
    assert parse_config(default_config_text()).power is None
    config = parse_config(default_config_text() + "\npower: {suspend: true}\n")
    assert config.power == PowerConfig(suspend=True, poweroff=False)


@pytest.mark.parametrize(
    "power, message",
    [
        ("{suspend: yes please}", "suspend"),
        ("{poweroff: 3}", "poweroff"),
        ("{reboot: true}", "reboot"),
        ("true", "power"),
    ],
)
def test_a_bad_power_setting_is_refused_at_load(power: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_config(default_config_text() + f"\npower: {power}\n")


@pytest.mark.anyio
async def test_the_runner_reports_exit_code_and_stderr() -> None:
    # A harmless stand-in command: the real ones are never run by a test.
    assert await run_command(["sh", "-c", "echo refused >&2; exit 2"]) == (2, "refused")
    assert await run_command(["true"]) == (0, "")
