import subprocess
from pathlib import Path

import pytest

from agent_orc.changes import NotAGitRepositoryError
from agent_orc.worktrees import (
    InvalidBranchError,
    WorktreeError,
    create_worktree,
    is_worktree,
    remove_worktree,
)


def git(folder: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(folder), "-c", "user.name=T", "-c", "user.email=t@e.org", *arguments],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    folder = tmp_path / "project"
    folder.mkdir()
    git(folder, "init", "-q", "-b", "main")
    (folder / "app.py").write_text("print(1)\n")
    git(folder, "add", ".")
    git(folder, "commit", "-q", "-m", "start")
    return folder


def test_worktree_lives_next_to_the_project_on_a_new_branch(project: Path) -> None:
    worktree = create_worktree(project, "fix-xy")
    assert worktree == project.parent / "project.worktrees" / "fix-xy"
    assert (worktree / "app.py").read_text() == "print(1)\n"
    assert is_worktree(worktree) and not is_worktree(project)


def test_removing_keeps_an_unmerged_branch_and_deletes_a_merged_one(project: Path) -> None:
    unmerged = create_worktree(project, "unmerged")
    (unmerged / "new.py").write_text("x\n")
    git(unmerged, "add", ".")
    git(unmerged, "commit", "-q", "-m", "work")
    assert remove_worktree(unmerged).branch_deleted is False
    assert not unmerged.exists()
    merged = create_worktree(project, "merged")
    assert remove_worktree(merged).branch_deleted is True
    # The last one takes the <project>.worktrees folder along.
    assert not (project.parent / "project.worktrees").exists()


def test_uncommitted_work_is_never_removed(project: Path) -> None:
    worktree = create_worktree(project, "busy")
    (worktree / "app.py").write_text("print(2)\n")
    with pytest.raises(WorktreeError):
        remove_worktree(worktree)
    assert (worktree / "app.py").read_text() == "print(2)\n"


def test_agent_orcs_own_files_do_not_block_but_any_other_file_does(project: Path) -> None:
    (project / ".gitignore").write_text(".claude/\n.env\n")
    git(project, "add", ".")
    git(project, "commit", "-q", "-m", "ignore")
    worktree = create_worktree(project, "settings")
    (worktree / ".claude").mkdir()
    (worktree / ".claude" / "settings.local.json").write_text("{}")
    (worktree / ".env").write_text("SECRET=1\n")
    with pytest.raises(WorktreeError, match=".env"):
        remove_worktree(worktree)
    (worktree / ".env").unlink()
    assert remove_worktree(worktree).branch_deleted is True
    assert not worktree.exists()


def test_bad_branch_names_and_folders_without_git(project: Path, tmp_path: Path) -> None:
    with pytest.raises(InvalidBranchError):
        create_worktree(project, "no spaces")
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(NotAGitRepositoryError):
        create_worktree(plain, "x")
