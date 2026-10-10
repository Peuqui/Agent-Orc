import asyncio
import subprocess
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_orc import hosts
from agent_orc.config import HostConfig, default_config_text, parse_config
from agent_orc.hosts import _relative_location, tunnel_command


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
