"""Loading and validating the AI-Orc configuration file."""

import os
from importlib.resources import files
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

NAME_PLACEHOLDER = "{name}"
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


class TmuxConfig(StrictModel):
    socket_name: str


class AgentProfile(StrictModel):
    label: str
    start: list[str]
    resume: list[str]


class Config(StrictModel):
    server: ServerConfig
    auth: AuthConfig
    files: FilesConfig
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
