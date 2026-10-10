"""File manager operations. Callers pass paths already checked by AccessScope."""

import itertools
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

UNSAFE_NAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]+")
UNNAMED = "attachment"


class InvalidNameError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


class NotTextError(ValueError):
    pass


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
    """The name of a file as it is kept here: its last part, with every run of characters other
    than letters, digits, ".", "_" and "-" made one "-" (the file may come from anywhere)."""
    return UNSAFE_NAME_CHARACTERS.sub("-", Path(name).name).strip("-.") or UNNAMED


def create_upload(folder: Path, name: str) -> tuple[Path, BinaryIO]:
    """Opens a new file in the folder for an upload under that name (see safe_file_name). A name
    that is taken gets a number before its suffix; nothing is ever overwritten."""
    safe_name = safe_file_name(name)
    stem, suffix = os.path.splitext(safe_name)
    for number in itertools.count(1):
        target = folder / (safe_name if number == 1 else f"{stem}-{number}{suffix}")
        try:
            return target, target.open("xb")
        except FileExistsError:
            continue
    raise AssertionError("unreachable")  # count() does not end


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
