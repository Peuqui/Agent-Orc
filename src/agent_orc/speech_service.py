"""Reading answers aloud with a TTS-Suite service: it chooses the engine, cuts and cleans the text
and answers with frames of audio (see its docs/INTERFACE.md). Agent-Orc hands the browser those
frames unchanged: the browser cannot reach the service itself (it may be on the server's loopback),
and the token stays on the server.
"""

import contextlib
import json
import urllib.error
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


def voices(config: TtsSuiteConfig, directory: Path) -> list[dict[str, str]]:
    """The voices of the shared folder: `id` (what a request names) and `label`."""
    with _open(config, _request(config, directory, "/voices", None)) as response:
        listed: list[dict[str, str]] = json.load(response)
    return [{"id": voice["name"], "label": voice["label"]} for voice in listed]


def speak(
    config: TtsSuiteConfig,
    directory: Path,
    text: str,
    language: str,
    voice: str | None,
    speed: float | None,
) -> Iterator[bytes]:
    """The frames of the reading. The service answers once the first piece exists, so a reading
    that cannot start raises here, before anything is sent on; later failures are frames."""
    head: dict[str, Any] = {"text": text, "language": language}
    if voice:
        head["voice"] = voice
    if speed is not None:
        head["speed"] = speed
    response = _open(config, _request(config, directory, "/speak", head))

    def frames() -> Iterator[bytes]:
        with response:
            while chunk := response.read(CHUNK_BYTES):
                yield chunk

    return frames()
