from pathlib import Path

import pytest

from agent_orc.scope import AccessScope, InvalidBaseDirError, OutsideScopeError
from tests.conftest import FakeClock


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "projects" / "demo").mkdir(parents=True)
    (tmp_path / "private").mkdir()
    return tmp_path


@pytest.fixture
def scope(home: Path, clock: FakeClock) -> AccessScope:
    return AccessScope(home / "projects", home, unlock_seconds=600, clock=clock)


def test_paths_inside_base_are_allowed(scope: AccessScope, home: Path) -> None:
    assert scope.resolve(str(home / "projects" / "demo")) == home / "projects" / "demo"
    assert scope.resolve(str(home / "projects" / "new-file")) == home / "projects" / "new-file"


@pytest.mark.parametrize(
    "relative", ["private", "projects/../private", "projects/demo/../../private"]
)
def test_paths_outside_base_are_rejected(scope: AccessScope, home: Path, relative: str) -> None:
    with pytest.raises(OutsideScopeError):
        scope.resolve(str(home / relative))


def test_relative_paths_are_rejected(scope: AccessScope) -> None:
    with pytest.raises(OutsideScopeError):
        scope.resolve("projects/demo")


def test_symlink_escape_is_rejected(scope: AccessScope, home: Path) -> None:
    (home / "projects" / "escape").symlink_to(home / "private")
    with pytest.raises(OutsideScopeError):
        scope.resolve(str(home / "projects" / "escape"))


def test_unlock_widens_to_home_until_it_expires(
    scope: AccessScope, home: Path, clock: FakeClock
) -> None:
    scope.unlock()
    assert scope.resolve(str(home / "private")) == home / "private"
    clock.advance(601)
    assert scope.root == home / "projects"
    with pytest.raises(OutsideScopeError):
        scope.resolve(str(home / "private"))


def test_lock_ends_unlock_early(scope: AccessScope, home: Path) -> None:
    scope.unlock()
    scope.lock()
    with pytest.raises(OutsideScopeError):
        scope.resolve(str(home / "private"))


def test_home_is_the_limit_even_when_unlocked(scope: AccessScope) -> None:
    scope.unlock()
    with pytest.raises(OutsideScopeError):
        scope.resolve("/etc")


def test_the_base_directory_can_move_inside_the_home_directory(
    scope: AccessScope, home: Path
) -> None:
    scope.change_base_dir(home / "private")
    assert scope.root == home / "private"
    assert scope.resolve(str(home / "private")) == home / "private"
    with pytest.raises(OutsideScopeError):
        scope.resolve(str(home / "projects"))


def test_the_base_directory_is_a_folder_in_the_home_directory(
    scope: AccessScope, home: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    (home / "afile").write_text("x")
    for wrong in (home / "afile", home / "missing", tmp_path_factory.mktemp("elsewhere")):
        with pytest.raises(InvalidBaseDirError):
            scope.change_base_dir(wrong)
    assert scope.base_dir == home / "projects"
