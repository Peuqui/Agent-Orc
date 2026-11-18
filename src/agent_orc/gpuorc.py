"""Freeing the graphics cards for a backend's model through GPU-Orc (github.com/Peuqui/GPU-Orc).

GPU-Orc runs on the machine of the model server and knows what holds its cards (speech services,
the server's persistent helper models) and how each lets go. Before a model loads, it is asked to
free the cards of that model: when Claude Code starts on the backend, and as a hook at every input,
as a server that unloaded the model after its idle time loads it again with the next request. A
model that runs already costs one quick answer.

What GPU-Orc did is told; what went wrong is told loudly, and the start or the input goes on (the
model may then fail to load at a card still held). There is no other way to free the cards.

The protocol itself is gpu_orc_client.py, a copy of GPU-Orc's shared client (GPU-Orc-client repo,
scripts/sync_clients.py; never edited here). This file is what Agent-Orc decides: where GPU-Orc is,
the token, the reason, and the words of the report.
"""

import urllib.parse
from pathlib import Path

from agent_orc.config import GpuOrcConfig
from agent_orc.gpu_orc_client import FINE_OUTCOMES, FreeResult, GpuOrc, GpuOrcError


def gpu_orc_url(base_url: str, port: int) -> str:
    """GPU-Orc runs beside the model server: the backend's address with GPU-Orc's port."""
    parts = urllib.parse.urlsplit(base_url)
    return f"{parts.scheme}://{parts.hostname}:{port}"


def gpu_orc_token(gpu_orc: GpuOrcConfig) -> str | None:
    return gpu_orc.token_file.expanduser().read_text().strip() if gpu_orc.token_file else None


def client(gpu_orc: GpuOrcConfig, base_url: str) -> GpuOrc:
    """Raises OSError when the token file cannot be read."""
    return GpuOrc(gpu_orc_url(base_url, gpu_orc.port), gpu_orc_token(gpu_orc))


def held(gpu_orc: GpuOrcConfig, base_url: str) -> dict[str, str] | None:
    """GPU-Orc's hold of the cards ({"since", "reason"}), None when there is none. Raises
    GpuOrcError (or OSError for the token file) when GPU-Orc cannot be asked (the caller decides
    what that means; see card_gate.hold_of for the gate's way)."""
    return client(gpu_orc, base_url).loading().held


def reason() -> str:
    """What GPU-Orc writes into its log: who asks (the agent's folder)."""
    return f"Agent-Orc: agent in {Path.cwd().name}"


def free_for_model(gpu_orc: GpuOrcConfig, base_url: str, model: str) -> list[str]:
    """Ask GPU-Orc to free the cards for the model; the lines to tell, problems marked as such."""
    try:
        orc = client(gpu_orc, base_url)
        result = orc.free_for_model(model, reason(), model_server=gpu_orc.model_server)
    except (GpuOrcError, OSError) as error:
        url = gpu_orc_url(base_url, gpu_orc.port)
        return [f"problem: GPU-Orc at {url} did not free the cards for {model}: {error}"]
    return report(result, model)


def report(result: FreeResult, model: str) -> list[str]:
    if result.already_running:
        return []
    lines = []
    for action in result.actions:
        text = f"{action.consumer} {action.item}: {action.outcome}"
        if action.detail:
            text += f" ({action.detail})"
        lines.append(text if action.outcome in FINE_OUTCOMES else f"problem: {text}")
    if not result.free:
        lines.append(f"problem: the cards for {model} are not free, it may fail to load")
    return lines
