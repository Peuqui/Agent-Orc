"""Command line entry point: `agent-orc setup | set-password | serve` and the agents' hooks."""

import argparse
import getpass
import json
import os
import signal
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

import uvicorn

from agent_orc.api import create_app
from agent_orc.approvals import close_request, hook_answer, open_request, wait_for_decision
from agent_orc.auth import load_credentials, new_credentials, save_credentials
from agent_orc.config import (
    CONFIG_FILE_NAME,
    CREDENTIALS_FILE_NAME,
    config_dir,
    load_config,
)
from agent_orc.context import status_line, store_activity, store_status
from agent_orc.push import agent_message, send_to_all
from agent_orc.sessions import SESSION_ENV
from agent_orc.setup import run_setup


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
    static_dir = Path(str(files("agent_orc").joinpath("static")))
    if not (static_dir / "index.html").is_file():
        sys.exit(f"Frontend not built: no index.html in {static_dir} (run: npm run build)")
    app = create_app(config, credentials, static_dir=static_dir)
    # The standard asyncio loop, not uvloop: uvloop runs preexec_fn before setsid(), which
    # breaks claiming the terminal PTY (see terminal.py); the tests also run on asyncio.
    uvicorn.run(app, host=config.server.host, port=config.server.port, loop="asyncio")


def statusline() -> None:
    """Status line command for Claude Code: store the session status, print a short line."""
    status = json.load(sys.stdin)
    # Set by Agent-Orc for every agent it starts; the command is only configured there.
    store_status(os.environ[SESSION_ENV], status)
    print(status_line(status))


def agent_busy() -> None:
    """Hook command (Claude: UserPromptSubmit): the agent starts working."""
    store_activity(os.environ[SESSION_ENV], busy=True)


def agent_idle() -> None:
    """Hook command (Claude: Stop): the agent finished its answer; tells the user's devices."""
    hook = json.load(sys.stdin)
    store_activity(os.environ[SESSION_ENV], busy=False)
    # Absent when the answer ended without text (e.g. interrupted).
    _notify("done", hook, hook.get("last_assistant_message") or "")


def agent_waiting() -> None:
    """Hook command (Claude: Notification): the agent waits for a permission or an answer."""
    hook = json.load(sys.stdin)
    _notify("waiting", hook, hook["message"])


def agent_permission() -> None:
    """Hook command (Claude: PermissionRequest): the user may answer in the web app too."""
    hook = json.load(sys.stdin)
    request = open_request(os.environ[SESSION_ENV], hook)
    # Claude ends the hook when the user answers in the terminal; the request goes along.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        allow = wait_for_decision(request.id)
    finally:
        close_request(request.id)
    print(json.dumps(hook_answer(allow)))


def _notify(kind: str, hook: dict[str, Any], text: str) -> None:
    config = load_config(config_dir() / CONFIG_FILE_NAME)
    message = agent_message(kind, os.environ[SESSION_ENV], Path(hook["cwd"]).name, text)
    send_to_all(message, config.push)


COMMANDS = {
    "setup": (run_setup, "first-run setup: config and password in ~/.config/agent-orc/"),
    "set-password": (set_password, "change the login password"),
    "serve": (serve, "run the web server"),
    "statusline": (statusline, "status line command for agent sessions (JSON on stdin)"),
    "agent-busy": (agent_busy, "hook command: the agent started working"),
    "agent-idle": (agent_idle, "hook command: the agent finished its answer"),
    "agent-waiting": (agent_waiting, "hook command: the agent waits for the user"),
    "agent-permission": (agent_permission, "hook command: a permission request for the web app"),
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="agent-orc", description="Agent orchestrator")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        subcommands.add_parser(name, help=help_text)
    arguments = parser.parse_args()
    COMMANDS[arguments.command][0]()
