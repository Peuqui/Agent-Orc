from pathlib import Path

from agent_orc.attachments import store_attachment
from tests.conftest import FakeClock


def test_stores_in_the_project_and_keeps_it_out_of_git(tmp_path: Path, clock: FakeClock) -> None:
    relative = store_attachment(tmp_path, "Bildschirmfoto 1.png", b"png", clock)
    assert relative.parts[:2] == (".agent-orc", "uploads")
    assert relative.name.endswith("-Bildschirmfoto-1.png")
    assert (tmp_path / relative).read_bytes() == b"png"
    assert (tmp_path / ".agent-orc" / ".gitignore").read_text() == "*\n"


def test_same_second_same_name_keeps_both(tmp_path: Path, clock: FakeClock) -> None:
    first = store_attachment(tmp_path, "a.jpg", b"1", clock)
    second = store_attachment(tmp_path, "a.jpg", b"2", clock)
    assert first != second
    assert (tmp_path / first).read_bytes() == b"1"
    assert (tmp_path / second).read_bytes() == b"2"


def test_name_cannot_leave_the_uploads(tmp_path: Path, clock: FakeClock) -> None:
    relative = store_attachment(tmp_path, "../../etc/passwd", b"x", clock)
    assert relative.parent == Path(".agent-orc/uploads")
    assert not (tmp_path.parent / "etc").exists()
