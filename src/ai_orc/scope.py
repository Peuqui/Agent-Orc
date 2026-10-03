"""Which part of the file system the web UI may touch, including the safety switch."""

from pathlib import Path

from ai_orc.auth import Clock


class OutsideScopeError(PermissionError):
    pass


class AccessScope:
    """Paths are confined to the base directory; the safety switch widens this to the
    home directory for a limited time."""

    def __init__(self, base_dir: Path, home: Path, unlock_seconds: float, clock: Clock) -> None:
        self.base_dir = base_dir.resolve()
        self.home = home.resolve()
        self._unlock_seconds = unlock_seconds
        self._clock = clock
        self._unlocked_until = 0.0

    def unlock(self) -> None:
        self._unlocked_until = self._clock() + self._unlock_seconds

    def lock(self) -> None:
        self._unlocked_until = 0.0

    def seconds_unlocked(self) -> float:
        return max(0.0, self._unlocked_until - self._clock())

    @property
    def root(self) -> Path:
        return self.home if self.seconds_unlocked() > 0 else self.base_dir

    def resolve(self, raw_path: str) -> Path:
        """Resolve an absolute path (following symlinks) and ensure it lies in scope."""
        path = Path(raw_path)
        if not path.is_absolute():
            raise OutsideScopeError(f"path must be absolute: {raw_path}")
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise OutsideScopeError(str(resolved))
        return resolved
