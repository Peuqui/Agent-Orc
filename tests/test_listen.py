import os
import socket
from pathlib import Path

import pytest

from agent_orc.listen import SocketFolderError, prepare_socket


def test_the_folder_is_made_closed_to_others(tmp_path: Path) -> None:
    path = tmp_path / "run" / "orc.sock"
    prepare_socket(path)
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_a_folder_open_to_others_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "run"
    folder.mkdir(mode=0o755)
    folder.chmod(0o755)
    with pytest.raises(SocketFolderError, match="closed to others"):
        prepare_socket(folder / "orc.sock")


def test_an_old_socket_goes_but_no_other_file(tmp_path: Path) -> None:
    path = tmp_path / "run" / "orc.sock"
    prepare_socket(path)
    old = socket.socket(socket.AF_UNIX)
    old.bind(str(path))
    old.close()
    assert path.is_socket()
    prepare_socket(path)
    assert not os.path.lexists(path)

    path.write_text("not a socket")
    with pytest.raises(SocketFolderError, match="no socket"):
        prepare_socket(path)
    assert path.read_text() == "not a socket"


def test_a_path_too_long_for_a_socket_is_refused_clearly(tmp_path: Path) -> None:
    with pytest.raises(SocketFolderError, match="too long"):
        prepare_socket(tmp_path / ("x" * 120) / "orc.sock")
