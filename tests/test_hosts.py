import asyncio
import errno
import socket
import subprocess
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_orc import hosts
from agent_orc.config import HostConfig, default_config_text, parse_config
from agent_orc.hosts import (
    HostLink,
    _relative_location,
    connection_result,
    probe,
    ssh_address,
    tunnel_command,
)


def test_the_tunnel_forwards_the_other_machines_socket_to_a_local_one() -> None:
    command = tunnel_command(
        Path("/run/me/host-A.sock"),
        HostConfig(ssh=["-p", "2222", "mp@10.0.0.2"], socket="/r/o.sock"),
    )
    assert command[0] == "ssh"
    assert command[command.index("-L") + 1] == "/run/me/host-A.sock:/r/o.sock"
    # Never asks for a password; without the forward the tunnel is worth nothing.
    assert "BatchMode=yes" in command
    assert "ExitOnForwardFailure=yes" in command
    assert command[-3:] == ["-p", "2222", "mp@10.0.0.2"]


def test_a_redirect_of_the_other_app_stays_below_its_address() -> None:
    # Static files send "/assets" on to "/assets/": the same name, with a slash, wherever we are.
    assert _relative_location("http://host/assets/", "assets", "/hosts/A") == "assets/"
    assert _relative_location("/a/b/", "a/b", "/hosts/A") == "b/"
    assert _relative_location("/login?next=1", "x", "/hosts/A") == "/hosts/A/login?next=1"


def test_the_tunnel_is_opened_again_when_it_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts = tmp_path / "starts"
    # Stands in for ssh: notes the start, ends at once.
    monkeypatch.setattr(
        hosts, "tunnel_command", lambda *_: ["sh", "-c", f"echo x >> {starts}; echo failed >&2"]
    )
    monkeypatch.setattr(hosts, "RECONNECT_FIRST_SECONDS", 0.05)
    monkeypatch.setattr(hosts, "RECONNECT_LAST_SECONDS", 0.1)

    async def run() -> None:
        task = asyncio.create_task(
            hosts.keep_tunnel_open(
                "A", tmp_path / "run" / "host-A.sock", HostConfig(ssh=[], socket="")
            )
        )
        for _ in range(100):
            await asyncio.sleep(0.05)
            if starts.exists() and len(starts.read_text().splitlines()) >= 3:
                break
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(starts.read_text().splitlines()) >= 3


def test_a_tunnel_that_never_shows_its_socket_is_ended_and_opened_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts = tmp_path / "starts"
    # Stands in for an ssh that hangs while connecting: notes the start, then waits.
    monkeypatch.setattr(
        hosts, "tunnel_command", lambda *_: ["sh", "-c", f"echo x >> {starts}; exec sleep 30"]
    )
    monkeypatch.setattr(hosts, "TUNNEL_SETUP_SECONDS", 0.2)
    monkeypatch.setattr(hosts, "RECONNECT_FIRST_SECONDS", 0.05)
    monkeypatch.setattr(hosts, "RECONNECT_LAST_SECONDS", 0.1)

    async def run() -> None:
        task = asyncio.create_task(
            hosts.keep_tunnel_open(
                "A", tmp_path / "run" / "host-A.sock", HostConfig(ssh=[], socket="")
            )
        )
        for _ in range(100):
            await asyncio.sleep(0.05)
            if starts.exists() and len(starts.read_text().splitlines()) >= 2:
                break
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(starts.read_text().splitlines()) >= 2


def test_a_tunnel_of_an_earlier_run_is_ended_and_nothing_else(tmp_path: Path) -> None:
    command = ["sleep", "321.1"]
    # Left behind: its parent shell is gone at once, so it is not ours.
    subprocess.run(["sh", "-c", "sleep 321.1 &"], check=True)
    # Not to be touched: the same command as a child of ours, and another command.
    ours = subprocess.Popen(command)
    other = subprocess.Popen(["sleep", "321.2"])
    try:
        ended = hosts.end_orphan_tunnels(command)
        assert len(ended) == 1
        for _ in range(50):
            if ours.poll() is None and other.poll() is None:
                break
            time.sleep(0.05)
        assert ours.poll() is None
        assert other.poll() is None
        assert hosts.end_orphan_tunnels(command) == []
    finally:
        ours.kill()
        other.kill()
        ours.wait()
        other.wait()


def hosts_section(lines: str) -> str:
    return default_config_text() + "\nhosts:\n" + lines


def test_hosts_are_named_for_an_address() -> None:
    config = parse_config(
        hosts_section('  Aragon:\n    ssh: ["-p", "2222", "mp@10.0.0.2"]\n    socket: /r/o.sock\n')
    )
    assert config.hosts is not None
    assert config.hosts["Aragon"].ssh == ["-p", "2222", "mp@10.0.0.2"]
    with pytest.raises(ValidationError, match="letters, digits"):
        parse_config(hosts_section('  "a/b":\n    ssh: [x]\n    socket: /s\n'))


class Wrapped(Exception):  # noqa: N818
    """A library's own error that carries the real one as its cause."""


def caused_by(error: BaseException) -> Wrapped:
    wrapped = Wrapped("request failed")
    wrapped.__cause__ = error
    return wrapped


@pytest.mark.parametrize(
    ("error", "result"),
    [
        (ConnectionRefusedError(), "refused"),
        (ConnectionResetError(), "refused"),
        (TimeoutError(), "off"),
        (socket.gaierror(socket.EAI_NONAME, "no such name"), "off"),
        (OSError(errno.EHOSTUNREACH, "no route to host"), "off"),
        (OSError(errno.ENETUNREACH, "network is unreachable"), "off"),
        (OSError(errno.ENETDOWN, "network is down"), "off"),
        (caused_by(ConnectionRefusedError()), "refused"),
        (caused_by(caused_by(OSError(errno.EHOSTUNREACH, "no route"))), "off"),
        (Wrapped("no cause at all"), "off"),
    ],
)
def test_a_failed_connection_says_whether_the_machine_is_there(
    error: BaseException, result: str
) -> None:
    assert connection_result(error) == result


def test_a_context_is_followed_like_a_cause() -> None:
    try:
        try:
            raise ConnectionRefusedError
        except ConnectionRefusedError:
            raise Wrapped("while handling") from None
    except Wrapped as error:
        assert connection_result(error) == "refused"


def test_probing_tells_open_refused_and_no_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def hang_up(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    async def listening() -> tuple[str, str, str]:
        server = await asyncio.start_server(hang_up, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            taken = await probe("127.0.0.1", port)
        refused = await probe("127.0.0.1", port)  # nobody listens any more
        monkeypatch.setattr(asyncio, "open_connection", never_answers)
        silent = await probe("10.255.255.1", 22)
        return taken, refused, silent

    assert asyncio.run(listening()) == ("open", "refused", "off")


async def never_answers(*_arguments: object) -> None:
    await asyncio.sleep(10)


def test_the_address_of_a_machine_is_what_ssh_would_connect_to() -> None:
    config = HostConfig(ssh=["-p", "2222", "-o", "HostName=10.0.0.2", "mp@somewhere"], socket="x")
    assert asyncio.run(ssh_address(config)) == ("10.0.0.2", 2222)


def test_a_machine_is_in_the_state_its_agent_orc_and_its_port_say(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link = HostLink("Aragon", Path("/nonexistent/host.sock"), HostConfig(ssh=["x"], socket="x"))

    async def offline() -> bool:
        return False

    async def address(_config: HostConfig) -> tuple[str, int]:
        return "10.0.0.2", 2222

    monkeypatch.setattr(link, "is_online", offline)
    monkeypatch.setattr("agent_orc.hosts.ssh_address", address)
    for connection, state in (("open", "service_off"), ("refused", "ssh_down"), ("off", "off")):

        async def answers(_address: str, _port: int, result: str = connection) -> str:
            return result

        monkeypatch.setattr("agent_orc.hosts.probe", answers)
        assert asyncio.run(link.state()) == state
