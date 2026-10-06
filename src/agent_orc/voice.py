"""Speaking to an agent through an Echo Dot: AIfred hands over what was said after the wake word
("Hey Orc, ..."); Agent-Orc finds the agent, has the Echo ask back whom it understood, and types
the text into that agent only after a spoken yes.

The decision is made here without a model: words in, a decision out. Speaking and typing are
done by the caller.
"""

import difflib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from agent_orc.config import VoiceConfig
from agent_orc.phonetics import cologne
from agent_orc.state import state_dir, write_atomically

MAX_NAME_WORDS = 4
_NOT_LETTERS = re.compile(r"[\W_]+")
# The parts of a folder name: words, camel case humps, numbers ("FreeEchoDot2": Free Echo Dot 2).
# Agents end an answer with a paragraph for listening that starts with this (the same marker the
# web app reads aloud: LISTEN_MARKER in speechText.ts).
LISTEN_MARKER = "🔊"
_NAME_PART = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


@dataclass(frozen=True)
class VoiceAgent:
    id: str
    # What the user calls it: the folder's name.
    name: str
    # Unix time of its last answer; None when it has not answered yet.
    last_spoke: float | None


class Action(Enum):
    ASK = "asked"
    SEND = "sent"
    DISCARD = "discarded"
    # After a no: the text is kept, the agent is asked for again.
    WHICH_AGENT = "which_agent"
    # No agent named, and none answered lately.
    NO_AGENT = "no_agent"


@dataclass(frozen=True)
class Decision:
    action: Action
    agent: VoiceAgent | None = None
    text: str = ""


@dataclass(frozen=True)
class _Pending:
    # None: the user said no and has not named another agent yet.
    agent: VoiceAgent | None
    text: str
    expires: float


def _squash(text: str) -> str:
    return _NOT_LETTERS.sub("", text.casefold())


def _similarity(spoken: str, spoken_words: int, name: str) -> float:
    """How alike a spoken name and an agent's name are: by letters (a typo) or by sound (another
    spelling), whichever fits better. The sound only counts for as many words as the name has,
    since it drops vowels and would otherwise take a few small words of an order for a name."""
    by_letters = difflib.SequenceMatcher(None, _squash(spoken), _squash(name)).ratio()
    if spoken_words > len(_NAME_PART.findall(name)):
        return by_letters
    by_sound = difflib.SequenceMatcher(None, cologne(spoken), cologne(name)).ratio()
    return max(by_letters, by_sound)


def _first_word(text: str) -> str:
    words = _NOT_LETTERS.sub(" ", text.casefold()).split()
    return words[0] if words else ""


class VoiceRouter:
    """Remembers per room what waits for a yes."""

    def __init__(self, config: VoiceConfig) -> None:
        self._config = config
        self._pending: dict[str, _Pending] = {}

    def handle(self, room: str, text: str, agents: list[VoiceAgent], now: float) -> Decision:
        pending = self._pending.pop(room, None)
        if pending is not None and pending.expires > now:
            answered = self._answer(room, pending, text, agents, now)
            if answered is not None:
                return answered
        # Anything else is a new request; nothing was sent for the old one.
        return self._ask(room, text, agents, now)

    def _answer(
        self, room: str, pending: _Pending, text: str, agents: list[VoiceAgent], now: float
    ) -> Decision | None:
        """What the user said to an open question; None if it was no answer to it."""
        word = _first_word(text)
        if word in self._config.cancel_words:
            return Decision(Action.DISCARD, pending.agent, pending.text)
        if pending.agent is not None:
            if word in self._config.yes_words:
                return Decision(Action.SEND, pending.agent, pending.text)
            if word in self._config.no_words:
                self._pending[room] = _Pending(None, pending.text, self._expiry(now))
                return Decision(Action.WHICH_AGENT, text=pending.text)
            return None
        if word in self._config.no_words:
            return Decision(Action.DISCARD, text=pending.text)
        named = self._named_alone(text, agents)
        return None if named is None else self._confirm(room, named, pending.text, now)

    def _ask(self, room: str, text: str, agents: list[VoiceAgent], now: float) -> Decision:
        named, request = self._address(text, agents)
        agent = named or self._last_spoken(agents, now)
        if agent is None:
            return Decision(Action.NO_AGENT, text=text)
        return self._confirm(room, agent, request, now)

    def _confirm(self, room: str, agent: VoiceAgent, text: str, now: float) -> Decision:
        self._pending[room] = _Pending(agent, text, self._expiry(now))
        return Decision(Action.ASK, agent, text)

    def _expiry(self, now: float) -> float:
        return now + self._config.confirm_minutes * 60

    def _named_alone(self, text: str, agents: list[VoiceAgent]) -> VoiceAgent | None:
        """The agent when the whole sentence is just its name."""
        count = len(text.split())
        similarity, agent = self._best_match(text, count, agents)
        return agent if similarity >= self._config.name_similarity else None

    def _best_match(
        self, spoken: str, count: int, agents: list[VoiceAgent]
    ) -> tuple[float, VoiceAgent | None]:
        scored = [(_similarity(spoken, count, agent.name), agent) for agent in agents]
        return max(scored, key=lambda match: match[0], default=(0.0, None))

    def _address(self, text: str, agents: list[VoiceAgent]) -> tuple[VoiceAgent | None, str]:
        """The agent named at the start of the sentence and what is left after its name."""
        words = text.split()
        best: tuple[float, VoiceAgent | None, int] = (0.0, None, 0)
        for count in range(1, min(MAX_NAME_WORDS, len(words) - 1) + 1):
            similarity, agent = self._best_match(" ".join(words[:count]), count, agents)
            if similarity > best[0]:
                best = (similarity, agent, count)
        similarity, named, count = best
        if named is None or similarity < self._config.name_similarity:
            return None, text.strip()
        return named, " ".join(words[count:]).strip(" ,:;-")

    def _last_spoken(self, agents: list[VoiceAgent], now: float) -> VoiceAgent | None:
        """The agent that answered last, if that was within the window."""
        window = self._config.window_minutes * 60
        recent = [a for a in agents if a.last_spoke is not None and now - a.last_spoke <= window]
        return max(recent, key=lambda a: a.last_spoke or 0.0, default=None)


def listening_paragraph(answer: str) -> str | None:
    """The last paragraph for listening of an answer, without its marker."""
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", answer)]
    marked = [p for p in paragraphs if p.startswith(LISTEN_MARKER)]
    return marked[-1].removeprefix(LISTEN_MARKER).strip() if marked else None


def _reply_file(session_id: str) -> Path:
    return state_dir() / "voice-replies" / session_id


def expect_reply(session_id: str, room: str) -> None:
    """The agent got a request spoken in this room: its next answer is announced there. A file,
    since the hook that sees the answer is a process of its own."""
    write_atomically(_reply_file(session_id), room)


def take_reply_room(session_id: str) -> str | None:
    """The room the agent's answer goes to, once; None if no request was spoken to it."""
    path = _reply_file(session_id)
    if not path.is_file():
        return None
    room = path.read_text(encoding="utf-8")
    path.unlink()
    return room
