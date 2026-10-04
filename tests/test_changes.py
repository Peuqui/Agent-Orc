import subprocess
from pathlib import Path

import pytest

from agent_orc.changes import (
    BINARY_NOTE,
    ChangeNotFoundError,
    FileChange,
    NotAGitRepositoryError,
    file_changes,
    file_diff,
)


def git(folder: Path, *arguments: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(folder),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=t@example.org",
            *arguments,
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    folder = tmp_path / "project"
    folder.mkdir()
    git(folder, "init", "-q")
    (folder / "app.py").write_text("print('hello')\n")
    (folder / "old name.txt").write_text("moved\n")
    (folder / "gone.txt").write_text("bye\n")
    git(folder, "add", ".")
    git(folder, "commit", "-q", "-m", "start")
    return folder


def test_changes_cover_modified_new_deleted_and_renamed(repository: Path) -> None:
    (repository / "app.py").write_text("print('hello, world')\n")
    (repository / "notes" / "new.md").parent.mkdir()
    (repository / "notes" / "new.md").write_text("# New\n")
    (repository / "gone.txt").unlink()
    git(repository, "mv", "old name.txt", "new name.txt")
    assert sorted(file_changes(repository), key=lambda change: change.path) == [
        FileChange("app.py", "M"),
        FileChange("gone.txt", "D"),
        FileChange("new name.txt", "R"),
        FileChange("notes/new.md", "??"),
    ]


def test_diff_of_a_changed_file_against_the_last_commit(repository: Path) -> None:
    (repository / "app.py").write_text("print('hello, world')\n")
    diff = file_diff(repository, "app.py")
    assert "-print('hello')" in diff.text
    assert "+print('hello, world')" in diff.text
    assert diff.truncated is False


def test_new_files_show_as_added_lines_binary_ones_as_a_note(repository: Path) -> None:
    (repository / "Grüße.txt").write_text("one\ntwo\n")
    (repository / "image.png").write_bytes(b"\x89PNG\0\0data")
    # Unquoted path with umlauts, as the user sees it.
    assert file_diff(repository, "Grüße.txt").text == "+one\n+two\n"
    assert file_diff(repository, "image.png").text == BINARY_NOTE


def test_only_changed_files_can_be_read(repository: Path) -> None:
    with pytest.raises(ChangeNotFoundError):
        file_diff(repository, "app.py")
    with pytest.raises(ChangeNotFoundError):
        file_diff(repository, "../../etc/passwd")


def test_folder_without_git(tmp_path: Path) -> None:
    with pytest.raises(NotAGitRepositoryError):
        file_changes(tmp_path)
