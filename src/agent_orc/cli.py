"""Command line entry point: `agent-orc setup | set-password | serve` and the agents' hooks."""

import argparse
import asyncio
import getpass
import json
import os
import signal
import socket
import sys
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

import uvicorn

from agent_orc.announce import announce
from agent_orc.answers import read_turns
from agent_orc.api import create_app
from agent_orc.approvals import (
    close_answered,
    close_request,
    close_session_requests,
    hook_answer,
    open_request,
    wait_for_decision,
)
from agent_orc.auth import load_credentials, new_credentials, save_credentials
from agent_orc.backends import (
    BACKEND_VARIABLE,
    EFFORT_VARIABLE,
    BackendError,
    backend_named,
    choose_model,
    exec_claude,
    free_cards_message,
    levels_of,
    models_lines,
    prepare_launch,
    split_effort,
)
from agent_orc.config import (
    CONFIG_FILE_NAME,
    CREDENTIALS_FILE_NAME,
    config_dir,
    load_config,
)
from agent_orc.context import (
    begin_compaction,
    end_compaction,
    status_line,
    store_activity,
    store_status,
)
from agent_orc.handover import SESSION_START_SUBCOMMAND, take_resume_request
from agent_orc.listen import SocketFolderError, prepare_socket
from agent_orc.push import agent_message, send_to_all
from agent_orc.schedule import mark_limited
from agent_orc.sessions import SESSION_ENV
from agent_orc.setup import run_setup
from agent_orc.voice import answered_reply, expected_reply, listening_paragraph, took_in


def set_password() -> None:
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    if not password:
        sys.exit("Password must not be empty.")
    path = config_dir() / CREDENTIALS_FILE_NAME
    save_credentials(path, new_credentials(password))
    print(f"Wrote {path}. All existing logins are now invalid.")


# How long a stop waits for connections that do not end by themselves. The live streams end as
# the stop begins (Server), and uvicorn closes the terminals' WebSockets itself; what is left (a
# download, a forwarded request) gets this long. Without a limit the stop hangs until systemd
# kills the service, and what the app cleans up as it ends (the tunnels to other machines) is
# not done.
SHUTDOWN_GRACE_SECONDS = 5


class Server(uvicorn.Server):
    """Tells the app's live streams to end as the stop begins: otherwise the stop waits for them
    in vain and cancels them, which uvicorn logs as an error for each."""

    def __init__(self, config: uvicorn.Config, stopping: asyncio.Event) -> None:
        super().__init__(config)
        self.stopping = stopping

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        self.stopping.set()
        await super().shutdown(sockets)


def serve() -> None:
    directory = config_dir()
    config = load_config(directory / CONFIG_FILE_NAME)
    socket = config.server.socket
    # On a socket nobody logs in: the folder's rights and SSH are the access control.
    credentials = None if socket else load_credentials(directory / CREDENTIALS_FILE_NAME)
    static_dir = Path(str(files("agent_orc").joinpath("static")))
    if not (static_dir / "index.html").is_file():
        sys.exit(f"Frontend not built: no index.html in {static_dir} (run: npm run build)")
    app = create_app(config, credentials, static_dir=static_dir)
    # The standard asyncio loop, not uvloop: uvloop runs preexec_fn before setsid(), which
    # breaks claiming the terminal PTY (see terminal.py); the tests also run on asyncio.
    if socket is not None:
        try:
            prepare_socket(socket)
        except SocketFolderError as error:
            sys.exit(str(error))
        where: dict[str, Any] = {"uds": str(socket)}
    else:
        assert config.server.host is not None and config.server.port is not None
        where = {"host": config.server.host, "port": config.server.port}
    server_config = uvicorn.Config(
        app, loop="asyncio", timeout_graceful_shutdown=SHUTDOWN_GRACE_SECONDS, **where
    )
    Server(server_config, app.state.stopping).run()


def statusline() -> None:
    """Status line command for Claude Code: store the session status, print a short line."""
    status = json.load(sys.stdin)
    # Set by Agent-Orc for every agent it starts; the command is only configured there.
    store_status(os.environ[SESSION_ENV], status)
    print(status_line(status))


def agent_busy() -> None:
    """Hook command (Claude: UserPromptSubmit): the agent starts working."""
    session_id = os.environ[SESSION_ENV]
    store_activity(session_id, busy=True)
    close_session_requests(session_id)


def agent_free_cards() -> None:
    """Hook command (Claude: UserPromptSubmit): GPU-Orc frees the graphics cards for the model of
    an agent on a backend (backends.py); what it did or what went wrong is shown to the user, and
    the input goes on whatever GPU-Orc answers."""
    if BACKEND_VARIABLE not in os.environ:
        return
    config = load_config(config_dir() / CONFIG_FILE_NAME)
    message = free_cards_message(config, os.environ)
    if message is not None:
        print(json.dumps({"systemMessage": message}))


def agent_session_start() -> None:
    """Hook command (Claude: SessionStart after /clear): a handover to a fresh session left the
    request to read the handover for this new conversation; it goes into the context before any
    turn runs, so it comes first."""
    prompt = take_resume_request(os.environ[SESSION_ENV])
    if prompt is not None:
        output = {"hookEventName": "SessionStart", "additionalContext": prompt}
        print(json.dumps({"hookSpecificOutput": output}))


def agent_compacting() -> None:
    """Hook command (Claude: PreCompact): the agent starts shrinking its context."""
    begin_compaction(os.environ[SESSION_ENV])


def agent_compacted() -> None:
    """Hook command (Claude: PostCompact): the agent has shrunk its context; nothing was
    answered, so the user's devices hear nothing."""
    end_compaction(os.environ[SESSION_ENV])


def agent_idle() -> None:
    """Hook command (Claude: Stop): the agent finished its answer; tells the user's devices."""
    hook = json.load(sys.stdin)
    session_id = os.environ[SESSION_ENV]
    store_activity(session_id, busy=False)
    close_session_requests(session_id)
    # Absent when the answer ended without text (e.g. interrupted).
    answer = hook.get("last_assistant_message") or ""
    _notify("done", hook, answer)
    _announce_voice_reply(hook, answer)


def agent_limited() -> None:
    """Hook command (Claude: StopFailure for rate_limit): the usage limit stopped the agent; the
    server plans its resume for when the limit is reset."""
    hook = json.load(sys.stdin)
    session_id = os.environ[SESSION_ENV]
    # StopFailure comes instead of Stop: the agent no longer works.
    store_activity(session_id, busy=False)
    close_session_requests(session_id)
    mark_limited(session_id)
    _notify("limited", hook, hook.get("last_assistant_message") or "")


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
        decision = wait_for_decision(request.id)
    finally:
        close_request(request.id)
    print(json.dumps(hook_answer(decision)))


def agent_tool_done() -> None:
    """Hook command (Claude: PostToolUse, PostToolUseFailure, PermissionDenied; async): a
    permission request for this call was answered, maybe in the terminal."""
    hook = json.load(sys.stdin)
    close_answered(os.environ[SESSION_ENV], hook["tool_name"], hook["tool_input"])


def _announce_voice_reply(hook: dict[str, Any], answer: str) -> None:
    """An agent spoken to on the Echo answers there, with its paragraph for listening, once the
    turn that took in the spoken request has ended (a request typed ahead into a busy agent is
    taken in by the turn that is still running, or by the next one)."""
    session_id = os.environ[SESSION_ENV]
    expected = expected_reply(session_id)
    if expected is None:
        return
    room, request = expected
    turns = read_turns(Path(hook["transcript_path"]), 1)
    if not turns or not took_in(turns[-1], request):
        return
    answered_reply(session_id)
    config = load_config(config_dir() / CONFIG_FILE_NAME)
    assert config.voice is not None and config.announce is not None
    agent = Path(hook["cwd"]).name
    text = listening_paragraph(answer) or config.voice.no_summary_line.format(agent=agent)
    announce(config.announce, config_dir(), room, [text], agent)


def _notify(kind: str, hook: dict[str, Any], text: str) -> None:
    config = load_config(config_dir() / CONFIG_FILE_NAME)
    message = agent_message(kind, os.environ[SESSION_ENV], Path(hook["cwd"]).name, text)
    send_to_all(message, config.push)


BACKEND_USAGE = (
    "usage: agent-orc backend models <backend> | levels <backend> <model>"
    " | run <backend> [<model>] [claude arguments]"
)


def run_backend(arguments: list[str]) -> None:
    """`agent-orc backend ...`: Claude Code on a backend other than Anthropic's (backends.py)."""
    config = load_config(config_dir() / CONFIG_FILE_NAME)
    try:
        match arguments:
            case ["models", name]:
                print("\n".join(models_lines(backend_named(config, name), date.today())))
            case ["levels", name, model]:
                print(" ".join(levels_of(backend_named(config, name), model)))
            case ["run", name, *rest]:
                backend = backend_named(config, name)
                if rest and not rest[0]:
                    raise BackendError("the model is empty: name one or leave it out")
                named = None if not rest or rest[0].startswith("-") else rest[0]
                wanted, claude_arguments = split_effort(
                    rest if named is None else rest[1:], os.environ.get(EFFORT_VARIABLE)
                )
                if named is None and not sys.stdin.isatty():
                    raise BackendError("name a model: this is not a terminal to choose in")
                model = named or choose_model(models_lines(backend, date.today()), date.today())
                launch = prepare_launch(
                    name, backend, model, wanted, claude_arguments, date.today()
                )
                exec_claude(launch)
            case _:
                sys.exit(BACKEND_USAGE)
    except BackendError as error:
        sys.exit(f"agent-orc backend: {error}")


COMMANDS = {
    "setup": (run_setup, "first-run setup: config and password in ~/.config/agent-orc/"),
    "set-password": (set_password, "change the login password"),
    "serve": (serve, "run the web server"),
    "statusline": (statusline, "status line command for agent sessions (JSON on stdin)"),
    "agent-busy": (agent_busy, "hook command: the agent started working"),
    "agent-idle": (agent_idle, "hook command: the agent finished its answer"),
    "agent-free-cards": (agent_free_cards, "hook command: free the graphics cards for the model"),
    SESSION_START_SUBCOMMAND: (
        agent_session_start,
        "hook command: a new conversation starts (the request after a handover)",
    ),
    "agent-compacting": (agent_compacting, "hook command: the agent starts shrinking its context"),
    "agent-compacted": (agent_compacted, "hook command: the agent has shrunk its context"),
    "agent-limited": (agent_limited, "hook command: the usage limit stopped the agent"),
    "agent-waiting": (agent_waiting, "hook command: the agent waits for the user"),
    "agent-tool-done": (agent_tool_done, "hook command: a tool call ran, failed or was denied"),
    "agent-permission": (agent_permission, "hook command: a permission request for the web app"),
}
BACKEND_HELP = (
    "start Claude Code on another backend (local models, DashScope); see backends in the config"
)


def main() -> None:
    # Its arguments go partly on to Claude Code, so argparse does not see them.
    if sys.argv[1:2] == ["backend"]:
        run_backend(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(prog="agent-orc", description="Agent orchestrator")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        subcommands.add_parser(name, help=help_text)
    subcommands.add_parser("backend", help=BACKEND_HELP)
    arguments = parser.parse_args()
    COMMANDS[arguments.command][0]()
