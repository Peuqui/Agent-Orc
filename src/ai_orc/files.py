"""File manager operations. Callers pass paths already checked by AccessScope."""

import re
from dataclasses import dataclass
from pathlib import Path


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
    modified_ns: int


def validate_name(name: str, pattern: str) -> None:
    if not re.fullmatch(pattern, name):
        raise InvalidNameError(name)


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


def read_text(path: Path, max_bytes: int) -> TextFile:
    stat = path.stat()
    if stat.st_size > max_bytes:
        raise FileTooLargeError(str(path))
    try:
        content = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise NotTextError(str(path)) from error
    return TextFile(content=content, modified_ns=stat.st_mtime_ns)


def write_text(path: Path, content: str, expected_modified_ns: int | None, max_bytes: int) -> int:
    """Write a text file and return its new modification time.

    expected_modified_ns None creates a new file; otherwise the file must be unchanged
    since it was read. Writing in place keeps permissions such as the executable bit.
    """
    data = content.encode("utf-8")
    if len(data) > max_bytes:
        raise FileTooLargeError(str(path))
    if expected_modified_ns is None:
        with path.open("xb") as handle:
            handle.write(data)
    else:
        if path.stat().st_mtime_ns != expected_modified_ns:
            raise FileConflictError(str(path))
        path.write_bytes(data)
    return path.stat().st_mtime_ns
