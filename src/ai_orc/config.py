"""Loading and validating the AI-Orc configuration file."""

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


class TmuxConfig(StrictModel):
    socket_name: str


class EffortConfig(StrictModel):
    """Reasoning effort the user may pick; without a pick the agent's own default applies."""

    levels: list[str]
    # Where the choice is kept (see effort.py); "claude_project": the folder's Claude settings.
    store: Literal["claude_project"]


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
    # Mark the folder as trusted before starting, so the agent does not stop at a prompt.
    trust: Literal["claude"] | None = None


class Config(StrictModel):
    server: ServerConfig
    auth: AuthConfig
    files: FilesConfig
    terminal: TerminalConfig
    tmux: TmuxConfig
    agents: dict[str, AgentProfile]


def default_config_text() -> str:
    """Return the shipped default configuration, used as template by `ai-orc init`."""
    return files("ai_orc").joinpath("default_config.yaml").read_text(encoding="utf-8")


def config_dir() -> Path:
    """AI-Orc's config directory, following the XDG base directory spec."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config_home) / "ai-orc"


def parse_config(text: str) -> Config:
    return Config.model_validate(yaml.safe_load(text))


def load_config(path: Path) -> Config:
    return parse_config(path.read_text(encoding="utf-8"))
