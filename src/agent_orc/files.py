"""File manager operations. Callers pass paths already checked by AccessScope."""

import itertools
import os
import re
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

UNSAFE_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]+")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
UNNAMED = "attachment"


class InvalidNameError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


class NotTextError(ValueError):
    pass


class InvalidTransferError(ValueError):
    """A folder cannot be moved or copied into itself."""


class FileConflictError(RuntimeError):
    """The file changed on disk since the editor loaded it."""


@dataclass(frozen=True)
class FileEntry:
    name: str
    path: Path
    is_dir: bool
    size: int
    modified: float


@dataclass(frozen=True)
class TextFile:
    content: str
    # Opaque version token (the mtime in ns as text). A string, because a nanosecond
    # timestamp exceeds the integer precision of JavaScript numbers.
    version: str


def _version(stat: os.stat_result) -> str:
    return str(stat.st_mtime_ns)


def file_version(path: Path) -> str:
    return _version(path.stat())


def validate_name(name: str, pattern: str) -> None:
    if not re.fullmatch(pattern, name):
        raise InvalidNameError(name)


def safe_file_name(name: str) -> str:
    """The name of a file as an agent is to be told it (an attachment): its last part, with every
    run of characters other than letters, digits, ".", "_" and "-" made one "-", so that it needs
    no quoting in a command or a prompt."""
    return UNSAFE_NAME_CHARACTERS.sub("-", Path(name).name).strip("-.") or UNNAMED


def upload_file_name(name: str) -> str:
    """The name of an uploaded file: its last part, as it is (spaces, umlauts and a leading "."
    as in ".gitignore" stay). Only what no name can hold goes: the path and control characters."""
    last = CONTROL_CHARACTERS.sub("", name.rsplit("/", 1)[-1])
    return UNNAMED if last in ("", ".", "..") else last


def upload_directory(folder: Path, subfolder: str) -> Path:
    """Where an uploaded file goes: a path of plain names below the folder ("" is the folder
    itself), as a dropped folder keeps its structure. "." and ".." are refused."""
    parts = [CONTROL_CHARACTERS.sub("", part) for part in subfolder.split("/") if part]
    if any(part in (".", "..") for part in parts):
        raise InvalidNameError(subfolder)
    return folder.joinpath(*parts)


def numbered_names(name: str) -> Iterator[str]:
    """`name`, then the same with a number before its suffix: "a.wav", "a-2.wav", "a-3.wav" ..."""
    stem, suffix = os.path.splitext(name)
    yield name
    for number in itertools.count(2):
        yield f"{stem}-{number}{suffix}"


def unused_path(folder: Path, name: str) -> Path:
    """`name` in the folder, or with a number when that is taken: the way every new file or
    folder here finds its place without overwriting anything."""
    return next(
        folder / candidate
        for candidate in numbered_names(name)
        if not os.path.lexists(folder / candidate)
    )


def transfer_into(paths: list[Path], folder: Path, copy: bool) -> list[Path]:
    """Moves (or copies) each path into the folder and returns where each one landed. A name that
    is taken there gets a number; a path that is in the folder already stays where it is (when
    moved). A folder cannot go into itself."""
    for path in paths:
        if folder == path or folder.is_relative_to(path):
            raise InvalidTransferError(str(path))
    landed = []
    for path in paths:
        if not copy and path.parent == folder:
            landed.append(path)
            continue
        target = unused_path(folder, path.name)
        if not copy:
            shutil.move(path, target)
        elif path.is_dir():
            shutil.copytree(path, target, symlinks=True)
        else:
            shutil.copy2(path, target)
        landed.append(target)
    return landed


def create_new_file(folder: Path, name: str) -> tuple[Path, BinaryIO]:
    """Opens a new file in the folder under that name. A name that is taken gets a number before
    its suffix: nothing is ever overwritten."""
    for candidate in numbered_names(name):
        target = folder / candidate
        try:
            return target, target.open("xb")
        except FileExistsError:
            continue
    raise AssertionError("unreachable")  # numbered_names does not end


def list_directory(path: Path) -> list[FileEntry]:
    entries = []
    for child in path.iterdir():
        # lstat: a dangling symlink must not break the whole listing.
        stat = child.lstat()
        entries.append(
            FileEntry(
                name=child.name,
                path=child,
                is_dir=child.is_dir(),
                size=stat.st_size,
                modified=stat.st_mtime,
            )
        )
    return sorted(entries, key=lambda entry: (not entry.is_dir, entry.name.casefold()))


def create_folder(parent: Path, name: str, pattern: str) -> Path:
    validate_name(name, pattern)
    folder = parent / name
    folder.mkdir()
    return folder


def rename(path: Path, new_name: str, pattern: str) -> Path:
    validate_name(new_name, pattern)
    target = path.with_name(new_name)
    if target.exists():
        raise FileExistsError(str(target))
    return path.rename(target)


def existing_paths(base: Path, candidates: list[str]) -> dict[str, Path]:
    """Which of the paths an agent mentioned exist, by the text it wrote: absolute, from ~ or
    relative to its folder (base)."""
    found = {}
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            path = base / path
        if path.exists():
            found[candidate] = path.resolve()
    return found


def read_text(path: Path, max_bytes: int) -> TextFile:
    stat = path.stat()
    if stat.st_size > max_bytes:
        raise FileTooLargeError(str(path))
    try:
        content = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise NotTextError(str(path)) from error
    return TextFile(content=content, version=_version(stat))


def write_text(path: Path, content: str, expected_version: str | None, max_bytes: int) -> str:
    """Write a text file and return its new version.

    expected_version None creates a new file; otherwise the file must be unchanged since
    it was read. Writing in place keeps permissions such as the executable bit.
    """
    data = content.encode("utf-8")
    if len(data) > max_bytes:
        raise FileTooLargeError(str(path))
    if expected_version is None:
        with path.open("xb") as handle:
            handle.write(data)
    else:
        if file_version(path) != expected_version:
            raise FileConflictError(str(path))
        path.write_bytes(data)
    return file_version(path)
