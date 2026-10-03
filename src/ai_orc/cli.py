"""Command line entry point: `ai-orc init | set-password | serve`."""

import argparse
import getpass
import json
import os
import sys
from importlib.resources import files
from pathlib import Path

import uvicorn

from ai_orc.api import create_app
from ai_orc.auth import load_credentials, new_credentials, save_credentials
from ai_orc.config import (
    CONFIG_FILE_NAME,
    CREDENTIALS_FILE_NAME,
    config_dir,
    default_config_text,
    load_config,
)
from ai_orc.context import status_line, store_activity, store_status
from ai_orc.sessions import SESSION_ENV


def init() -> None:
    path = config_dir() / CONFIG_FILE_NAME
    if path.exists():
        sys.exit(f"Config already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(default_config_text(), encoding="utf-8")
    print(f"Wrote {path}. Adapt it, then run `ai-orc set-password`.")


def set_password() -> None:
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    if not password:
        sys.exit("Password must not be empty.")
    path = config_dir() / CREDENTIALS_FILE_NAME
    save_credentials(path, new_credentials(password))
    print(f"Wrote {path}. All existing logins are now invalid.")


def serve() -> None:
    directory = config_dir()
    config = load_config(directory / CONFIG_FILE_NAME)
    credentials = load_credentials(directory / CREDENTIALS_FILE_NAME)
    static_dir = Path(str(files("ai_orc").joinpath("static")))
    if not (static_dir / "index.html").is_file():
        sys.exit(f"Frontend not built: no index.html in {static_dir} (run: npm run build)")
    app = create_app(config, credentials, static_dir=static_dir)
    # The standard asyncio loop, not uvloop: uvloop runs preexec_fn before setsid(), which
    # breaks claiming the terminal PTY (see terminal.py); the tests also run on asyncio.
    uvicorn.run(app, host=config.server.host, port=config.server.port, loop="asyncio")


def statusline() -> None:
    """Status line command for Claude Code: store the session status, print a short line."""
    status = json.load(sys.stdin)
    # Set by AI-Orc for every agent it starts; the command is only configured there.
    store_status(os.environ[SESSION_ENV], status)
    print(status_line(status))


def agent_busy() -> None:
    """Hook command (Claude: UserPromptSubmit): the agent starts working."""
    store_activity(os.environ[SESSION_ENV], busy=True)


def agent_idle() -> None:
    """Hook command (Claude: Stop): the agent finished its answer."""
    store_activity(os.environ[SESSION_ENV], busy=False)


COMMANDS = {
    "init": (init, "write the default config to ~/.config/ai-orc/"),
    "set-password": (set_password, "set the login password"),
    "serve": (serve, "run the web server"),
    "statusline": (statusline, "status line command for agent sessions (JSON on stdin)"),
    "agent-busy": (agent_busy, "hook command: the agent started working"),
    "agent-idle": (agent_idle, "hook command: the agent finished its answer"),
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai-orc", description="Agent orchestrator")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        subcommands.add_parser(name, help=help_text)
    arguments = parser.parse_args()
    COMMANDS[arguments.command][0]()
