import pytest
from pydantic import ValidationError

from agent_orc.config import parse_config
from agent_orc.wake import magic_packet
from tests.test_hosts import hosts_section


def test_the_magic_packet_is_six_ff_and_the_mac_sixteen_times() -> None:
    packet = magic_packet("aa:bb:cc:dd:ee:ff")
    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    assert packet[6:] == bytes.fromhex("aabbccddeeff") * 16


def host_with_wake(wake: str) -> str:
    return hosts_section(f"  Aragon:\n    ssh: [[x]]\n    socket: /s\n    wake: {wake}\n")


def test_the_wake_setting_is_read_with_port_nine_by_default() -> None:
    config = parse_config(host_with_wake('{mac: "AA:bb:cc:dd:ee:ff", broadcast: "192.168.0.255"}'))
    assert config.hosts is not None
    wake = config.hosts["Aragon"].wake
    assert wake is not None
    assert (wake.mac, wake.broadcast, wake.port) == ("AA:bb:cc:dd:ee:ff", "192.168.0.255", 9)


@pytest.mark.parametrize(
    "wake, message",
    [
        ('{mac: "aa:bb:cc:dd:ee", broadcast: "192.168.0.255"}', "MAC address"),
        ('{mac: "aa-bb-cc-dd-ee-ff", broadcast: "192.168.0.255"}', "MAC address"),
        ('{mac: "aa:bb:cc:dd:ee:gg", broadcast: "192.168.0.255"}', "MAC address"),
        ('{mac: "aa:bb:cc:dd:ee:ff", broadcast: "192.168.0"}', "IPv4"),
        ('{mac: "aa:bb:cc:dd:ee:ff", broadcast: "fe80::1"}', "IPv4"),
        ('{mac: "aa:bb:cc:dd:ee:ff", broadcast: "192.168.0.255", port: 0}', "port"),
        ('{mac: "aa:bb:cc:dd:ee:ff", broadcast: "192.168.0.255", extra: 1}', "extra"),
    ],
)
def test_a_bad_wake_setting_is_refused_at_load(wake: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_config(host_with_wake(wake))
