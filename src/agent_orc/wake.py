"""Wake-on-LAN: the magic packet that switches a machine on (see HostConfig.wake)."""

import socket

MAC_BYTES = 6
MAGIC_REPEATS = 16


class WakeNotConfiguredError(LookupError):
    """The machine has no `wake` setting, so there is nowhere to send a packet."""


def magic_packet(mac: str) -> bytes:
    """Six 0xFF bytes, then the machine's MAC address sixteen times."""
    return b"\xff" * MAC_BYTES + bytes.fromhex(mac.replace(":", "")) * MAGIC_REPEATS


def send_magic_packet(mac: str, broadcast: str, port: int) -> None:
    """Sends the packet as a UDP broadcast. Nothing answers it: the machine just starts."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp.sendto(magic_packet(mac), (broadcast, port))
