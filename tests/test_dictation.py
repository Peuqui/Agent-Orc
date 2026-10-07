import pytest

from agent_orc.config import DictationConfig
from agent_orc.dictation import (
    DictationServiceError,
    GpuUnavailableError,
    ServiceStatus,
    UnsupportedAudioError,
    service_status,
    transcribe,
)
from tests.conftest import FakeWhisper

AUDIO = b"\x1a\x45\xdf\xa3 not really opus"


def dictation_config(url: str) -> DictationConfig:
    return DictationConfig(whisper_url=url, language="de", timeout_seconds=5)


def test_transcribes_with_chosen_device(fake_whisper: FakeWhisper) -> None:
    text = transcribe(AUDIO, "audio/webm;codecs=opus", "cuda", dictation_config(fake_whisper.url))
    assert text == "Hallo Welt"
    body = fake_whisper.bodies[0]
    assert b'name="device"\r\n\r\ncuda\r\n' in body
    assert b'name="language"\r\n\r\nde\r\n' in body
    assert b'filename="dictation.webm"\r\nContent-Type: audio/webm\r\n\r\n' + AUDIO in body
    # The engine and its quality are the service's: nothing of them goes along.
    assert b'name="engine"' not in body
    assert b'name="quality"' not in body


def test_the_service_settings_show_what_the_engine_uses(fake_whisper: FakeWhisper) -> None:
    # Parakeet: its precision per device (the Whisper models are not in use).
    assert service_status(dictation_config(fake_whisper.url)) == ServiceStatus(
        "parakeet", gpu="fp32", cpu="int8"
    )
    assert service_status(dictation_config("http://127.0.0.1:9")) is None


def test_full_gpu_is_reported_not_switched_to_cpu(fake_whisper: FakeWhisper) -> None:
    fake_whisper.status = 503
    fake_whisper.answer = {"error": "no GPU with enough VRAM"}
    with pytest.raises(GpuUnavailableError, match="VRAM"):
        transcribe(AUDIO, "audio/ogg", "cuda", dictation_config(fake_whisper.url))
    assert len(fake_whisper.bodies) == 1


def test_service_error(fake_whisper: FakeWhisper) -> None:
    fake_whisper.status = 500
    fake_whisper.answer = {"error": "kaputt"}
    with pytest.raises(DictationServiceError, match="500"):
        transcribe(AUDIO, "audio/ogg", "cpu", dictation_config(fake_whisper.url))


def test_unreachable_service() -> None:
    # Port 9 (discard) has no listener here.
    with pytest.raises(DictationServiceError):
        transcribe(AUDIO, "audio/ogg", "cpu", dictation_config("http://127.0.0.1:9"))


def test_rejects_unknown_audio_format(fake_whisper: FakeWhisper) -> None:
    with pytest.raises(UnsupportedAudioError):
        transcribe(AUDIO, "video/x-msvideo", "cpu", dictation_config(fake_whisper.url))
    assert fake_whisper.bodies == []


def test_without_whisper_service() -> None:
    config = DictationConfig(whisper_url=None, language="de", timeout_seconds=5)
    with pytest.raises(DictationServiceError, match="no Whisper"):
        transcribe(AUDIO, "audio/ogg", "cpu", config)
