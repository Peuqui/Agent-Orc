import os
from pathlib import Path

import pytest

from agent_orc import files
from agent_orc.config import default_config_text, parse_config

PATTERN = parse_config(default_config_text()).files.name_pattern
MAX_BYTES = 1000


def test_list_directory_dirs_first_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("x")
    (tmp_path / "A.txt").write_text("x")
    (tmp_path / "zdir").mkdir()
    (tmp_path / "dangling").symlink_to(tmp_path / "missing")
    names = [entry.name for entry in files.list_directory(tmp_path)]
    assert names == ["zdir", "A.txt", "b.txt", "dangling"]


def test_create_folder(tmp_path: Path) -> None:
    assert files.create_folder(tmp_path, "my-project", PATTERN) == tmp_path / "my-project"
    assert (tmp_path / "my-project").is_dir()
    with pytest.raises(FileExistsError):
        files.create_folder(tmp_path, "my-project", PATTERN)


@pytest.mark.parametrize("name", ["", "..", ".hidden", "a/b", "with space", "x" * 101])
def test_invalid_names_are_rejected(tmp_path: Path, name: str) -> None:
    with pytest.raises(files.InvalidNameError):
        files.create_folder(tmp_path, name, PATTERN)


def test_rename_refuses_to_overwrite(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    with pytest.raises(FileExistsError):
        files.rename(tmp_path / "a.txt", "b.txt", PATTERN)
    assert files.rename(tmp_path / "a.txt", "c.txt", PATTERN) == tmp_path / "c.txt"


def test_read_text(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("Grüße", encoding="utf-8")
    text = files.read_text(path, MAX_BYTES)
    assert text.content == "Grüße"
    assert text.version == str(path.stat().st_mtime_ns)


def test_read_rejects_large_and_binary_files(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("x" * (MAX_BYTES + 1))
    (tmp_path / "blob.bin").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(files.FileTooLargeError):
        files.read_text(tmp_path / "big.txt", MAX_BYTES)
    with pytest.raises(files.NotTextError):
        files.read_text(tmp_path / "blob.bin", MAX_BYTES)


def test_write_detects_concurrent_change(tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text("v1")
    loaded = files.read_text(path, MAX_BYTES)
    path.write_text("changed by agent")
    changed = int(loaded.version) + 1
    os.utime(path, ns=(changed, changed))
    with pytest.raises(files.FileConflictError):
        files.write_text(path, "v2", loaded.version, MAX_BYTES)
    assert path.read_text() == "changed by agent"


def test_write_keeps_executable_bit(tmp_path: Path) -> None:
    path = tmp_path / "run.sh"
    path.write_text("echo 1")
    path.chmod(0o755)
    version = files.write_text(path, "echo 2", files.file_version(path), MAX_BYTES)
    assert path.read_text() == "echo 2"
    assert path.stat().st_mode & 0o111
    assert version == files.file_version(path)


def test_write_new_file_does_not_overwrite(tmp_path: Path) -> None:
    files.write_text(tmp_path / "new.txt", "hello", None, MAX_BYTES)
    with pytest.raises(FileExistsError):
        files.write_text(tmp_path / "new.txt", "again", None, MAX_BYTES)
    assert (tmp_path / "new.txt").read_text() == "hello"


def test_write_rejects_too_large_content(tmp_path: Path) -> None:
    with pytest.raises(files.FileTooLargeError):
        files.write_text(tmp_path / "x.txt", "x" * (MAX_BYTES + 1), None, MAX_BYTES)


def test_a_file_name_is_made_safe() -> None:
    assert files.safe_file_name("Stimme Codine (1).mp3") == "Stimme-Codine-1-.mp3"
    assert files.safe_file_name("../../etc/passwd") == "passwd"
    assert files.safe_file_name("...") == files.UNNAMED


def test_an_upload_never_takes_a_name_that_is_taken(tmp_path: Path) -> None:
    for expected in ("a.wav", "a-2.wav", "a-3.wav"):
        target, handle = files.create_upload(tmp_path, "a.wav")
        handle.close()
        assert target == tmp_path / expected
    target, handle = files.create_upload(tmp_path, "ohne")
    handle.close()
    other, other_handle = files.create_upload(tmp_path, "ohne")
    other_handle.close()
    assert (target.name, other.name) == ("ohne", "ohne-2")
