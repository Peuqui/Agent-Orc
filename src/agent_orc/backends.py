"""Claude Code on other backends than Anthropic's: models on a local server or in a cloud.

`agent-orc backend` replaces the one script per backend (lclaude, qclaude) that shared most of
its lines: it lists the models of a backend, tells the levels one takes, and starts Claude Code
on one. Nothing is kept between starts and nothing is switched globally: a start is a process
of its own whose environment alone says which backend it talks to, so agents on Anthropic's
service, on a local server and in a cloud run side by side.
"""

import fnmatch
import http.client
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from agent_orc.config import (
    KEY_VARIABLES,
    LEVELS,
    BackendConfig,
    BackendModelConfig,
    Config,
)
from agent_orc.gpuorc import Request, free_for_model, request_json

# What Claude Code asks for without being told (its own default).
DEFAULT_LEVEL = "high"
# The effort a profile hands over to the start (AgentProfile.env: {effort}).
EFFORT_VARIABLE = "AGENT_ORC_EFFORT"
# What a start tells the hooks of its session: which backend, where it is and which model runs.
BACKEND_VARIABLE = "AGENT_ORC_BACKEND"
BASE_URL_VARIABLE = "AGENT_ORC_BACKEND_URL"
MODEL_VARIABLE = "AGENT_ORC_BACKEND_MODEL"
# How long an address gets to answer before the next one is tried.
PROBE_SECONDS = 2
# Loading a model can take minutes (the server loads it on the first request).
CONTEXT_SECONDS = 900
LISTING_SECONDS = 30

Fetch = Callable[[str, str | None, float], Any]
# A model's note that is the last day of its free quota (the user interface words it).
FREE_UNTIL_PREFIX = "free_until="
# What a request to a server can raise: no answer, an answer that is no JSON, a broken one.
FETCH_ERRORS = (OSError, ValueError, http.client.HTTPException)


class BackendError(RuntimeError):
    """Something that keeps a backend from starting, said to the user as it is."""


@dataclass(frozen=True)
class Launch:
    """What to run: Claude Code's command line and its environment."""

    command: list[str]
    environment: dict[str, str]


def fetch_json(url: str, key: str | None, timeout: float) -> Any:
    request = urllib.request.Request(url)
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def translate_level(wanted: str, allowed: Sequence[str]) -> str:
    """The level to ask the model for: the wanted one if it takes it, otherwise the next higher
    one it takes, otherwise its highest. (A model refuses levels its template does not know.)"""
    if wanted not in LEVELS:
        raise BackendError(f"unknown level {wanted!r}; Claude Code knows {', '.join(LEVELS)}")
    if wanted in allowed:
        return wanted
    return next(
        (level for level in allowed if LEVELS.index(level) >= LEVELS.index(wanted)), allowed[-1]
    )


def entry_of(backend: BackendConfig, model: str) -> BackendModelConfig | None:
    """What the configuration knows about a model: the first entry whose name or pattern fits."""
    return next(
        (entry for pattern, entry in backend.models.items() if fnmatch.fnmatchcase(model, pattern)),
        None,
    )


def free_note(entry: BackendModelConfig) -> str:
    """The note of a model whose quota is free for a while: the last day, which the user
    interface words in its own language (the note is `free_until=<date>`); empty for one without an
    end."""
    return "" if entry.free_until is None else f"{FREE_UNTIL_PREFIX}{entry.free_until.isoformat()}"


def readable_note(note: str, today: date) -> str:
    """A note worded for the terminal: the free quota as "free until <date> (n days left)"."""
    if not note.startswith(FREE_UNTIL_PREFIX):
        return note
    until = date.fromisoformat(note.removeprefix(FREE_UNTIL_PREFIX))
    days = (until - today).days
    return f"free until {until.isoformat()} ({days} day{'' if days == 1 else 's'} left)"


def offered(listed: Sequence[str], backend: BackendConfig, today: date) -> list[str]:
    """Of the models the server lists, those the configuration names and whose quota has not
    ended (afterwards they would be billed), in alphabetical order."""
    chosen = []
    for name in sorted(listed):
        entry = entry_of(backend, name)
        if entry is not None and (entry.free_until is None or entry.free_until >= today):
            chosen.append(name)
    return chosen


def resolve_key(backend: BackendConfig) -> str:
    if backend.key is not None:
        return backend.key
    if backend.key_env is not None:
        value = os.environ.get(backend.key_env)
        if not value:
            raise BackendError(
                f"the key of {backend.label} is not in the environment variable {backend.key_env}"
            )
        return value
    assert backend.key_file is not None
    try:
        return backend.key_file.expanduser().read_text(encoding="utf-8").strip()
    except OSError as error:
        raise BackendError(
            f"the key of {backend.label} cannot be read from {backend.key_file}: {error}"
        ) from error


def reachable_base_url(backend: BackendConfig, key: str, fetch: Fetch) -> str:
    """The first address of the backend that lists its models."""
    for base_url in backend.base_urls:
        try:
            fetch(base_url + backend.models_path, key, PROBE_SECONDS)
        except FETCH_ERRORS:
            continue
        return base_url
    raise BackendError(f"{backend.label} does not answer at {', '.join(backend.base_urls)}")


def listed_models(backend: BackendConfig, base_url: str, key: str, fetch: Fetch) -> list[str]:
    try:
        listing = fetch(base_url + backend.models_path, key, LISTING_SECONDS)
        return [entry["id"] for entry in listing["data"]]
    except (*FETCH_ERRORS, KeyError, TypeError) as error:
        raise BackendError(
            f"{backend.label} lists no models at {base_url}{backend.models_path}: {error}"
        ) from error


def context_length(
    backend: BackendConfig, base_url: str, model: str, key: str, fetch: Fetch
) -> int | None:
    """The context length the server reports for the model, if it does."""
    if backend.context_path is None:
        return None
    try:
        reported = fetch(
            base_url + backend.context_path.replace("{model}", model), key, CONTEXT_SECONDS
        )
        return int(reported["data"][0]["max_model_len"])
    except (*FETCH_ERRORS, KeyError, IndexError, TypeError):
        return None


def claude_environment(
    name: str, backend: BackendConfig, base_url: str, model: str, key: str, context: int | None
) -> dict[str, str]:
    """What Claude Code needs to talk to the backend. It sends Anthropic's model names for
    background requests and aliases (sonnet, opus, subagents), which the backend does not know:
    all of them are mapped to the chosen model."""
    environment = {
        # For hooks of the session (Claude Code hands its environment on to them), e.g. one that
        # frees the graphics cards before a model is loaded.
        BACKEND_VARIABLE: name,
        BASE_URL_VARIABLE: base_url,
        MODEL_VARIABLE: model,
        "ANTHROPIC_BASE_URL": base_url + backend.anthropic_path,
        backend.key_variable: key,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": backend.background_model or model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
        "CLAUDE_CODE_SUBAGENT_MODEL": model,
    }
    if backend.api_timeout_ms is not None:
        environment["API_TIMEOUT_MS"] = str(backend.api_timeout_ms)
    if context is not None:
        environment["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(context)
    return environment


def level_arguments(entry: BackendModelConfig | None, wanted: str | None) -> list[str]:
    """Claude Code's `--effort` for the model: nothing for a model that takes no levels; for one
    that does, what was wanted (or Claude Code's default) translated to a level it takes."""
    if entry is None or not entry.levels:
        return []
    return ["--effort", translate_level(wanted or DEFAULT_LEVEL, entry.levels)]


def backend_named(config: Config, name: str) -> BackendConfig:
    backend = (config.backends or {}).get(name)
    if backend is None:
        known = ", ".join(config.backends or {}) or "none configured"
        raise BackendError(f"no backend {name!r} in the configuration (known: {known})")
    return backend


def models_lines(backend: BackendConfig, today: date, fetch: Fetch = fetch_json) -> list[str]:
    """The models to choose from, one line each; after a tab a note (until when it is free)."""
    key = resolve_key(backend)
    base_url = reachable_base_url(backend, key, fetch)
    lines = []
    for name in offered(listed_models(backend, base_url, key, fetch), backend, today):
        note = free_note(entry_of(backend, name) or BackendModelConfig())
        lines.append(f"{name}\t{note}" if note else name)
    return lines


def levels_of(backend: BackendConfig, model: str) -> list[str]:
    """The levels a model takes (none: Claude Code's own default holds, no slider)."""
    entry = entry_of(backend, model)
    return list(entry.levels) if entry is not None and entry.levels else []


def prepare_launch(
    name: str,
    backend: BackendConfig,
    model: str,
    wanted_level: str | None,
    claude_arguments: Sequence[str],
    today: date,
    fetch: Fetch = fetch_json,
    gpu_orc_request: Request = request_json,
) -> Launch:
    """Everything for starting Claude Code on the backend with the model."""
    key = resolve_key(backend)
    base_url = reachable_base_url(backend, key, fetch)
    if model not in offered(listed_models(backend, base_url, key, fetch), backend, today):
        raise BackendError(
            f"{model!r} is not on offer at {backend.label} (see `agent-orc backend models`)"
        )
    if backend.gpu_orc is not None:
        for line in free_for_model(backend.gpu_orc, base_url, model, gpu_orc_request):
            print(f"GPU-Orc: {line}", file=sys.stderr)
    context = context_length(backend, base_url, model, key, fetch)
    arguments = [
        "claude",
        "--model",
        model,
        *claude_arguments,
        *level_arguments(entry_of(backend, model), wanted_level),
    ]
    # The keys of other services stay behind: Claude Code sends every key it finds to the backend.
    inherited = {
        variable: value for variable, value in os.environ.items() if variable not in KEY_VARIABLES
    }
    return Launch(
        arguments,
        {**inherited, **claude_environment(name, backend, base_url, model, key, context)},
    )


def free_cards_message(
    config: Config, environment: Mapping[str, str], request: Request = request_json
) -> str | None:
    """At an input of an agent on a backend with GPU-Orc: free the cards for its model, which the
    server may have unloaded after its idle time. What to tell the user, if anything."""
    name = environment.get(BACKEND_VARIABLE)
    if name is None:
        return None
    gpu_orc = backend_named(config, name).gpu_orc
    if gpu_orc is None:
        return None
    base_url, model = environment[BASE_URL_VARIABLE], environment[MODEL_VARIABLE]
    lines = free_for_model(gpu_orc, base_url, model, request)
    return "\n".join(f"GPU-Orc: {line}" for line in lines) or None


def split_effort(
    arguments: Sequence[str], from_environment: str | None
) -> tuple[str | None, list[str]]:
    """The wanted level (`--effort`, or what the profile handed over) and the other arguments,
    which go on to Claude Code unchanged."""
    wanted = from_environment or None
    rest: list[str] = []
    remaining = list(arguments)
    while remaining:
        argument = remaining.pop(0)
        if argument == "--effort" and remaining:
            wanted = remaining.pop(0)
        elif argument.startswith("--effort="):
            wanted = argument.removeprefix("--effort=")
        else:
            rest.append(argument)
    return wanted, rest


def choose_model(models: list[str], today: date, ask: Callable[[str], str] = input) -> str:
    """The model by number or name, asked for on the terminal."""
    if not models:
        raise BackendError("the backend offers no model to choose")
    for number, line in enumerate(models, start=1):
        name, _, note = line.partition("\t")
        shown = f"{name}  {readable_note(note, today)}" if note else name
        print(f"  {number:2d}) {shown}", file=sys.stderr)
    answer = ask(f"Model [1-{len(models)}]: ").strip()
    names = [line.split("\t")[0] for line in models]
    if answer.isdigit() and 1 <= int(answer) <= len(names):
        return names[int(answer) - 1]
    if answer in names:
        return answer
    raise BackendError("no such model")


def exec_claude(launch: Launch) -> None:
    try:
        os.execvpe(launch.command[0], launch.command, launch.environment)
    except OSError as error:
        raise BackendError(f"Claude Code cannot be started: {error}") from error
