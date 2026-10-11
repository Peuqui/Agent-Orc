"""Reading answers aloud with a TTS-Suite service: it chooses the engine, cuts and cleans the text
and answers with frames of audio (see its docs/INTERFACE.md). Agent-Orc hands the browser those
frames unchanged: the browser cannot reach the service itself (it may be on the server's loopback),
and the token stays on the server.
"""

import contextlib
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from http.client import HTTPResponse
from pathlib import Path
from typing import Any

from agent_orc.config import TtsSuiteConfig

FRAMES_MEDIA_TYPE = "application/x-tts-frames"
CHUNK_BYTES = 16384


class SpeechServiceError(RuntimeError):
    """The service cannot be reached or refused; the message is what it said."""


class NothingSwitchedOnError(ValueError):
    """Every engine is switched off in the settings, so there is nothing to speak with."""


def _request(
    config: TtsSuiteConfig, directory: Path, path: str, body: dict[str, Any] | None
) -> urllib.request.Request:
    headers = {"Content-Type": "application/json"}
    if config.token_file is not None:
        token = (directory / config.token_file).read_text(encoding="utf-8").strip()
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(
        f"{config.url.rstrip('/')}{path}",
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
    )


def _open(config: TtsSuiteConfig, request: urllib.request.Request) -> HTTPResponse:
    try:
        response: HTTPResponse = urllib.request.urlopen(request, timeout=config.timeout_seconds)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        # The service answers `{"error", "detail"}`; anything else is passed on as it came.
        with contextlib.suppress(ValueError, KeyError, TypeError):
            detail = json.loads(detail)["detail"]
        raise SpeechServiceError(f"{error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise SpeechServiceError(str(error)) from error
    return response


def engines(config: TtsSuiteConfig, directory: Path) -> list[dict[str, Any]]:
    """The engines the service offers, one per key in the order the service tries them (an engine
    on several machines is one): `engine`, `label` (per language), `cloud`, `needs_gpu`. The
    browser's voice is the client's own and not offered."""
    with _open(config, _request(config, directory, "/engines", None)) as response:
        listed: list[dict[str, Any]] = json.load(response)
    offered: dict[str, dict[str, Any]] = {}
    for entry in listed:
        if entry["browser"] or entry["engine"] in offered:
            continue
        offered[entry["engine"]] = {
            key: entry[key] for key in ("engine", "label", "cloud", "needs_gpu")
        }
    return list(offered.values())


def merged_choices(
    stored: list[dict[str, Any]], offered: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """What the user chose, with what the service offers now: an engine the service no longer has
    is dropped, one it newly has joins at the end (switched on, its own voice)."""
    keys = [engine["engine"] for engine in offered]
    kept = [choice for choice in stored if choice["engine"] in keys]
    known = {choice["engine"] for choice in kept}
    return kept + [
        {"engine": key, "enabled": True, "voice": ""} for key in keys if key not in known
    ]


def voices(config: TtsSuiteConfig, directory: Path, engine: str) -> list[dict[str, str]]:
    """The voices of an engine: `id` (what a request names) and `label`."""
    request = _request(config, directory, f"/voices?engine={urllib.parse.quote(engine)}", None)
    with _open(config, request) as response:
        listed: list[dict[str, str]] = json.load(response)
    return [{"id": voice["name"], "label": voice["label"]} for voice in listed]


def speak(
    config: TtsSuiteConfig,
    directory: Path,
    text: str,
    language: str,
    speed: float | None,
    chosen: list[dict[str, Any]],
) -> Iterator[bytes]:
    """The frames of the reading, with the engines the user switched on (`chosen`: `engine`,
    `enabled`, `voice`, in the order of speaking). The service answers once the first piece exists,
    so a reading that cannot start raises here, before anything is sent on; later failures are
    frames."""
    head: dict[str, Any] = {"text": text, "language": language}
    # Without a choice the service would go through its whole list: engines that have no voice to
    # speak with, and a cloud engine that is paid for. The user chooses first.
    on = [entry for entry in chosen if entry["enabled"]]
    if not on:
        raise NothingSwitchedOnError(
            "no engine of the TTS service is switched on: choose them in the settings"
            " (Engines of the TTS service)"
        )
    head["engines"] = [entry["engine"] for entry in on]
    head["voices"] = {entry["engine"]: {"voice": entry["voice"]} for entry in on if entry["voice"]}
    if speed is not None:
        head["speed"] = speed
    response = _open(config, _request(config, directory, "/speak", head))

    def frames() -> Iterator[bytes]:
        with response:
            while chunk := response.read(CHUNK_BYTES):
                yield chunk

    return frames()
