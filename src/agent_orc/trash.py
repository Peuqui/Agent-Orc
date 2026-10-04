"""The user's home trash, following the freedesktop.org Trash specification,
so items trashed here also show up in the desktop's trash and vice versa."""

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

INFO_SUFFIX = ".trashinfo"
INFO_HEADER = "[Trash Info]"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class TrashEntryNotFoundError(LookupError):
    pass


class RestoreConflictError(FileExistsError):
    pass


@dataclass(frozen=True)
class TrashEntry:
    id: str
    original_path: Path
    deleted_at: str
    is_dir: bool


def home_trash_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "Trash"


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


class Trash:
    def __init__(self, trash_dir: Path) -> None:
        self._files = trash_dir / "files"
        self._info = trash_dir / "info"

    def move(self, path: Path) -> TrashEntry:
        self._files.mkdir(parents=True, exist_ok=True)
        self._info.mkdir(parents=True, exist_ok=True)
        deleted_at = datetime.now().strftime(DATE_FORMAT)
        entry_id = self._reserve_info(path, deleted_at)
        shutil.move(path, self._files / entry_id)
        return TrashEntry(entry_id, path, deleted_at, (self._files / entry_id).is_dir())

    def list(self) -> list[TrashEntry]:
        if not self._info.is_dir():
            return []
        entries = [self._read_entry(info) for info in self._info.glob(f"*{INFO_SUFFIX}")]
        present = [entry for entry in entries if (self._files / entry.id).exists()]
        return sorted(present, key=lambda entry: entry.deleted_at, reverse=True)

    def restore(self, entry_id: str) -> Path:
        entry = self._read_entry(self._info_path(entry_id))
        if entry.original_path.exists():
            raise RestoreConflictError(str(entry.original_path))
        shutil.move(self._files / entry_id, entry.original_path)
        self._info_path(entry_id).unlink()
        return entry.original_path

    def entry(self, entry_id: str) -> TrashEntry:
        return self._read_entry(self._info_path(entry_id))

    def delete(self, entry_id: str) -> None:
        info = self._info_path(entry_id)
        _remove(self._files / entry_id)
        info.unlink()

    def empty(self) -> None:
        for entry in self.list():
            self.delete(entry.id)

    def _reserve_info(self, path: Path, deleted_at: str) -> str:
        """Create the .trashinfo file exclusively; this claims the name (as the spec asks)."""
        content = f"{INFO_HEADER}\nPath={quote(str(path))}\nDeletionDate={deleted_at}\n"
        counter = 1
        while True:
            entry_id = path.name if counter == 1 else f"{path.name}.{counter}"
            try:
                with (self._info / f"{entry_id}{INFO_SUFFIX}").open("x", encoding="utf-8") as f:
                    f.write(content)
            except FileExistsError:
                counter += 1
                continue
            if not (self._files / entry_id).exists():
                return entry_id
            (self._info / f"{entry_id}{INFO_SUFFIX}").unlink()
            counter += 1

    def _info_path(self, entry_id: str) -> Path:
        if "/" in entry_id or entry_id in ("", ".", ".."):
            raise TrashEntryNotFoundError(entry_id)
        info = self._info / f"{entry_id}{INFO_SUFFIX}"
        if not info.is_file():
            raise TrashEntryNotFoundError(entry_id)
        return info

    def _read_entry(self, info: Path) -> TrashEntry:
        fields = dict(
            line.split("=", 1) for line in info.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )  # fmt: skip
        entry_id = info.name.removesuffix(INFO_SUFFIX)
        return TrashEntry(
            id=entry_id,
            original_path=Path(unquote(fields["Path"])),
            deleted_at=fields["DeletionDate"],
            is_dir=(self._files / entry_id).is_dir(),
        )
