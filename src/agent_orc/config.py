"""Loading and validating the Agent-Orc configuration file."""

import os
from importlib.resources import files
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

NAME_PLACEHOLDER = "{name}"
CONVERSATION_PLACEHOLDER = "{conversation}"
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

    @model_validator(mode="after")
    def send_xor_modifier(self) -> Self:
        if (self.send is None) == (self.modifier is None):
            raise ValueError(f"key {self.label!r} needs exactly one of send or modifier")
        return self


class TerminalConfig(StrictModel):
    keys: list[list[TerminalKey]]
    submit_delay_ms: int
    text_history_lines: int


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


class TmuxConfig(StrictModel):
    socket_name: str


class EffortConfig(StrictModel):
    """Reasoning effort the user may pick; without a pick the agent's own default applies."""

    levels: list[str]
    # Where the choice is kept (see effort.py); "claude_project": the folder's Claude settings.
    store: Literal["claude_project"]
    # The agent also offers ultracode (workflow orchestration), switched on next to the effort.
    ultracode: bool = False


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


class Config(StrictModel):
    server: ServerConfig
    auth: AuthConfig
    files: FilesConfig
    terminal: TerminalConfig
    push: PushConfig
    dictation: DictationConfig
    tmux: TmuxConfig
    agents: dict[str, AgentProfile]


def default_config_text() -> str:
    """Return the shipped default configuration, used as template by `agent-orc init`."""
    return files("agent_orc").joinpath("default_config.yaml").read_text(encoding="utf-8")


def config_dir() -> Path:
    """Agent-Orc's config directory, following the XDG base directory spec."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config_home) / "agent-orc"


def parse_config(text: str) -> Config:
    return Config.model_validate(yaml.safe_load(text))


def load_config(path: Path) -> Config:
    return parse_config(path.read_text(encoding="utf-8"))
