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

from agent_orc.config import VoiceConfig
from agent_orc.phonetics import cologne

MAX_NAME_WORDS = 4
_NOT_LETTERS = re.compile(r"[\W_]+")
# The parts of a folder name: words, camel case humps, numbers ("FreeEchoDot2": Free Echo Dot 2).
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
    UNKNOWN_AGENT = "unknown_agent"


@dataclass(frozen=True)
class Decision:
    action: Action
    agent: VoiceAgent | None = None
    text: str = ""


@dataclass(frozen=True)
class _Pending:
    agent: VoiceAgent
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
            answer = _first_word(text)
            if answer in self._config.yes_words:
                return Decision(Action.SEND, pending.agent, pending.text)
            if answer in self._config.no_words:
                return Decision(Action.DISCARD, pending.agent, pending.text)
        # Anything else is a new request; nothing was sent for the old one.
        return self._ask(room, text, agents, now)

    def _ask(self, room: str, text: str, agents: list[VoiceAgent], now: float) -> Decision:
        named, request = self._address(text, agents)
        agent = named or self._last_spoken(agents, now)
        if agent is None:
            return Decision(Action.UNKNOWN_AGENT, text=text)
        expires = now + self._config.confirm_minutes * 60
        self._pending[room] = _Pending(agent, request, expires)
        return Decision(Action.ASK, agent, request)

    def _address(self, text: str, agents: list[VoiceAgent]) -> tuple[VoiceAgent | None, str]:
        """The agent named at the start of the sentence and what is left after its name."""
        words = text.split()
        best: tuple[float, VoiceAgent | None, int] = (0.0, None, 0)
        for count in range(1, min(MAX_NAME_WORDS, len(words) - 1) + 1):
            spoken = " ".join(words[:count])
            for agent in agents:
                similarity = _similarity(spoken, count, agent.name)
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
