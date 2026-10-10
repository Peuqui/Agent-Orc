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


def test_an_attachment_name_is_made_safe() -> None:
    assert files.safe_file_name("Stimme Codine (1).mp3") == "Stimme-Codine-1-.mp3"
    assert files.safe_file_name("../../etc/passwd") == "passwd"
    assert files.safe_file_name("...") == files.UNNAMED


def test_an_upload_name_stays_as_it_is_but_for_the_path_and_control_characters() -> None:
    assert files.upload_file_name("Stimme Codine (1).mp3") == "Stimme Codine (1).mp3"
    assert files.upload_file_name("Prüfung äöü.txt") == "Prüfung äöü.txt"
    # A project's own files keep their names, the dot files too.
    assert files.upload_file_name(".gitignore") == ".gitignore"
    assert files.upload_file_name("../../etc/passwd") == "passwd"
    assert files.upload_file_name("a\x00b\nc.txt") == "abc.txt"
    for unusable in ("", ".", "..", "x/..", "x/"):
        assert files.upload_file_name(unusable) == files.UNNAMED


def test_a_new_file_never_takes_a_name_that_is_taken(tmp_path: Path) -> None:
    for expected in ("a.wav", "a-2.wav", "a-3.wav"):
        target, handle = files.create_new_file(tmp_path, "a.wav")
        handle.close()
        assert target == tmp_path / expected
    target, handle = files.create_new_file(tmp_path, "ohne")
    handle.close()
    other, other_handle = files.create_new_file(tmp_path, "ohne")
    other_handle.close()
    assert (target.name, other.name) == ("ohne", "ohne-2")


def test_numbered_names_run_on() -> None:
    names = files.numbered_names("a.tar.gz")
    assert [next(names) for _ in range(3)] == ["a.tar.gz", "a.tar-2.gz", "a.tar-3.gz"]


def test_paths_are_moved_into_a_folder_and_a_taken_name_gets_a_number(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "a.txt").write_text("alt")
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.txt").write_text("neu")
    (source / "sub").mkdir()
    (source / "sub" / "b.txt").write_text("b")
    landed = files.transfer_into([source / "a.txt", source / "sub"], target, copy=False)
    assert landed == [target / "a-2.txt", target / "sub"]
    assert (target / "a.txt").read_text() == "alt"
    assert (target / "a-2.txt").read_text() == "neu"
    assert (target / "sub" / "b.txt").read_text() == "b"
    assert not (source / "a.txt").exists() and not (source / "sub").exists()


def test_a_copy_leaves_the_original_and_takes_a_folder_along(tmp_path: Path) -> None:
    folder = tmp_path / "proj"
    (folder / "src").mkdir(parents=True)
    (folder / "src" / "main.py").write_text("x")
    (tmp_path / "other").mkdir()
    files.transfer_into([folder], tmp_path / "other", copy=True)
    again = files.transfer_into([folder], tmp_path / "other", copy=True)
    assert again == [tmp_path / "other" / "proj-2"]
    assert (folder / "src" / "main.py").exists()
    assert (tmp_path / "other" / "proj-2" / "src" / "main.py").read_text() == "x"


def test_a_folder_does_not_go_into_itself_and_a_path_in_place_stays(tmp_path: Path) -> None:
    folder = tmp_path / "proj"
    (folder / "inner").mkdir(parents=True)
    with pytest.raises(files.InvalidTransferError):
        files.transfer_into([folder], folder / "inner", copy=False)
    with pytest.raises(files.InvalidTransferError):
        files.transfer_into([folder], folder, copy=True)
    (folder / "a.txt").write_text("x")
    assert files.transfer_into([folder / "a.txt"], folder, copy=False) == [folder / "a.txt"]
