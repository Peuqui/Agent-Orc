"""What the Agent-Orc of another machine knows about the local models it serves: their names and
the reasoning levels each takes (see docs/PLAN-2026-11-14-modellkatalog.md).

Only the machine that holds a model's files can read its chat template. A backend on another
machine (`catalog_from`) takes the models and levels from that machine's catalog instead. The
Agent-Orc that controls others exchanges the catalogs over its tunnels both ways: it sends its own
to each machine and fetches each machine's, so the catalog reaches the machine that needs it
whichever of the two controls the other. Each is kept here under the name of the machine it is
from, which is that machine's host name.
"""

import json
import socket
import time

from pydantic import BaseModel, ConfigDict, ValidationError

from agent_orc.config import HOST_NAME_PATTERN, Level
from agent_orc.state import state_dir, write_atomically

CATALOGS_FOLDER = "catalogs"


class CatalogModel(BaseModel):
    """A model on offer: the levels it takes, or why they cannot be told."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    levels: list[Level] = []
    problem: str | None = None


class CatalogBackend(BaseModel):
    """A backend the machine reads itself: its models, or why they cannot be listed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    models: list[CatalogModel] = []
    problem: str | None = None


class StoredCatalog(BaseModel):
    """Another machine's catalog as kept here, with when it arrived (seconds since the epoch)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    received: float
    backends: dict[str, CatalogBackend]


class CatalogError(RuntimeError):
    """No catalog of the machine is here (yet), said as it is."""


class UnknownMachineError(ValueError):
    """Not a name a machine can have here (letters, digits, - and _ only)."""


def machine_name() -> str:
    """The name this machine's catalog has on the others: its host name."""
    return socket.gethostname()


def catalog_file(machine: str) -> str:
    if not HOST_NAME_PATTERN.fullmatch(machine):
        raise UnknownMachineError(machine)
    return f"{machine}.json"


def store_catalog(machine: str, backends: dict[str, CatalogBackend]) -> None:
    stored = StoredCatalog(received=time.time(), backends=backends)
    target = state_dir() / CATALOGS_FOLDER / catalog_file(machine)
    write_atomically(target, stored.model_dump_json())


def read_catalog(machine: str) -> StoredCatalog:
    path = state_dir() / CATALOGS_FOLDER / catalog_file(machine)
    try:
        return StoredCatalog.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError as error:
        raise CatalogError(
            f"no catalog from {machine} here yet: its Agent-Orc and this one have not reached"
            " each other since"
        ) from error
    except (OSError, ValueError, ValidationError) as error:
        raise CatalogError(f"the catalog from {machine} cannot be read: {error}") from error
