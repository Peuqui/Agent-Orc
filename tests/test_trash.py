from pathlib import Path

import pytest

from agent_orc.trash import RestoreConflictError, Trash, TrashEntryNotFoundError


@pytest.fixture
def trash(tmp_path: Path) -> Trash:
    return Trash(tmp_path / "Trash")


@pytest.fixture
def work(tmp_path: Path) -> Path:
    folder = tmp_path / "work"
    folder.mkdir()
    return folder


def test_move_writes_spec_conform_info(trash: Trash, work: Path, tmp_path: Path) -> None:
    path = work / "my file.txt"
    path.write_text("x")
    entry = trash.move(path)
    assert not path.exists()
    assert (tmp_path / "Trash" / "files" / "my file.txt").read_text() == "x"
    info = (tmp_path / "Trash" / "info" / "my file.txt.trashinfo").read_text()
    assert info.startswith("[Trash Info]\nPath=")
    assert "my%20file.txt" in info
    assert trash.list() == [entry]
    assert entry.original_path == path


def test_same_name_twice_gets_unique_ids(trash: Trash, work: Path) -> None:
    for content in ("first", "second"):
        (work / "a.txt").write_text(content)
        trash.move(work / "a.txt")
    assert {entry.id for entry in trash.list()} == {"a.txt", "a.txt.2"}


def test_restore_folder(trash: Trash, work: Path) -> None:
    folder = work / "project"
    (folder / "src").mkdir(parents=True)
    (folder / "src" / "main.py").write_text("print(1)")
    entry = trash.move(folder)
    assert entry.is_dir
    assert trash.restore(entry.id) == folder
    assert (folder / "src" / "main.py").read_text() == "print(1)"
    assert trash.list() == []


def test_restore_refuses_to_overwrite(trash: Trash, work: Path) -> None:
    (work / "a.txt").write_text("old")
    entry = trash.move(work / "a.txt")
    (work / "a.txt").write_text("new")
    with pytest.raises(RestoreConflictError):
        trash.restore(entry.id)
    assert (work / "a.txt").read_text() == "new"


def test_delete_and_empty(trash: Trash, work: Path) -> None:
    for name in ("a.txt", "b.txt"):
        (work / name).write_text(name)
    (work / "dir").mkdir()
    first = trash.move(work / "a.txt")
    trash.move(work / "b.txt")
    trash.move(work / "dir")
    trash.delete(first.id)
    assert {entry.id for entry in trash.list()} == {"b.txt", "dir"}
    trash.empty()
    assert trash.list() == []


@pytest.mark.parametrize("entry_id", ["", ".", "..", "../etc", "missing"])
def test_invalid_ids_are_rejected(trash: Trash, entry_id: str) -> None:
    with pytest.raises(TrashEntryNotFoundError):
        trash.delete(entry_id)


def test_list_on_missing_trash_is_empty(trash: Trash) -> None:
    assert trash.list() == []
