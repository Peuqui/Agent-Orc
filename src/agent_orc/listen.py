"""Where the server listens when it does so on a Unix socket instead of a port.

uvicorn gives its socket file the rights 0666, so what keeps others out is the folder holding it:
it must be the user's alone. Whoever may enter it controls every agent, as with a login.
"""

import os
import stat
from pathlib import Path

FOLDER_MODE = 0o700
OTHERS_MASK = 0o077
# What fits in a socket address on Linux (sun_path is 108 bytes, with the ending zero).
MAX_PATH_BYTES = 107


class SocketFolderError(RuntimeError):
    """The socket's folder or file cannot be used safely."""


def prepare_socket(path: Path) -> None:
    """Make sure `path`'s folder exists, is the user's alone, and no old socket stays in the way."""
    if len(os.fsencode(path)) > MAX_PATH_BYTES:
        raise SocketFolderError(f"{path} is too long for a socket ({MAX_PATH_BYTES} bytes at most)")
    folder = path.parent
    folder.mkdir(mode=FOLDER_MODE, parents=True, exist_ok=True)
    folder_stat = folder.stat()
    if folder_stat.st_uid != os.getuid() or folder_stat.st_mode & OTHERS_MASK:
        raise SocketFolderError(
            f"{folder} must belong to you and be closed to others (chmod {FOLDER_MODE:o} {folder})"
        )
    if path.is_socket():
        # What a stopped server left behind; a running one would have been refused by its port.
        path.unlink()
    elif os.path.lexists(path):
        raise SocketFolderError(
            f"{path} exists and is no socket: {stat.filemode(path.lstat().st_mode)}"
        )
