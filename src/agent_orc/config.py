"""Loading and validating the Agent-Orc configuration file."""

import os
import re
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal, Self, get_args

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

NAME_PLACEHOLDER = "{name}"
CONVERSATION_PLACEHOLDER = "{conversation}"
# The model chosen at start, for profiles that offer a choice (AgentProfile.models).
MODEL_PLACEHOLDER = "{model}"
# The folder's reasoning effort, in a profile's environment (AgentProfile.env).
EFFORT_PLACEHOLDER = "{effort}"
# The suffix of a further agent in a folder, in a profile's environment (AgentProfile.env).
SUFFIX_PLACEHOLDER = "{suffix}"
# The agent's own settings file (AgentProfile.settings), in its command.
SETTINGS_PLACEHOLDER = "{settings}"
CONFIG_FILE_NAME = "config.yaml"
CREDENTIALS_FILE_NAME = "credentials.json"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServerConfig(StrictModel):
    """Where the server listens: on a port behind a login (host, port, cookie_secure), or on a
    Unix socket without one (socket). The socket is for a machine that another Agent-Orc
    controls through an SSH tunnel: it is reachable by whoever may enter the socket's folder (the
    folder is the user's alone, see `agent-orc serve`), and SSH is the login."""

    host: str | None = None
    port: int | None = None
    cookie_secure: bool | None = None
    socket: Path | None = None

    @field_validator("socket")
    @classmethod
    def expand_home(cls, value: Path | None) -> Path | None:
        return value.expanduser() if value is not None else None

    @model_validator(mode="after")
    def one_way_to_listen(self) -> Self:
        port_keys = (self.host, self.port, self.cookie_secure)
        if self.socket is not None:
            if any(key is not None for key in port_keys):
                raise ValueError("server: socket excludes host, port and cookie_secure")
        elif any(key is None for key in port_keys):
            raise ValueError("server: give host, port and cookie_secure, or a socket")
        return self


class AuthConfig(StrictModel):
    session_days: int
    max_failed_logins: int
    lockout_minutes: int


class FilesConfig(StrictModel):
    base_dir: Path
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
    # An agent with an exit command is asked to end by itself first and given this long for it
    # (seconds); what still runs after that is killed.
    exit_wait_seconds: int = 5


class HandoverConfig(StrictModel):
    """When an agent's context is full enough to advise a handover to a fresh session: just
    below the point where Claude Code compacts it by itself (see handover.py)."""

    threshold_percent: int
    # Typed into the agent to ask for its handover.
    prompt: str


class CacheConfig(StrictModel):
    """How an agent's prompt cache is shown on its card."""

    # This long before the cache expires, its age turns amber: the next message soon reads the
    # whole context in again.
    warning_minutes: int


class KeepWarmConfig(StrictModel):
    """Keeps a resting agent's prompt cache warm by typing a tiny prompt shortly before the cache
    expires (see keepwarm.py). Each answer that reads the cache starts its window anew."""

    # Typed into the agent; it should answer with next to nothing.
    prompt: str
    # This long before the cache expires, the prompt is typed. It must be shorter than the
    # cache's window, or the agent would be asked again and again.
    lead_minutes: int
    # Prompts in a row during one rest; then the agent is left to go cold. The user's next input
    # starts the count anew.
    max_pings: int


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
    """Speech input, transcribed by an STT-Suite service (see dictation.py)."""

    # Without an STT-Suite service the browser's own speech recognition is used, where it has one.
    stt_url: str | None
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


class TtsSuiteConfig(StrictModel):
    """Answers read aloud by a TTS-Suite service (see speech_service.py)."""

    # The service's address, e.g. http://127.0.0.1:5090
    url: str
    # A file in the config directory holding the bearer token; only needed when the service wants
    # one for speaking (it does when it listens on a network). Readable by the user only.
    token_file: str | None = None
    timeout_seconds: int
    # What the speech settings call this output.
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
    # Of what was said, this many of the newest requests stay (with their recordings). A stopped
    # agent's recordings go with it; the lines stay, to measure the recognition by.
    keep_entries: int
    # Recordings older than this many days go; the lines stay.
    recording_days: int
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


class PeersConfig(StrictModel):
    """Reading along in AI-Connect and writing to its agents as the user, through its program for
    JSON lines (see peers.py)."""

    # Starts that program; "observe" or "send" and their arguments follow.
    command: list[str]
    # Where the command runs (AI-Connect's folder).
    directory: Path
    # Messages of this many past hours are shown when the page opens, at most `limit` of them.
    hours: float
    limit: int
    # The agents see what is written here as coming from User:<user_name>.
    user_name: str

    @field_validator("directory")
    @classmethod
    def expand_home(cls, value: Path) -> Path:
        return value.expanduser()


HOST_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


class HostConfig(StrictModel):
    """Another machine whose Agent-Orc this one reaches through an SSH tunnel (see hosts.py)."""

    # The arguments of ssh: its options and the destination, e.g. ["-p", "2222", "mp@10.0.0.2"].
    # It must log in without asking (a key).
    ssh: list[str]
    # That Agent-Orc's socket on the machine (its server.socket), spelled out: ssh does not
    # expand "~".
    socket: str


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
    """Reasoning effort the user may pick, and the one an agent has until the user picks."""

    levels: list[str]
    # The level of an agent without one of its own.
    default: str
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
    # Keeping the prompt cache warm of agents that rest; without it the profile has no such thing
    # (the cache of other services than Anthropic's lives by other rules).
    keep_warm: KeepWarmConfig | None = None
    # A plain terminal, no agent: it may run in a folder next to that folder's agent.
    terminal: bool = False
    # Prints the models to choose from at start, one per line; the choice fills {model}. A tab
    # may follow the name, then a note shown beside it; the note `free_until=<YYYY-MM-DD>` is the
    # last day the model is free, which the interface words in its own language.
    models: list[str] | None = None
    # Without it, a running agent is restarted (resumed) to take another model.
    model_live: LiveModelConfig | None = None
    # Typed into an idle agent to empty its context, without a restart (Claude: /clear).
    clear_command: str | None = None
    # Typed into an idle agent to shrink its context to a summary (Claude: /compact).
    compact_command: str | None = None
    # Typed into a running agent to end it by itself before it is stopped or restarted (Claude:
    # /exit): only then does Claude Code close its Remote Control session in the Claude app, a
    # killed one stays there as an offline entry until it is archived by hand.
    exit_command: str | None = None
    # Environment of the agent; {effort} is its level, {suffix} that of a further agent in the
    # folder (an entry is left out when its placeholder has no value).
    env: dict[str, str] = {}
    # Claude's settings (status line, hooks) for the agent's own settings file, which also carries
    # its effort, ultracode and permission mode (see effort.py); its path fills {settings}.
    settings: dict[str, Any] | None = None
    # Shown in the start dialog when this profile is chosen (e.g. what to stop first).
    hint: str | None = None

    @model_validator(mode="after")
    def choices_reach_the_agent(self) -> Self:
        if (self.effort is not None or self.permission is not None) and self.settings is None:
            raise ValueError("effort and permission reach the agent only through its settings")
        return self


# Claude Code's levels of effort, from the lowest; a model takes only some of them.
Level = Literal["low", "medium", "high", "xhigh", "max"]
LEVELS: tuple[str, ...] = get_args(Level)
# The two variables Claude Code reads a key from.
KeyVariable = Literal["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]
KEY_VARIABLES: tuple[str, ...] = get_args(KeyVariable)


class BackendModelConfig(StrictModel):
    """What is known about a model that a backend offers."""

    # The levels the model takes, from the lowest up; without them no level is passed on and the
    # model's own default holds.
    levels: list[Level] | None = None
    # The last day its quota is free. Afterwards it is not offered, as it would be billed.
    free_until: date | None = None

    @field_validator("levels")
    @classmethod
    def levels_rise(cls, levels: list[Level] | None) -> list[Level] | None:
        if levels is not None and levels != sorted(set(levels), key=LEVELS.index):
            raise ValueError(f"levels go from the lowest up, each once ({', '.join(LEVELS)})")
        return levels


class BackendConfig(StrictModel):
    """A service that Claude Code can run on instead of Anthropic's: models on a local server
    (llama-swap, vLLM) or in a cloud (Qwen on DashScope). Used by `agent-orc backend`."""

    label: str
    # Where the models are served; the first address that answers is used.
    base_urls: list[str]
    # What follows the address for Claude's own API (Anthropic's Messages API).
    anthropic_path: str = ""
    # Where the server lists its models (OpenAI style).
    models_path: str = "/v1/models"
    # The variable Claude Code reads the key from, and where the key comes from: a value (local
    # servers take any), a file (kept readable for you alone) or an environment variable.
    key_variable: KeyVariable = "ANTHROPIC_AUTH_TOKEN"
    key: str | None = None
    key_file: Path | None = None
    key_env: str | None = None
    # The models on offer, name (a shell pattern is allowed) to what is known about them. Only
    # these are listed and chosen from.
    models: dict[str, BackendModelConfig]
    # The model for Claude Code's background requests (titles, summaries); without it the chosen
    # model does them. On a server that swaps models in and out, never name another one here.
    background_model: str | None = None
    # Where the server tells the context length of a model (max_model_len); {model} is the model.
    # Claude Code does not know the models and assumes 200k.
    context_path: str | None = None
    # A command run before Claude Code starts, e.g. to free graphics cards; {base_url} and {model}
    # are filled in. A failure is reported and the start goes on.
    before_start: list[str] | None = None
    # How long Claude Code waits for an answer of the server.
    api_timeout_ms: int | None = None

    @model_validator(mode="after")
    def one_place_for_the_key(self) -> Self:
        given = [source for source in (self.key, self.key_file, self.key_env) if source is not None]
        if len(given) != 1:
            raise ValueError("give the key as exactly one of key, key_file and key_env")
        return self


class Config(StrictModel):
    server: ServerConfig
    auth: AuthConfig
    files: FilesConfig
    terminal: TerminalConfig
    push: PushConfig
    handover: HandoverConfig
    cache: CacheConfig
    limit_resume: LimitResumeConfig
    dictation: DictationConfig
    # Without it there is no Echo Dot to read answers on.
    announce: AnnounceConfig | None = None
    # Without it no TTS-Suite service reads answers aloud (the browser's voices remain).
    tts_suite: TtsSuiteConfig | None = None
    # Without it nobody can speak to an agent through the Echo; needs "announce" for its answers.
    voice: VoiceConfig | None = None
    # Without it there is no AI-Connect to read along in.
    peers: PeersConfig | None = None
    # Without it there are no other machines. A name is part of the address: /hosts/<name>/.
    hosts: dict[str, HostConfig] | None = None
    # Without it Claude Code runs on Anthropic's service only; see `agent-orc backend`.
    backends: dict[str, BackendConfig] | None = None
    tmux: TmuxConfig
    agents: dict[str, AgentProfile]

    @field_validator("hosts")
    @classmethod
    def host_names_fit_an_address(
        cls, hosts: dict[str, HostConfig] | None
    ) -> dict[str, HostConfig] | None:
        for name in hosts or {}:
            if not HOST_NAME_PATTERN.fullmatch(name):
                raise ValueError(f"host name {name!r}: letters, digits, - and _ only")
        return hosts

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
