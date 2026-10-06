"""Reading answers aloud on an Echo Dot: AIfred owns the device (its WebSocket server, the voice
and the queue of announcements), Agent-Orc hands it the text through AIfred's announce endpoint.

No model sits in between. The token stays on the server: the browser asks Agent-Orc, which asks
AIfred.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from agent_orc.config import AnnounceConfig

# Named in AIfred's record of the announcements when no agent is the speaker.
APP_SPEAKER = "Agent-Orc"
NOT_FOUND = 404
TEXT_TOO_LONG = 413


class AnnounceError(RuntimeError):
    """AIfred cannot be reached or refused."""


class UnknownRoomError(AnnounceError):
    """No Echo is connected in this room."""


class TextTooLongError(AnnounceError):
    pass


def _request(
    config: AnnounceConfig, directory: Path, path: str, body: dict[str, Any] | None
) -> dict[str, list[str]]:
    token = (directory / config.token_file).read_text(encoding="utf-8").strip()
    request = urllib.request.Request(
        f"{config.url}{path}",
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            answer: dict[str, list[str]] = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        if error.code == NOT_FOUND:
            raise UnknownRoomError(detail) from error
        if error.code == TEXT_TOO_LONG:
            raise TextTooLongError(detail) from error
        raise AnnounceError(f"{error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise AnnounceError(str(error)) from error
    return answer


def rooms(config: AnnounceConfig, directory: Path) -> list[str]:
    """The rooms with an Echo connected right now."""
    return _request(config, directory, "/audio/announce/rooms", None)["rooms"]


def announce(
    config: AnnounceConfig, directory: Path, room: str, texts: list[str], speaker: str
) -> list[str]:
    """Queues the texts as ONE announcement for the room ("*": every room, "@group": a group), with
    a pause between them and the signal tones around the whole; `speaker` (an agent's name) is
    what AIfred records it under. Returns the rooms it went to, once AIfred has made the first
    sentence of speech and queued it, not once it has been played."""
    body = {"room": room, "texts": texts, "speaker": speaker}
    return _request(config, directory, "/audio/announce", body)["rooms"]
