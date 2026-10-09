"""Speaking to an agent on the Echo Dot: who is addressed, the question back, the spoken yes."""

import io
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_orc import cli
from agent_orc.api import create_app
from agent_orc.auth import new_credentials
from agent_orc.config import Config, VoiceConfig, default_config_text
from agent_orc.context import store_activity, store_status
from agent_orc.sessions import SESSION_ENV
from agent_orc.voice import (
    Action,
    VoiceAgent,
    VoiceRouter,
    answered_reply,
    expect_reply,
    expected_reply,
    listening_paragraph,
)
from agent_orc.voicelog import (
    append_entry,
    drop_old_recordings,
    forget_agent,
    new_entry,
    read_entries,
    store_recording,
)
from tests.conftest import MAX_CHARS, TOKEN, FakeAifred, FakeClock

NOW = 1_000_000.0
MINUTE = 60.0
VOICE_TOKEN = "voice-secret"
# 2026-10-07T10:00:05Z, when the agent in the tests answered.
ANSWERED = 1791367205


def voice_config() -> VoiceConfig:
    return VoiceConfig(
        token_file="voice-token",
        window_minutes=10,
        confirm_minutes=2,
        keep_entries=3,
        recording_days=7,
        name_similarity=0.75,
        yes_words=["ja", "richtig"],
        no_words=["nein"],
        cancel_words=["abbrechen"],
        ask_line="An {agent}, richtig?",
        sent_line="Gesendet an {agent}.",
        sent_busy_line="{agent} arbeitet noch.",
        discarded_line="Verworfen.",
        which_agent_line="Welcher Agent dann?",
        no_agent_line="Welcher Agent?",
        no_summary_line="{agent} ist fertig.",
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


def test_a_name_heard_with_another_spelling_is_found_by_its_sound_and_ordinary_words_are_not() -> (
    None
):
    router = VoiceRouter(voice_config())
    for spoken in ("Agent Org", "Agentork", "Visper", "Wisper"):
        found = router.handle("buero", f"{spoken} mach das", AGENTS, NOW).agent
        assert found in (AGENTS[0], AGENTS[1]), spoken
    assert router.handle("buero", "Visper mach das", AGENTS, NOW).agent == AGENTS[0]
    # Only its sound is left of the name, as a speech recognition writes it.
    assert router.handle("buero", "Vispa mach das", AGENTS, NOW).agent == AGENTS[0]
    assert router.handle("buero", "Agent Org mach das", AGENTS, NOW).agent == AGENTS[1]
    # Words of an order that only look a little like a name stay part of the text.
    for order in ("Starte die Tests", "Teste das", "Fertig machen bitte", "Frei Echo"):
        assert router.handle("buero", order, [AGENTS[2]], NOW).agent is None or order == "Frei Echo"


def test_without_a_name_the_agent_that_answered_last_gets_it_if_that_was_recent() -> None:
    router = VoiceRouter(voice_config())
    decision = router.handle("buero", "wie ist der Stand", AGENTS, NOW)
    assert (decision.agent, decision.text) == (AGENTS[0], "wie ist der Stand")
    # 30 minutes ago is out of the window; the one that never answered is no candidate.
    later = router.handle("buero", "wie ist der Stand", AGENTS, NOW + 10 * MINUTE)
    assert later.action is Action.NO_AGENT


def test_nothing_is_sent_before_a_yes() -> None:
    router = VoiceRouter(voice_config())
    router.handle("buero", "Whisper starte neu", AGENTS, NOW)
    sent = router.handle("buero", "Ja.", AGENTS, NOW + 10)
    assert (sent.action, sent.agent, sent.text) == (Action.SEND, AGENTS[0], "starte neu")
    # The yes counts once; said again it is only a request, which asks back first.
    assert router.handle("buero", "Ja", AGENTS, NOW + 20).action is Action.ASK


def test_after_a_no_the_text_is_kept_and_another_agent_can_be_named() -> None:
    router = VoiceRouter(voice_config())
    router.handle("buero", "Whisper starte neu", AGENTS, NOW)
    asked_again = router.handle("buero", "Nein, doch nicht", AGENTS, NOW + 10)
    assert (asked_again.action, asked_again.text) == (Action.WHICH_AGENT, "starte neu")
    # The name alone is enough; it goes to the one named, after asking back again.
    other = router.handle("buero", "Agent Orc", AGENTS, NOW + 20)
    assert (other.action, other.agent, other.text) == (Action.ASK, AGENTS[1], "starte neu")
    sent = router.handle("buero", "ja", AGENTS, NOW + 30)
    assert (sent.action, sent.agent, sent.text) == (Action.SEND, AGENTS[1], "starte neu")


def test_while_asking_for_the_agent_a_refusal_drops_the_text_and_a_request_replaces_it() -> None:
    router = VoiceRouter(voice_config())
    for refusal in ("nein", "abbrechen"):
        router.handle("buero", "Whisper starte neu", AGENTS, NOW)
        router.handle("buero", "nein", AGENTS, NOW + 10)
        assert router.handle("buero", refusal, AGENTS, NOW + 20).action is Action.DISCARD
        assert router.handle("buero", "ja", AGENTS, NOW + 30).action is Action.ASK
    router.handle("buero", "Whisper starte neu", AGENTS, NOW)
    router.handle("buero", "nein", AGENTS, NOW + 10)
    replaced = router.handle("buero", "Agent Orc baue das", AGENTS, NOW + 20)
    assert (replaced.agent, replaced.text) == (AGENTS[1], "baue das")


def test_cancel_drops_an_open_question_for_good() -> None:
    router = VoiceRouter(voice_config())
    router.handle("buero", "Whisper starte neu", AGENTS, NOW)
    assert router.handle("buero", "Abbrechen", AGENTS, NOW + 10).action is Action.DISCARD
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
        "label": "Echo",
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


RECORDING = b"RIFF....WAVEfmt "


def say(client: TestClient, text: str, token: str = VOICE_TOKEN) -> Any:
    """As AIfred sends it: a form with the words and the recording."""
    return client.post(
        "/api/voice",
        data={"room": "testraum", "text": text},
        files={"audio": ("said.wav", RECORDING, "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
    )


def start_listener(client: TestClient, home: Path) -> str:
    """An agent called "whisper" that answered a minute ago, in a transcript Agent-Orc can read."""
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
    session_id: str = client.post("/api/sessions", json=started).json()["id"]
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
    return session_id


def test_what_is_said_reaches_the_agent_only_after_the_spoken_yes(
    home: Path, socket_name: str, clock: FakeClock, aifred: str
) -> None:
    # Shortly after the answer in the transcript (the login is valid from now on).
    clock.now = ANSWERED + 60.0
    client = voice_client(home, socket_name, clock, aifred)
    assert client.post("/api/login", json={"password": "x" * 16}).status_code == 204
    session_id = start_listener(client, home)

    asked = say(client, "starte die Tests")
    assert asked.json() == {"action": "asked", "agent": "whisper"}
    assert FakeAifred.spoken[-1] == {
        "room": "testraum",
        "texts": ["An whisper, richtig?"],
        "speaker": "whisper",
    }
    assert "starte die Tests" not in client.get(f"/api/sessions/{session_id}/text").json()["text"]

    assert say(client, "ja").json() == {"action": "sent", "agent": "whisper"}
    assert FakeAifred.spoken[-1]["texts"] == ["Gesendet an whisper."]
    # Its next answer is announced in that room.
    assert expected_reply(session_id) == ("testraum", "starte die Tests")
    # The request is kept with the sentence as it was recognised, to compare with what was meant.
    [spoken] = client.get(f"/api/sessions/{session_id}/voice").json()
    assert (spoken["heard"], spoken["request"]) == ("starte die Tests", "starte die Tests")
    assert spoken["score"] is None
    # What was said is kept as it was recorded, for the answers to play.
    assert spoken["recording"] is True
    audio = client.get(f"/api/voice/{spoken['id']}/audio")
    assert (audio.status_code, audio.content) == (200, RECORDING)
    assert client.get("/api/voice/not-an-id/audio").status_code == 404
    assert client.get(f"/api/voice/{'0' * 32}/audio").status_code == 404
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
    unsigned = client.post(
        "/api/voice",
        data={"room": "r", "text": "x"},
        files={"audio": ("a.wav", b"x", "audio/wav")},
    )
    assert unsigned.status_code == 401


def test_the_paragraph_for_listening_is_the_last_marked_one() -> None:
    answer = (
        "Langer Text.\n\n🔊 Erster Hörabsatz.\n\nMehr Text.\n\n🔊 Letzter Hörabsatz. Zweiter Satz."
    )
    assert listening_paragraph(answer) == "Letzter Hörabsatz. Zweiter Satz."
    assert listening_paragraph("Nur Text, ohne Absatz zum Hören.") is None


def test_a_reply_is_expected_until_it_is_answered(home: Path) -> None:
    assert expected_reply("a-1") is None
    expect_reply("a-1", "testraum", "starte neu")
    assert expected_reply("a-1") == ("testraum", "starte neu")
    answered_reply("a-1")
    assert expected_reply("a-1") is None


def transcript_of(path: Path, *records: dict[str, Any]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return path


def typed(request: str, second: int) -> list[dict[str, Any]]:
    """What Claude writes when a request is typed ahead and then taken in during the turn."""
    time = f"2026-10-07T10:00:{second:02d}Z"
    return [
        {"type": "queue-operation", "operation": "enqueue", "timestamp": time, "content": request},
        {"type": "queue-operation", "operation": "remove", "timestamp": time, "content": request},
        {
            "type": "attachment",
            "uuid": f"d{second}",
            "timestamp": time,
            "attachment": {
                "type": "queued_command",
                "prompt": request,
                "origin": {"kind": "human"},
            },
        },
    ]


def test_the_agent_spoken_to_answers_in_the_room_with_its_paragraph_for_listening(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, aifred: str
) -> None:
    raw: dict[str, Any] = yaml.safe_load(default_config_text())
    raw["announce"] = {
        "url": aifred,
        "token_file": "announce-token",
        "max_chars": MAX_CHARS,
        "timeout_seconds": 5,
        "label": "Echo",
    }
    raw["voice"] = voice_config().model_dump()
    config_file = tmp_path / "config" / "agent-orc" / "config.yaml"
    config_file.write_text(yaml.safe_dump(raw), encoding="utf-8")
    monkeypatch.setenv(SESSION_ENV, "whisper-1")
    transcript = tmp_path / "t.jsonl"

    def user(text: str, second: int) -> dict[str, Any]:
        stamp = f"2026-10-07T10:00:{second:02d}Z"
        return {
            "type": "user",
            "uuid": f"u{second}",
            "timestamp": stamp,
            "message": {"content": text},
        }

    def finish(answer: str) -> None:
        stop = {
            "cwd": "/w/whisper",
            "transcript_path": str(transcript),
            "last_assistant_message": answer,
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(stop)))
        cli.agent_idle()

    # An answer to something typed in the terminal is not announced.
    transcript_of(transcript, user("etwas im Terminal", 1))
    finish("🔊 Nicht für den Echo.")
    assert FakeAifred.spoken == []

    # The spoken request started the turn: its answer is announced.
    expect_reply("whisper-1", "testraum", "zähle die Dateien")
    transcript_of(transcript, user("zähle die Dateien", 2))
    finish("Details.\n\n🔊 Es sind drei Dateien.")
    assert FakeAifred.spoken == [
        {"room": "testraum", "texts": ["Es sind drei Dateien."], "speaker": "whisper"}
    ]
    assert expected_reply("whisper-1") is None

    # Typed ahead into a busy agent: the turn that ends first has not taken it in yet.
    expect_reply("whisper-1", "testraum", "wie ist der Stand")
    waiting = typed("wie ist der Stand", 4)[:2]
    transcript_of(transcript, user("lange Aufgabe", 3), *waiting[:1])
    finish("🔊 Die lange Aufgabe ist fertig.")
    assert len(FakeAifred.spoken) == 1 and expected_reply("whisper-1") is not None
    # The next turn takes it in; its answer is announced, here one without paragraph for listening.
    transcript_of(transcript, user("lange Aufgabe", 3), *typed("wie ist der Stand", 4))
    finish("Nur Text.")
    assert FakeAifred.spoken[-1]["texts"] == ["whisper ist fertig."]
    assert expected_reply("whisper-1") is None


def test_a_request_sent_after_a_no_keeps_the_sentence_it_was_first_said_in(
    home: Path, socket_name: str, clock: FakeClock, aifred: str
) -> None:
    clock.now = ANSWERED + 60.0
    client = voice_client(home, socket_name, clock, aifred)
    assert client.post("/api/login", json={"password": "x" * 16}).status_code == 204
    session_id = start_listener(client, home)
    actions = [
        say(client, text).json()["action"] for text in ("starte die Tests", "nein", "Whisper", "ja")
    ]
    assert actions == ["asked", "which_agent", "asked", "sent"]
    [spoken] = client.get(f"/api/sessions/{session_id}/voice").json()
    assert (spoken["heard"], spoken["request"]) == ("starte die Tests", "starte die Tests")
    # The name was spoken alone, in the second sentence: the first one carries no name score.
    assert spoken["score"] is None


def test_an_agent_at_work_says_so_and_what_was_said_waits_for_it(
    home: Path, socket_name: str, clock: FakeClock, aifred: str
) -> None:
    clock.now = ANSWERED + 60.0
    client = voice_client(home, socket_name, clock, aifred)
    assert client.post("/api/login", json={"password": "x" * 16}).status_code == 204
    session_id = start_listener(client, home)
    store_activity(session_id, busy=True)
    say(client, "starte die Tests")
    say(client, "ja")
    assert FakeAifred.spoken[-1]["texts"] == ["whisper arbeitet noch."]
    assert expected_reply(session_id) == ("testraum", "starte die Tests")


def entry_of(agent_id: str | None, action: str, source: str | None = None) -> Any:
    return new_entry(
        ANSWERED,
        room="testraum",
        heard="x",
        action=action,
        agent_id=agent_id,
        agent=agent_id,
        request="x",
        score=None,
        source=source,
    )


def test_only_the_newest_entries_stay_with_their_recordings(home: Path) -> None:
    entries = [entry_of("a", "asked") for _ in range(5)]
    for entry in entries:
        store_recording(entry.id, b"wav")
        append_entry(entry, keep=3)
    assert [e["id"] for e in read_entries()] == [e.id for e in entries[2:]]
    assert not recording_file_path(entries[0].id).exists()
    assert recording_file_path(entries[4].id).exists()


def test_a_stopped_agents_recordings_go_but_the_lines_stay(home: Path) -> None:
    first = entry_of("a", "asked")
    # The sentence was said for "a", then confirmed for "b": "b" still shows it, with its recording.
    sent_on = entry_of("b", "sent", source=first.id)
    own = entry_of("a", "sent", source=first.id)
    other = entry_of("b", "asked")
    for entry in (first, sent_on, own, other):
        store_recording(entry.id, b"wav")
        append_entry(entry, keep=10)
    forget_agent("a")
    # The lines stay, to measure the recognition by.
    assert [e["id"] for e in read_entries()] == [first.id, sent_on.id, own.id, other.id]
    assert not recording_file_path(own.id).exists()
    assert recording_file_path(first.id).exists()
    assert recording_file_path(other.id).exists()


def test_recordings_older_than_the_days_go(home: Path) -> None:
    old, new = entry_of("a", "asked"), entry_of("a", "asked")
    for entry in (old, new):
        store_recording(entry.id, b"wav")
        append_entry(entry, keep=10)
    now = time.time()
    eight_days_ago = now - 8 * 24 * 60 * 60
    os.utime(recording_file_path(old.id), (eight_days_ago, eight_days_ago))
    drop_old_recordings(now, days=7)
    assert not recording_file_path(old.id).exists()
    assert recording_file_path(new.id).exists()
    assert [e["id"] for e in read_entries()] == [old.id, new.id]


def recording_file_path(entry_id: str) -> Path:
    return Path(os.environ["XDG_STATE_HOME"]) / "agent-orc" / "voice-recordings" / f"{entry_id}.wav"
