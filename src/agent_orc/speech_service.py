"""Reading answers aloud with a TTS-Suite service: it chooses the engine, cuts and cleans the text
and answers with frames of audio (see its docs/INTERFACE.md). Agent-Orc hands the browser those
frames unchanged: the browser cannot reach the service itself (it may be on the server's loopback),
and the token stays on the server.
"""

import contextlib
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPResponse
from pathlib import Path
from typing import Any

from agent_orc.config import TtsSuiteConfig

FRAMES_MEDIA_TYPE = "application/x-tts-frames"
CHUNK_BYTES = 16384
# Not `Authorization`: a login in front of the TTS-Suite would take that header.
TOKEN_HEADER = "X-TTS-Suite-Token"


class SpeechServiceError(RuntimeError):
    """The service cannot be reached or refused; the message is what it said."""


class NothingSwitchedOnError(ValueError):
    """Every engine is switched off in the settings, so there is nothing to speak with."""


class FrameStream:
    """The frames of a reading as the service makes them. `close` ends the reading there: the
    service stops making what is not made yet. It may be called from another thread than the one
    that reads; a read in progress ends first (the service sends something at least every few
    seconds), and then the connection is closed by the thread that was reading."""

    def __init__(self, response: HTTPResponse) -> None:
        self._response = response
        self._closing = threading.Event()
        self._reading = threading.Lock()

    def read(self) -> bytes:
        """The next piece of the answer; empty at its end or once the stream is closed."""
        with self._reading:
            if self._closing.is_set():
                return b""
            chunk = self._response.read(CHUNK_BYTES)
            if not chunk or self._closing.is_set():
                self._response.close()
                return b""
            return chunk

    def close(self) -> None:
        self._closing.set()
        if self._reading.acquire(blocking=False):
            try:
                self._response.close()
            finally:
                self._reading.release()


def _request(
    config: TtsSuiteConfig, directory: Path, path: str, body: dict[str, Any] | None
) -> urllib.request.Request:
    headers = {"Content-Type": "application/json"}
    if config.token_file is not None:
        token = (directory / config.token_file).read_text(encoding="utf-8").strip()
        headers[TOKEN_HEADER] = token
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


def catalog(config: TtsSuiteConfig, directory: Path) -> list[dict[str, Any]]:
    """The service's catalog: one row per engine and machine that can speak (`engine`, `host`: null
    for the service's own machine; `label` and `label_short` per language, `unit_default`, `cloud`,
    `needs_gpu`,
    `status`, `installed`). The browser's voice is the client's own and not in it."""
    with _open(config, _request(config, directory, "/engines", None)) as response:
        listed: list[dict[str, Any]] = json.load(response)
    keys = (
        "engine", "host", "label", "label_short", "unit_default", "cloud", "needs_gpu", "status",
        "installed",
    )
    return [{key: row[key] for key in keys} for row in listed if not row["browser"]]


def merged_choices(stored: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What the user chose, with what the catalog has now: nothing is removed. An entry the catalog
    no longer has stays, marked `offered: false` (it is never sent); a row it newly has joins at
    the end, switched OFF (an engine may cost money), in the unit the engine recommends."""
    present = {(row["engine"], row["host"]) for row in rows}
    kept = [
        {**entry, "offered": (entry["engine"], entry["host"]) in present}
        for entry in stored["entries"]
    ]
    known = {(entry["engine"], entry["host"]) for entry in kept}
    joined = [
        {
            "engine": row["engine"],
            "host": row["host"],
            "unit": row["unit_default"],
            "enabled": False,
            "offered": True,
        }
        for row in rows
        if (row["engine"], row["host"]) not in known
    ]
    return {
        "entries": kept + joined,
        "voices": stored["voices"],
        "tuning": stored["tuning"],
        "paragraph_pause_ms": stored["paragraph_pause_ms"],
        "prefer_loaded": stored["prefer_loaded"],
    }


def with_loaded_first(chosen: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """With `prefer_loaded`, the entry of a GPU engine that is running already goes first (the
    highest in the user's order if several run), so a reading attaches to what is loaded instead of
    loading a second engine. Only entries the user switched on can move; the rest keeps its
    order."""
    if not chosen["prefer_loaded"]:
        return chosen
    loaded = {
        (row["engine"], row["host"])
        for row in rows
        if row["status"] == "running" and row["needs_gpu"]
    }
    entries = chosen["entries"]
    usable = [
        entry
        for entry in entries
        if entry["enabled"] and entry["offered"] and (entry["engine"], entry["host"]) in loaded
    ]
    if not usable:
        return chosen
    first = usable[0]
    return {**chosen, "entries": [first] + [entry for entry in entries if entry is not first]}


def voices(config: TtsSuiteConfig, directory: Path, engine: str) -> list[dict[str, str]]:
    """The voices of an engine: `id` (what a request names) and `label`."""
    request = _request(config, directory, f"/voices?engine={urllib.parse.quote(engine)}", None)
    with _open(config, request) as response:
        listed: list[dict[str, str]] = json.load(response)
    return [{"id": voice["name"], "label": voice["label"]} for voice in listed]


def _engine_settings(chosen: dict[str, Any], engines: list[str]) -> dict[str, dict[str, Any]]:
    """Per engine what the user set: the voice, and speed and pitch where one was given (the
    service uses its own values for the rest)."""
    settings: dict[str, dict[str, Any]] = {}
    for engine in engines:
        own: dict[str, Any] = {}
        if chosen["voices"].get(engine):
            own["voice"] = chosen["voices"][engine]
        tuning = chosen["tuning"].get(engine, {})
        own.update({key: value for key, value in tuning.items() if value is not None})
        if own:
            settings[engine] = own
    return settings


def speak(
    config: TtsSuiteConfig,
    directory: Path,
    text: str,
    language: str,
    chosen: dict[str, Any],
) -> FrameStream:
    """The frames of the reading, with the entries the user switched on and the service offers
    (`chosen` as merged_choices has it: `entries` in the order of speaking, `voices` per engine).
    The service answers once the first piece exists, so a
    reading that cannot start raises here, before anything is sent on; later failures are frames."""
    # Without a choice the service refuses (a request names its engines); the user chooses first.
    on = [entry for entry in chosen["entries"] if entry["enabled"] and entry["offered"]]
    if not on:
        raise NothingSwitchedOnError(
            "no engine of the TTS service is switched on: choose them in the settings"
            " (Engines of the TTS service)"
        )
    engines = list(dict.fromkeys(entry["engine"] for entry in on))
    head: dict[str, Any] = {
        "text": text,
        "language": language,
        "paragraph_pause_ms": chosen["paragraph_pause_ms"],
        "engines": [
            {"engine": entry["engine"], "unit": entry["unit"], "host": entry["host"]}
            for entry in on
        ],
        "voices": _engine_settings(chosen, engines),
    }
    return FrameStream(_open(config, _request(config, directory, "/speak", head)))
