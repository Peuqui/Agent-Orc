"""Freeing the graphics cards for a backend's model through GPU-Orc (github.com/Peuqui/GPU-Orc).

GPU-Orc runs on the machine of the model server and knows what holds its cards (speech services,
the server's persistent helper models) and how each lets go. Before a model loads, it is asked to
free the cards of that model: when Claude Code starts on the backend, and as a hook at every input,
as a server that unloaded the model after its idle time loads it again with the next request. A
model that runs already costs one quick answer.

What GPU-Orc did is told; what went wrong is told loudly, and the start or the input goes on (the
model may then fail to load at a card still held). There is no other way to free the cards.
"""

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_orc.config import GpuOrcConfig

# GPU-Orc answers its health at once; the time a request to free may take comes from there.
HEALTH_SECONDS = 5
# The outcomes that leave the cards as wanted; any other one is a problem to tell.
FINE_OUTCOMES = frozenset({"released", "released_forced", "kept"})

# url, body (None: GET), token, timeout → the answer's JSON
Request = Callable[[str, dict[str, Any] | None, str | None, float], Any]


def request_json(url: str, body: dict[str, Any] | None, token: str | None, timeout: float) -> Any:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method="GET" if body is None else "POST")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def gpu_orc_url(base_url: str, port: int) -> str:
    """GPU-Orc runs beside the model server: the backend's address with GPU-Orc's port."""
    parts = urllib.parse.urlsplit(base_url)
    return f"{parts.scheme}://{parts.hostname}:{port}"


def reason() -> str:
    """What GPU-Orc writes into its log: who asks (the agent's folder)."""
    return f"Agent-Orc: agent in {Path.cwd().name}"


def free_for_model(
    gpu_orc: GpuOrcConfig, base_url: str, model: str, request: Request = request_json
) -> list[str]:
    """Ask GPU-Orc to free the cards for the model; the lines to tell, problems marked as such."""
    url = gpu_orc_url(base_url, gpu_orc.port)
    body: dict[str, Any] = {"model": model, "reason": reason()}
    if gpu_orc.model_server is not None:
        body["model_server"] = gpu_orc.model_server
    try:
        token = gpu_orc.token_file.expanduser().read_text().strip() if gpu_orc.token_file else None
        health = request(f"{url}/health", None, token, HEALTH_SECONDS)
        answer = request(f"{url}/free", body, token, health["caller_timeout_s"])
    except urllib.error.HTTPError as error:
        refusal = error.read().decode(errors="replace").strip()
        return [f"problem: GPU-Orc at {url} refused to free the cards ({error.code}): {refusal}"]
    except (OSError, ValueError, http.client.HTTPException, KeyError, TypeError) as error:
        return [f"problem: GPU-Orc at {url} did not free the cards for {model}: {error}"]
    return report(answer, model)


def report(answer: dict[str, Any], model: str) -> list[str]:
    if answer["already_running"]:
        return []
    lines = []
    for action in answer["actions"]:
        text = f"{action['consumer']} {action['item']}: {action['outcome']}"
        if action.get("detail"):
            text += f" ({action['detail']})"
        lines.append(text if action["outcome"] in FINE_OUTCOMES else f"problem: {text}")
    if not answer["free"]:
        lines.append(f"problem: the cards for {model} are not free, it may fail to load")
    return lines
