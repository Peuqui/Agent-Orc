"""Dictation: audio recorded in the browser, transcribed by an STT-Suite service.

Speaks the API of the STT-Suite service: POST /transcribe with a multipart form holding the
audio file, the device ("cpu", "cuda" or "auto") and the language; the answer is JSON with "text"
and the "device" that really transcribed. "cpu" and "cuda" name exactly that device (a full GPU is
an error); "auto" follows the service's own list and may end on the CPU.
The engine and its model are the service's own settings, one per device (it keeps one model per
device and reloads it for a request that wants another): Agent-Orc only shows them.
"""

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from agent_orc.config import DictationConfig

Device = Literal["cpu", "cuda", "auto"]

# The service decodes by content; the file name only needs a fitting suffix.
AUDIO_SUFFIXES = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a"}
SERVICE_UNAVAILABLE = 503


class UnsupportedAudioError(ValueError):
    """The browser sent an audio format the service is not known to accept."""


class GpuUnavailableError(RuntimeError):
    """No GPU has room for the model right now; the CPU can be chosen instead."""


class DictationServiceError(RuntimeError):
    """The STT-Suite service cannot be reached or failed."""


# How long a look at the service's settings may take; the settings menu waits for it.
STATUS_TIMEOUT_SECONDS = 3


@dataclass(frozen=True)
class Transcription:
    """The text and the device ("cpu" or "cuda") the service really transcribed on."""

    text: str
    device: Literal["cpu", "cuda"]


@dataclass(frozen=True)
class ServiceStatus:
    """What the service transcribes with, per device: its engine and the model that engine uses,
    like "parakeet fp32" or "whisper large-v3", and whether a model sits in memory right now."""

    gpu: str
    cpu: str
    gpu_loaded: bool
    cpu_loaded: bool
    # Seconds until the idle GPU worker ends itself; None when the service never unloads it.
    gpu_ttl_remaining_seconds: int | None


def service_status(config: DictationConfig) -> ServiceStatus | None:
    """The service's settings (STT-Suite GET /status); None when no service is configured or it
    does not answer right now."""
    if config.stt_url is None:
        return None
    try:
        with urllib.request.urlopen(
            f"{config.stt_url}/status", timeout=STATUS_TIMEOUT_SECONDS
        ) as response:
            status = json.load(response)
    except (urllib.error.URLError, TimeoutError):
        return None
    return ServiceStatus(
        _configured(status, "gpu"),
        _configured(status, "cpu"),
        status["gpu_loaded"],
        status["cpu_loaded"],
        status.get("gpu_ttl_remaining_seconds"),
    )


def _configured(status: dict[str, Any], device: Literal["gpu", "cpu"]) -> str:
    """The engine of a device and its model: Parakeet has a precision (fp32, int8), Whisper a size
    (tiny to large-v3)."""
    engine = status[f"{device}_engine"]
    return f"{engine} {status[f'{device}_{"quality" if engine == "parakeet" else "model"}']}"


def transcribe(
    audio: bytes, content_type: str, device: Device, config: DictationConfig
) -> Transcription:
    if config.stt_url is None:
        raise DictationServiceError("no STT-Suite service configured")
    media_type = content_type.split(";")[0].strip()
    if media_type not in AUDIO_SUFFIXES:
        raise UnsupportedAudioError(content_type)
    boundary = uuid.uuid4().hex
    fields = {"device": device, "language": config.language}
    body = _multipart(boundary, fields, f"dictation{AUDIO_SUFFIXES[media_type]}", media_type, audio)
    request = urllib.request.Request(
        f"{config.stt_url}/transcribe",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        if error.code == SERVICE_UNAVAILABLE:
            raise GpuUnavailableError(detail) from error
        raise DictationServiceError(f"{error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise DictationServiceError(str(error)) from error
    return Transcription(answer["text"].strip(), answer["device"])


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
