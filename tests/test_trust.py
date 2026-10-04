import json
import stat
from pathlib import Path

from agent_orc.trust import CLAUDE_STATE, trust_claude_folder


def write_state(home: Path, state: dict[str, object]) -> Path:
    path = home / CLAUDE_STATE
    path.write_text(json.dumps(state))
    path.chmod(0o600)
    return path


def test_marks_folder_trusted_and_keeps_everything_else(tmp_path: Path) -> None:
    other = {"hasTrustDialogAccepted": True, "allowedTools": ["Bash"]}
    path = write_state(tmp_path, {"numStartups": 140, "projects": {"/a": other}})
    trust_claude_folder(tmp_path, Path("/b/new"))
    state = json.loads(path.read_text())
    assert state["numStartups"] == 140
    assert state["projects"]["/a"] == other
    assert state["projects"]["/b/new"] == {"hasTrustDialogAccepted": True}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(tmp_path.glob("*.agent-orc-tmp"))


def test_existing_project_entry_is_extended(tmp_path: Path) -> None:
    path = write_state(tmp_path, {"projects": {"/b": {"lastCost": 1.5}}})
    trust_claude_folder(tmp_path, Path("/b"))
    assert json.loads(path.read_text())["projects"]["/b"] == {
        "lastCost": 1.5,
        "hasTrustDialogAccepted": True,
    }


def test_already_trusted_folder_leaves_file_untouched(tmp_path: Path) -> None:
    path = write_state(tmp_path, {"projects": {"/b": {"hasTrustDialogAccepted": True}}})
    before = path.stat().st_mtime_ns, path.read_text()
    trust_claude_folder(tmp_path, Path("/b"))
    assert (path.stat().st_mtime_ns, path.read_text()) == before


def test_state_without_projects(tmp_path: Path) -> None:
    path = write_state(tmp_path, {"numStartups": 1})
    trust_claude_folder(tmp_path, Path("/b"))
    assert json.loads(path.read_text())["projects"] == {"/b": {"hasTrustDialogAccepted": True}}
