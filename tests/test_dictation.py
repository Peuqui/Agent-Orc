import pytest

from agent_orc.config import DictationConfig
from agent_orc.dictation import (
    DictationServiceError,
    GpuUnavailableError,
    ServiceStatus,
    Transcription,
    UnsupportedAudioError,
    service_status,
    transcribe,
)
from tests.conftest import FakeStt

AUDIO = b"\x1a\x45\xdf\xa3 not really opus"


def dictation_config(url: str) -> DictationConfig:
    return DictationConfig(stt_url=url, language="de", timeout_seconds=5)


def test_transcribes_with_chosen_device(fake_stt: FakeStt) -> None:
    fake_stt.answer = {"text": " Hallo Welt ", "device": "cuda"}
    result = transcribe(AUDIO, "audio/webm;codecs=opus", "cuda", dictation_config(fake_stt.url))
    assert result == Transcription("Hallo Welt", "cuda")
    body = fake_stt.bodies[0]
    assert b'name="device"\r\n\r\ncuda\r\n' in body
    assert b'name="language"\r\n\r\nde\r\n' in body
    assert b'filename="dictation.webm"\r\nContent-Type: audio/webm\r\n\r\n' + AUDIO in body
    # The engine and its quality are the service's: nothing of them goes along.
    assert b'name="engine"' not in body
    assert b'name="quality"' not in body


def test_auto_reports_the_device_that_really_transcribed(fake_stt: FakeStt) -> None:
    # The service fell back from the full GPU to the CPU: the answer says so.
    fallback = [{"tried": "cuda parakeet fp32", "reason": "no room"}]
    fake_stt.answer = {"text": "Hallo", "device": "cpu", "fallback": fallback}
    result = transcribe(AUDIO, "audio/webm", "auto", dictation_config(fake_stt.url))
    assert result == Transcription("Hallo", "cpu")
    assert b'name="device"\r\n\r\nauto\r\n' in fake_stt.bodies[0]


def test_the_service_settings_show_what_the_engine_uses(fake_stt: FakeStt) -> None:
    # Each device has its own engine: Whisper's size on the GPU, Parakeet's precision on the CPU.
    assert service_status(dictation_config(fake_stt.url)) == ServiceStatus(
        gpu="whisper large-v3", cpu="parakeet int8"
    )
    assert service_status(dictation_config("http://127.0.0.1:9")) is None


def test_full_gpu_is_reported_not_switched_to_cpu(fake_stt: FakeStt) -> None:
    fake_stt.status = 503
    fake_stt.answer = {"error": "no GPU with enough VRAM"}
    with pytest.raises(GpuUnavailableError, match="VRAM"):
        transcribe(AUDIO, "audio/ogg", "cuda", dictation_config(fake_stt.url))
    assert len(fake_stt.bodies) == 1


def test_service_error(fake_stt: FakeStt) -> None:
    fake_stt.status = 500
    fake_stt.answer = {"error": "kaputt"}
    with pytest.raises(DictationServiceError, match="500"):
        transcribe(AUDIO, "audio/ogg", "cpu", dictation_config(fake_stt.url))


def test_unreachable_service() -> None:
    # Port 9 (discard) has no listener here.
    with pytest.raises(DictationServiceError):
        transcribe(AUDIO, "audio/ogg", "cpu", dictation_config("http://127.0.0.1:9"))


def test_rejects_unknown_audio_format(fake_stt: FakeStt) -> None:
    with pytest.raises(UnsupportedAudioError):
        transcribe(AUDIO, "video/x-msvideo", "cpu", dictation_config(fake_stt.url))
    assert fake_stt.bodies == []


def test_without_stt_service() -> None:
    config = DictationConfig(stt_url=None, language="de", timeout_seconds=5)
    with pytest.raises(DictationServiceError, match="no STT-Suite"):
        transcribe(AUDIO, "audio/ogg", "cpu", config)
