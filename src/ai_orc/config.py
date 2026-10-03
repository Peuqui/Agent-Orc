"""Loading and validating the AI-Orc configuration file."""

import os
from importlib.resources import files
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

NAME_PLACEHOLDER = "{name}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TmuxConfig(StrictModel):
    socket_name: str


class AgentProfile(StrictModel):
    label: str
    start: list[str]
    resume: list[str]


class Config(StrictModel):
    tmux: TmuxConfig
    agents: dict[str, AgentProfile]


def default_config_text() -> str:
    """Return the shipped default configuration, used as template by `ai-orc init`."""
    return files("ai_orc").joinpath("default_config.yaml").read_text(encoding="utf-8")


def user_config_path() -> Path:
    """Location of the user's config file, following the XDG base directory spec."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config_home) / "ai-orc" / "config.yaml"


def parse_config(text: str) -> Config:
    return Config.model_validate(yaml.safe_load(text))


def load_config(path: Path) -> Config:
    return parse_config(path.read_text(encoding="utf-8"))
