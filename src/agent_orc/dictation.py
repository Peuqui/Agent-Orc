"""Dictation: audio recorded in the browser, transcribed by a Whisper service.

Speaks the API of the whisper-stt service: POST /transcribe with a multipart form holding the
audio file, the device ("cpu" or "cuda") and the language; the answer is JSON with "text".
The device is the user's choice per dictation; nothing switches between them automatically.
"""

import json
import urllib.error
import urllib.request
import uuid
from typing import Literal

from agent_orc.config import DictationConfig

Device = Literal["cpu", "cuda"]

# Whisper decodes by content; the file name only needs a fitting suffix.
AUDIO_SUFFIXES = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a"}
SERVICE_UNAVAILABLE = 503


class UnsupportedAudioError(ValueError):
    """The browser sent an audio format the service is not known to accept."""


class GpuUnavailableError(RuntimeError):
    """No GPU has room for the model right now; the CPU can be chosen instead."""


class DictationServiceError(RuntimeError):
    """The Whisper service cannot be reached or failed."""


# How long a look at the service's engines may take; the settings menu waits for it.
STATUS_TIMEOUT_SECONDS = 3


def service_engines(config: DictationConfig) -> list[str]:
    """The engines the Whisper service offers (whisper-stt GET /status), e.g. whisper and
    parakeet; none when no service is configured or it does not answer right now."""
    if config.whisper_url is None:
        return []
    try:
        with urllib.request.urlopen(
            f"{config.whisper_url}/status", timeout=STATUS_TIMEOUT_SECONDS
        ) as response:
            engines: list[str] = json.load(response).get("engines", [])
    except (urllib.error.URLError, TimeoutError):
        return []
    return engines


def transcribe(
    audio: bytes, content_type: str, device: Device, engine: str | None, config: DictationConfig
) -> str:
    """engine None: the service's default engine."""
    if config.whisper_url is None:
        raise DictationServiceError("no Whisper service configured")
    media_type = content_type.split(";")[0].strip()
    if media_type not in AUDIO_SUFFIXES:
        raise UnsupportedAudioError(content_type)
    boundary = uuid.uuid4().hex
    fields = {"device": device, "language": config.language}
    if engine is not None:
        fields["engine"] = engine
    body = _multipart(boundary, fields, f"dictation{AUDIO_SUFFIXES[media_type]}", media_type, audio)
    request = urllib.request.Request(
        f"{config.whisper_url}/transcribe",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            text: str = json.load(response)["text"]
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        if error.code == SERVICE_UNAVAILABLE:
            raise GpuUnavailableError(detail) from error
        raise DictationServiceError(f"{error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise DictationServiceError(str(error)) from error
    return text.strip()


def _multipart(
    boundary: str, fields: dict[str, str], file_name: str, media_type: str, content: bytes
) -> bytes:
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{file_name}"\r\nContent-Type: {media_type}\r\n\r\n'.encode()
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)
