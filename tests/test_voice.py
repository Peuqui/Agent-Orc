"""Speaking to an agent on the Echo Dot: who is addressed, the question back, the spoken yes."""

import json
import time
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.config import Config, VoiceConfig, default_config_text
from agent_orc.context import store_status
from agent_orc.voice import Action, VoiceAgent, VoiceRouter
from tests.conftest import MAX_CHARS, TOKEN, FakeAifred, FakeClock

NOW = 1_000_000.0
MINUTE = 60.0
VOICE_TOKEN = "voice-secret"


def voice_config() -> VoiceConfig:
    return VoiceConfig(
        token_file="voice-token",
        window_minutes=10,
        confirm_minutes=2,
        name_similarity=0.75,
        yes_words=["ja", "richtig"],
        no_words=["nein"],
        ask_line="An {agent}, richtig?",
        sent_line="Gesendet an {agent}.",
        discarded_line="Verworfen.",
        unknown_agent_line="Welcher Agent?",
    )


AGENTS = [
    VoiceAgent("a", "Whisper", NOW - 5 * MINUTE),
    VoiceAgent("b", "Agent-Orc", NOW - 30 * MINUTE),
    VoiceAgent("c", "FreeEchoDot2", None),
]


def test_a_name_at_the_start_picks_the_agent_and_is_not_part_of_the_text() -> None:
    router = VoiceRouter(voice_config())
    decision = router.handle("buero", "Agent Orc, baue den Eingang", AGENTS, NOW)
    assert (decision.action, decision.agent, decision.text) == (
        Action.ASK,
        AGENTS[1],
        "baue den Eingang",
    )
    # A mishearing close enough still finds it.
    assert router.handle("buero", "Visper starte neu", AGENTS, NOW).agent == AGENTS[0]


def test_without_a_name_the_agent_that_answered_last_gets_it_if_that_was_recent() -> None:
    router = VoiceRouter(voice_config())
    decision = router.handle("buero", "wie ist der Stand", AGENTS, NOW)
    assert (decision.agent, decision.text) == (AGENTS[0], "wie ist der Stand")
    # 30 minutes ago is out of the window; the one that never answered is no candidate.
    later = router.handle("buero", "wie ist der Stand", AGENTS, NOW + 10 * MINUTE)
    assert later.action is Action.UNKNOWN_AGENT


def test_nothing_is_sent_before_a_yes_and_a_no_drops_it() -> None:
    router = VoiceRouter(voice_config())
    router.handle("buero", "Whisper starte neu", AGENTS, NOW)
    sent = router.handle("buero", "Ja.", AGENTS, NOW + 10)
    assert (sent.action, sent.agent, sent.text) == (Action.SEND, AGENTS[0], "starte neu")
    # The yes counts once; said again it is only a request, which asks back first.
    assert router.handle("buero", "Ja", AGENTS, NOW + 20).action is Action.ASK

    router.handle("buero", "Whisper starte neu", AGENTS, NOW)
    assert router.handle("buero", "Nein, doch nicht", AGENTS, NOW + 10).action is Action.DISCARD
    assert router.handle("buero", "ja", AGENTS, NOW + 20).action is Action.ASK


def test_a_yes_to_a_forgotten_question_or_in_another_room_sends_nothing() -> None:
    router = VoiceRouter(voice_config())
    router.handle("buero", "Whisper starte neu", AGENTS, NOW)
    assert router.handle("kueche", "ja", AGENTS, NOW + 10).action is not Action.SEND
    assert router.handle("buero", "ja", AGENTS, NOW + 3 * MINUTE).action is not Action.SEND


def test_another_request_replaces_the_open_question() -> None:
    router = VoiceRouter(voice_config())
    router.handle("buero", "Whisper starte neu", AGENTS, NOW)
    router.handle("buero", "Agent-Orc baue das", AGENTS, NOW + 5)
    sent = router.handle("buero", "ja", AGENTS, NOW + 10)
    assert (sent.agent, sent.text) == (AGENTS[1], "baue das")


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    directory = tmp_path / "config" / "agent-orc"
    directory.mkdir(parents=True)
    (directory / "announce-token").write_text(TOKEN, encoding="utf-8")
    (directory / "voice-token").write_text(VOICE_TOKEN + "\n", encoding="utf-8")
    return home


def voice_client(home: Path, socket_name: str, clock: FakeClock, aifred_url: str) -> TestClient:
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["server"]["cookie_secure"] = False
    raw["files"]["base_dir"] = str(home / "projects")
    raw["tmux"]["socket_name"] = socket_name
    raw["announce"] = {
        "url": aifred_url,
        "token_file": "announce-token",
        "max_chars": MAX_CHARS,
        "timeout_seconds": 5,
    }
    raw["voice"] = voice_config().model_dump()
    raw["agents"] = {
        "listener": {
            "label": "Listener",
            "start": ["sh", "-c", "exec cat"],
            "resume": ["true"],
        },
    }
    app = create_app(
        Config.model_validate(raw), new_credentials("x" * 16), static_dir=None, clock=clock
    )
    return TestClient(app)


def say(client: TestClient, text: str, token: str = VOICE_TOKEN) -> Any:
    return client.post(
        "/api/voice",
        json={"room": "testraum", "text": text},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_what_is_said_reaches_the_agent_only_after_the_spoken_yes(
    home: Path, socket_name: str, clock: FakeClock, aifred: str
) -> None:
    # Shortly after the answer in the transcript below (the login is valid from now on).
    clock.now = 1791367205 + 60.0
    client = voice_client(home, socket_name, clock, aifred)
    assert client.post("/api/login", json={"password": "x" * 16}).status_code == 204
    folder = home / "projects" / "whisper"
    folder.mkdir()
    started = {
        "profile": "listener",
        "path": str(folder),
        "resume": False,
        "effort": None,
        "ultracode": False,
        "conversation": None,
        "workspace": None,
    }
    session_id = client.post("/api/sessions", json=started).json()["id"]
    transcript = home / ".claude" / "projects" / "-whisper" / "conversation.jsonl"
    transcript.parent.mkdir(parents=True)
    entries = [
        {
            "type": "user",
            "uuid": "u1",
            "timestamp": "2026-10-07T10:00:00Z",
            "message": {"content": "?"},
        },
        {
            "type": "assistant",
            "uuid": "a2",
            "timestamp": "2026-10-07T10:00:05Z",
            "message": {"content": [{"type": "text", "text": "Fertig."}]},
        },
    ]
    transcript.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    store_status(session_id, {"model": {"display_name": "M"}, "transcript_path": str(transcript)})

    asked = say(client, "starte die Tests")
    assert asked.json() == {"action": "asked", "agent": "whisper"}
    assert FakeAifred.spoken[-1] == {"room": "testraum", "text": "An whisper, richtig?"}
    assert "starte die Tests" not in client.get(f"/api/sessions/{session_id}/text").json()["text"]

    assert say(client, "ja").json() == {"action": "sent", "agent": "whisper"}
    assert FakeAifred.spoken[-1]["text"] == "Gesendet an whisper."
    for _ in range(50):
        if "starte die Tests" in client.get(f"/api/sessions/{session_id}/text").json()["text"]:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the text did not reach the agent")


def test_only_aifred_with_the_token_may_speak_to_the_agents(
    home: Path, socket_name: str, clock: FakeClock, aifred: str
) -> None:
    client = voice_client(home, socket_name, clock, aifred)
    assert say(client, "hallo", token="wrong").status_code == 401
    assert client.post("/api/voice", json={"room": "r", "text": "x"}).status_code == 401
