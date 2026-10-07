"""Loading and validating the Agent-Orc configuration file."""

import os
from importlib.resources import files
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

NAME_PLACEHOLDER = "{name}"
CONVERSATION_PLACEHOLDER = "{conversation}"
# The model chosen at start, for profiles that offer a choice (AgentProfile.models).
MODEL_PLACEHOLDER = "{model}"
# The folder's reasoning effort, in a profile's environment (AgentProfile.env).
EFFORT_PLACEHOLDER = "{effort}"
CONFIG_FILE_NAME = "config.yaml"
CREDENTIALS_FILE_NAME = "credentials.json"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServerConfig(StrictModel):
    host: str
    port: int
    cookie_secure: bool


class AuthConfig(StrictModel):
    session_days: int
    max_failed_logins: int
    lockout_minutes: int


class FilesConfig(StrictModel):
    base_dir: Path
    name_pattern: str
    unlock_minutes: int
    max_edit_bytes: int

    @field_validator("base_dir")
    @classmethod
    def expand_home(cls, value: Path) -> Path:
        return value.expanduser()


class TerminalKey(StrictModel):
    label: str
    send: str | None = None
    modifier: Literal["ctrl", "alt"] | None = None
    # A text key (macro): Enter follows the text after the submit delay, as for the input field.
    submit: bool = False

    @model_validator(mode="after")
    def send_xor_modifier(self) -> Self:
        if (self.send is None) == (self.modifier is None):
            raise ValueError(f"key {self.label!r} needs exactly one of send or modifier")
        if self.submit and self.send is None:
            raise ValueError(f"key {self.label!r} submits, so it needs a text to send")
        return self


class TerminalConfig(StrictModel):
    keys: list[list[TerminalKey]]
    submit_delay_ms: int
    text_history_lines: int
    # A long text goes into the agent in pieces of this many characters, a pause apart: Claude
    # Code takes one big chunk (about 800 characters on) for a paste and wraps it as pasted
    # content, which the agent then may refuse to follow.
    type_chunk_chars: int = 200
    type_chunk_delay_ms: int = 30


class HandoverConfig(StrictModel):
    """When an agent's context is large enough to advise a handover to a fresh session."""

    threshold_percent: int
    # Idle this long, the prompt cache has expired: the next message reads it all in again.
    cold_after_minutes: int
    # Typed into the agent to ask for its handover.
    prompt: str


class LimitResumeConfig(StrictModel):
    """Resuming an agent stopped by its usage limit once the limit is reset (schedule.py)."""

    # Typed into the agent after the reset.
    prompt: str
    # Waited after the announced reset, in case the limit lifts a little later.
    delay_seconds: int


class PushConfig(StrictModel):
    """Notifications on the user's devices when an agent finished or waits (see push.py)."""

    # Contact the push services may write to (VAPID "sub"): a mailto: or https: URL.
    contact: str
    # An undelivered message is dropped after this long; an old "finished" is worth nothing.
    time_to_live_seconds: int
    # A hook waits this long at most for each device, so a slow push service cannot hold up
    # the agent.
    timeout_seconds: float


class DictationConfig(StrictModel):
    """Speech input, transcribed by a Whisper service (see dictation.py)."""

    # Without a Whisper service the browser's own speech recognition is used, where it has one.
    whisper_url: str | None
    language: str
    timeout_seconds: int


class AnnounceConfig(StrictModel):
    """Answers read aloud on an Echo Dot, through AIfred's announce endpoint (see announce.py)."""

    # AIfred's API, e.g. http://127.0.0.1:8002/api
    url: str
    # A file in the config directory holding the bearer token; readable by the user only, so the
    # token is not in this file (it may be shared) and a new one needs no restart.
    token_file: str
    # AIfred refuses a longer text; the answer is cut at a sentence beforehand.
    max_chars: int
    timeout_seconds: int
    # What the speech settings call this output (the device or devices behind it).
    label: str


class VoiceConfig(StrictModel):
    """Speaking to an agent on the Echo Dot: what AIfred hands over after the wake word (see
    voice.py). The spoken lines are here, not in the code."""

    # A file in the config directory holding the bearer token AIfred sends; readable by the user
    # only.
    token_file: str
    # With no agent named, the text goes to the one that answered last, if within this.
    window_minutes: int
    # A question nobody answers is forgotten after this.
    confirm_minutes: int
    # Of what was said, this many of the newest requests stay (with their recordings); what was
    # said to an agent that is stopped goes with it.
    keep_entries: int
    # How well a spoken name must match an agent's folder name (0 to 1).
    name_similarity: float
    yes_words: list[str]
    no_words: list[str]
    # Drops what was said instead of asking for another agent.
    cancel_words: list[str]
    # Spoken to the room; {agent} is the agent's name.
    ask_line: str
    sent_line: str
    # Said instead when the agent is still at work: what was said waits in its input.
    sent_busy_line: str
    discarded_line: str
    which_agent_line: str
    # Nobody was named and no agent answered within the window.
    no_agent_line: str
    # Spoken when an agent that was spoken to has finished without a paragraph for listening.
    no_summary_line: str


class TmuxConfig(StrictModel):
    socket_name: str


class LiveEffortConfig(StrictModel):
    """How a running agent switches its reasoning in place, without a restart."""

    # Typed into the agent; {level} becomes the effort level.
    command: str
    # Typed when ultracode changes; {state} becomes "on" or "off".
    ultracode_command: str
    # A file the agent rewrites when its effort is set this way (Claude: the user's own
    # settings); Agent-Orc puts it back as it was, so nothing changes outside the session.
    protected_file: str


class LiveModelConfig(StrictModel):
    """How a running agent switches its model in place, without a restart."""

    # Typed into the agent; {model} becomes the chosen model.
    command: str
    # Text on the agent's screen that asks to confirm the switch (Claude: a warning that the
    # conversation is cached for the current model, once it has some content); Enter answers
    # it with its default, the switch. Without it nothing is confirmed.
    confirm: str | None = None
    # A file the agent rewrites when its model is set this way (Claude: the user's own settings,
    # which then name the model as default for new sessions); Agent-Orc puts it back as it was.
    protected_file: str


class EffortConfig(StrictModel):
    """Reasoning effort the user may pick, and the one a folder has until the user picks."""

    levels: list[str]
    # The level of a folder without one of its own.
    default: str
    # Where the choice is kept (see effort.py); "claude_project": the folder's Claude settings.
    store: Literal["claude_project"]
    # The agent also offers ultracode (workflow orchestration), switched on next to the effort.
    ultracode: bool = False
    # Without it, a running agent is restarted (resumed) to take a new reasoning.
    live: LiveEffortConfig | None = None
    # For profiles with a choice of models: prints the levels the chosen model ({model}) takes,
    # space-separated; nothing means the model gets no level at all (no slider).
    levels_command: list[str] | None = None

    @model_validator(mode="after")
    def default_is_offered(self) -> "EffortConfig":
        if self.default not in self.levels:
            raise ValueError(f"effort default {self.default!r} is not one of {self.levels}")
        return self


class PermissionConfig(StrictModel):
    """Permission modes a session may start in, and the one it starts in until the user picks."""

    modes: list[str]
    default: str
    # Where the choice is kept (see effort.py); "claude_project": the folder's Claude settings.
    store: Literal["claude_project"]

    @model_validator(mode="after")
    def default_is_offered(self) -> "PermissionConfig":
        if self.default not in self.modes:
            raise ValueError(f"permission default {self.default!r} is not one of {self.modes}")
        return self


class ConversationsConfig(StrictModel):
    """Earlier conversations in a folder that can be resumed one by one."""

    # Where they are listed from (see history.py).
    source: Literal["claude"]
    # Command resuming one of them; contains the placeholder {conversation}.
    resume: list[str]


class AgentProfile(StrictModel):
    label: str
    start: list[str]
    resume: list[str]
    conversations: ConversationsConfig | None = None
    effort: EffortConfig | None = None
    permission: PermissionConfig | None = None
    # Mark the folder as trusted before starting, so the agent does not stop at a prompt.
    trust: Literal["claude"] | None = None
    # Where the account's usage limits come from (see context.QUOTA_SOURCES).
    quota: Literal["claude"] | None = None
    # A plain terminal, no agent: it may run in a folder next to that folder's agent.
    terminal: bool = False
    # Prints the models to choose from at start, one per line; the choice fills {model}. A tab
    # may follow the name, then a note shown beside it (e.g. until when the model is free).
    models: list[str] | None = None
    # Without it, a running agent is restarted (resumed) to take another model.
    model_live: LiveModelConfig | None = None
    # Environment of the agent; {effort} is the folder's level (left out when it has none).
    env: dict[str, str] = {}
    # Shown in the start dialog when this profile is chosen (e.g. what to stop first).
    hint: str | None = None


class Config(StrictModel):
    server: ServerConfig
    auth: AuthConfig
    files: FilesConfig
    terminal: TerminalConfig
    push: PushConfig
    handover: HandoverConfig
    limit_resume: LimitResumeConfig
    dictation: DictationConfig
    # Without it there is no Echo Dot to read answers on.
    announce: AnnounceConfig | None = None
    # Without it nobody can speak to an agent through the Echo; needs "announce" for its answers.
    voice: VoiceConfig | None = None
    tmux: TmuxConfig
    agents: dict[str, AgentProfile]

    @model_validator(mode="after")
    def voice_needs_announce(self) -> Self:
        if self.voice is not None and self.announce is None:
            raise ValueError("voice speaks its answers through announce, which is not configured")
        return self


def default_config_text() -> str:
    """Return the shipped default configuration, the template `agent-orc setup` fills in."""
    return files("agent_orc").joinpath("default_config.yaml").read_text(encoding="utf-8")


def config_dir() -> Path:
    """Agent-Orc's config directory, following the XDG base directory spec."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config_home) / "agent-orc"


def parse_config(text: str) -> Config:
    return Config.model_validate(yaml.safe_load(text))


def load_config(path: Path) -> Config:
    return parse_config(path.read_text(encoding="utf-8"))
