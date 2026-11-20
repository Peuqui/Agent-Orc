"""The holds of GPU-Orc as the page shows them, and the person's hand-over of the cards.

A hold is somebody keeping the graphics cards of a machine (a measurement, a training). GPU-Orc
makes a requested hold effective by itself once no main model is loaded; while one is, only a
person's grant lets it go on (GPU-Orc's POST /hold/grant). The page asks for the holds of every
GPU-Orc the backends name and sends the grant back here; the protocol is gpu_orc_client.py.
"""

from dataclasses import dataclass
from typing import Any

from agent_orc.backends import BackendError, Fetch, backend_named, reachable_base_url, resolve_key
from agent_orc.config import BackendConfig, Config
from agent_orc.gpu_orc_client import GpuOrc, GpuOrcError, Hold
from agent_orc.gpuorc import client, gpu_orc_url

# What keeps one backend from being asked: its server does not answer, GPU-Orc does not, or the
# token file cannot be read.
ASKING_ERRORS = (BackendError, GpuOrcError, OSError)


@dataclass(frozen=True)
class GpuOrcHolds:
    """The hold (requested or active) of one GPU-Orc, or why it could not be asked."""

    backend: str  # the first backend that names this GPU-Orc
    label: str
    url: str | None  # None when the backend's address is not known (its server does not answer)
    hold: Hold | None
    error: str | None

    def as_json(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "label": self.label,
            "url": self.url,
            "hold": None if self.hold is None else hold_json(self.hold),
            "error": self.error,
        }


def hold_json(hold: Hold) -> dict[str, Any]:
    return {
        "owner": hold.owner,
        "reason": hold.reason,
        "model": hold.model,
        "state": hold.state,
        "granted_by": hold.granted_by,
        "since": hold.since,
    }


def gpu_orc_of(backend: BackendConfig, fetch: Fetch) -> tuple[GpuOrc, str]:
    """The client of the backend's GPU-Orc, and its address. Raises ASKING_ERRORS."""
    assert backend.gpu_orc is not None
    base_url = reachable_base_url(backend, resolve_key(backend), fetch)
    return client(backend.gpu_orc, base_url), gpu_orc_url(base_url, backend.gpu_orc.port)


def holds_of_backends(config: Config, fetch: Fetch) -> list[GpuOrcHolds]:
    """One entry per GPU-Orc the backends name (backends on the same one count once); a GPU-Orc
    that cannot be asked is an entry with its error, never left out."""
    entries: list[GpuOrcHolds] = []
    seen: set[str] = set()
    for name, backend in (config.backends or {}).items():
        if backend.gpu_orc is None:
            continue
        try:
            orc, url = gpu_orc_of(backend, fetch)
            if url in seen:
                continue
            seen.add(url)
            light = orc.loading()
        except ASKING_ERRORS as error:
            entries.append(GpuOrcHolds(name, backend.label, None, None, str(error)))
            continue
        hold = light.held or light.hold_requested
        entries.append(GpuOrcHolds(name, backend.label, url, hold, None))
    return entries


def grant_hold(config: Config, backend_name: str, owner: str, fetch: Fetch) -> Hold:
    """The person grants the requested hold of `owner` at the GPU-Orc of the backend. Raises
    BackendError (the backend names no GPU-Orc or its server does not answer) or GpuOrcError (no
    hold, a hold of another owner, GPU-Orc not reachable, token file unreadable)."""
    backend = backend_named(config, backend_name)
    if backend.gpu_orc is None:
        raise BackendError(f"{backend.label} names no GPU-Orc (gpu_orc)")
    try:
        orc, _ = gpu_orc_of(backend, fetch)
    except OSError as error:
        raise GpuOrcError(f"GPU-Orc token of {backend.label} unreadable: {error}") from error
    return orc.grant_hold(owner, config.gpu_orc_grant_by)
