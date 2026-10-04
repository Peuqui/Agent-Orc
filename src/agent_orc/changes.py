"""What an agent changed in its project: the git working tree against the last commit.

Read-only: the agent stages and commits itself. GIT_OPTIONAL_LOCKS=0 keeps git from taking the
index lock for its status refresh, so looking never gets in the way of an agent at work.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

# A diff larger than this is cut; the page shows that it was.
MAX_DIFF_CHARS = 200_000
# Untracked files are shown whole as added lines, up to this size.
MAX_NEW_FILE_BYTES = 200_000
# LC_ALL=C: git's messages in English whatever the user's language, as they are read here.
GIT_ENVIRONMENT = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}


class NotAGitRepositoryError(ValueError):
    pass


class ChangeNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class FileChange:
    path: str
    # As `git status --porcelain` puts it, e.g. "M", "A", "D", "R", "??" for untracked.
    status: str


@dataclass(frozen=True)
class Diff:
    text: str
    truncated: bool


def _git(folder: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(folder), "--no-pager", *arguments],
        capture_output=True,
        text=True,
        env=GIT_ENVIRONMENT,
    )
    if result.returncode != 0:
        if "not a git repository" in result.stderr:
            raise NotAGitRepositoryError(str(folder))
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def file_changes(folder: Path) -> list[FileChange]:
    """Changed, new and deleted files of the working tree, staged or not."""
    # -z: paths unquoted and NUL-separated; a rename carries its old path as the next field.
    fields = _git(folder, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
    changes = []
    index = 0
    while index < len(fields) and fields[index]:
        entry = fields[index]
        status, path = entry[:2].strip(), entry[3:]
        changes.append(FileChange(path=path, status=status))
        index += 2 if status.startswith(("R", "C")) else 1
    return changes


def _has_commits(folder: Path) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(folder), "rev-parse", "--verify", "--quiet", "HEAD"],
            capture_output=True,
            env=GIT_ENVIRONMENT,
        ).returncode
        == 0
    )


def file_diff(folder: Path, path: str) -> Diff:
    """The diff of one changed file against the last commit; new files as all lines added."""
    change = next((c for c in file_changes(folder) if c.path == path), None)
    if change is None:
        # Only files git reports as changed: no other file of the machine can be read here.
        raise ChangeNotFoundError(path)
    if change.status == "??" or not _has_commits(folder):
        text = _new_file_diff(folder / path)
    else:
        text = _git(folder, "diff", "HEAD", "--", path)
    return Diff(text=text[:MAX_DIFF_CHARS], truncated=len(text) > MAX_DIFF_CHARS)


# Shown instead of the content of a new binary file, as git does for changed ones.
BINARY_NOTE = "Binary file"


def _new_file_diff(file: Path) -> str:
    content = file.read_bytes()[:MAX_NEW_FILE_BYTES]
    if b"\0" in content:
        return BINARY_NOTE
    text = content.decode("utf-8", errors="replace")
    return "".join(f"+{line}\n" for line in text.splitlines())
