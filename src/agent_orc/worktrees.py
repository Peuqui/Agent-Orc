"""Git worktrees: a second working copy of a repository on a branch of its own, so two agents can
work on one project without overwriting each other's files.

Worktrees live next to the project, in <project>.worktrees/<branch>; inside the project, git
would see them as a subfolder. Removing one never loses work: git refuses to remove a worktree
with uncommitted changes, and the branch is deleted only once it is merged.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from agent_orc.changes import GIT_ENVIRONMENT, NotAGitRepositoryError

WORKTREES_SUFFIX = ".worktrees"
# Where the repository keeps a linked worktree's administrative files (.git/worktrees/<name>).
WORKTREES_DIR = "/worktrees"
# Files that land in an agent's folder without being its work (Claude's own project settings,
# Agent-Orc's attachments), so they do not keep a worktree from being removed. Git counts them as
# untracked even when they are ignored.
OWN_FILES = (".claude/", ".claude/settings.local.json", ".agent-orc/")


class InvalidBranchError(ValueError):
    pass


class WorktreeError(RuntimeError):
    """git refused, e.g. a worktree with uncommitted changes; its message says why."""


@dataclass(frozen=True)
class Removal:
    # The branch is kept while it is not merged yet.
    branch_deleted: bool
    branch: str


def _git(folder: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(folder), *arguments],
        capture_output=True,
        text=True,
        env=GIT_ENVIRONMENT,
    )


def _top_level(folder: Path) -> Path:
    result = _git(folder, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise NotAGitRepositoryError(str(folder))
    return Path(result.stdout.strip())


def worktree_path(folder: Path, branch: str) -> Path:
    """Where the worktree for the branch goes, so the caller can check it before it exists."""
    if _git(folder, "check-ref-format", "--branch", branch).returncode != 0:
        raise InvalidBranchError(branch)
    project = _top_level(folder)
    return project.parent / f"{project.name}{WORKTREES_SUFFIX}" / branch


def create_worktree(folder: Path, branch: str) -> Path:
    """A new worktree of the folder's repository on a new branch from its current state."""
    target = worktree_path(folder, branch)
    result = _git(_top_level(folder), "worktree", "add", "-b", branch, str(target))
    if result.returncode != 0:
        raise WorktreeError(result.stderr.strip())
    return target


def is_worktree(folder: Path) -> bool:
    """A linked worktree: its .git is a file pointing into the repository's worktrees/ (asked
    for every agent on every refresh, so without starting git)."""
    marker = folder / ".git"
    if not marker.is_file():
        return False
    return f"{WORKTREES_DIR}/" in marker.read_text(encoding="utf-8")


def remove_worktree(folder: Path) -> Removal:
    """Remove the worktree; delete its branch only if it is merged."""
    if not is_worktree(folder):
        raise WorktreeError(f"{folder} is not a worktree")
    branch = _git(folder, "branch", "--show-current").stdout.strip()
    common_dir = Path(
        _git(folder, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    )
    main = common_dir.parent
    status = _git(folder, "status", "--porcelain=v1", "-z", "--ignored", "--untracked-files=normal")
    leftovers = [entry[3:] for entry in status.stdout.split("\0") if entry]
    others = [path for path in leftovers if path not in OWN_FILES]
    if others:
        # Changes, new files or ignored ones like a .env: never removed without the user.
        raise WorktreeError(f"{folder} still holds: {', '.join(others)}")
    # Only Agent-Orc's own files are left, which git would refuse without --force.
    removed = _git(main, "worktree", "remove", "--force", str(folder))
    if removed.returncode != 0:
        raise WorktreeError(removed.stderr.strip())
    # The <project>.worktrees folder goes with its last worktree.
    if folder.parent.name.endswith(WORKTREES_SUFFIX) and not any(folder.parent.iterdir()):
        folder.parent.rmdir()
    # -d (not -D): git keeps a branch that is not merged.
    deleted = _git(main, "branch", "-d", branch).returncode == 0
    return Removal(branch_deleted=deleted, branch=branch)
