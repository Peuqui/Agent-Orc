"""The settings that are the same on every device, kept on the server. Everything that depends on
the device itself (the sizes of the fonts, the scrolling, the voices of the browser, the columns of
a workspace) stays in the browser, see frontend/src/composables/useSettings.ts. The defaults of
these settings are here and nowhere else: a page shows what the server sends."""

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


class SharedSettingsInvalidError(ValueError):
    """A change of the shared settings that cannot be kept (unknown, or out of range)."""


class SharedSettings(BaseModel):
    # Where the STT-Suite transcribes a dictation: the CPU unless the GPU is chosen on purpose.
    dictation_device: Literal["cpu", "cuda"] = "cpu"
    # A dictation goes to the agent as soon as it is transcribed, without pressing send.
    dictation_sends_at_once: bool = False
    # Which speech output reads answers aloud: "browser", "echo" or "tts-suite".
    speech_engine: str = Field(default="browser", min_length=1)
    # Speed and pitch of what is read aloud, as overrides: with nothing set the TTS service's own
    # values apply (per engine and voice) and the browser's voices speak at 1 (unchanged).
    speech_rate: float | None = Field(default=None, gt=0, le=4)
    speech_pitch: float | None = Field(default=None, gt=0, le=4)
    # The agent's name is said before its answer.
    speech_announce_name: bool = True
    # The most characters of an answer that are read aloud without a "listening paragraph".
    speech_max_chars: int = Field(default=900, ge=100, le=100_000)
    # The voice chosen for an output (not the browser's: its voices are the device's own).
    speech_voices: dict[str, str] = Field(default_factory=dict)


def changed(current: dict[str, Any], change: dict[str, Any]) -> SharedSettings:
    """The settings after `change` (some of them, by name) is applied to `current` (as stored)."""
    unknown = sorted(set(change) - set(SharedSettings.model_fields))
    if unknown:
        raise SharedSettingsInvalidError(f"unknown settings: {', '.join(unknown)}")
    try:
        return SharedSettings.model_validate({**current, **change})
    except ValidationError as error:
        raise SharedSettingsInvalidError(str(error)) from error
