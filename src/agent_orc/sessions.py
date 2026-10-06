"""Agent sessions, each one a tmux session on Agent-Orc's own tmux server."""

import builtins
import hashlib
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from agent_orc.config import (
    CONVERSATION_PLACEHOLDER,
    MODEL_PLACEHOLDER,
    NAME_PLACEHOLDER,
    AgentProfile,
)

# Every agent gets its session id in this environment variable, so helpers it runs
# (e.g. the status line command) know which session they belong to.
SESSION_ENV = "AGENT_ORC_SESSION"
PROFILE_OPTION = "@orc_profile"
PATH_OPTION = "@orc_path"
# The model chosen at start (profiles with a choice); a restart takes the same.
MODEL_OPTION = "@orc_model"
# Marks a folder's terminal apart from its agent in the session name.
TERMINAL_ID_SUFFIX = "-terminal"
FIELD_SEPARATOR = "\t"
LIST_FORMAT = FIELD_SEPARATOR.join(
    [
        "#{session_name}",
        "#{" + PROFILE_OPTION + "}",
        "#{" + PATH_OPTION + "}",
        "#{" + MODEL_OPTION + "}",
        "#{pane_dead}",
        "#{pane_dead_status}",
        "#{session_created}",
    ]
)
MILLISECONDS_PER_SECOND = 1000
# tmux reports a missing server on stderr; that state simply means "no sessions".
NO_SERVER_MARKERS = ("no server running", "error connecting")


class SessionError(RuntimeError):
    pass


class UnknownProfileError(SessionError):
    pass


class SessionAlreadyRunningError(SessionError):
    pass


class SessionNotFoundError(SessionError):
    pass


class MissingModelError(SessionError):
    """The command needs a model that was not chosen, e.g. a session started before the profile
    offered a choice."""


@dataclass(frozen=True)
class AgentSession:
    id: str
    profile: str
    path: Path
    running: bool
    exit_status: int | None
    # Unix time the tmux session was created.
    created: float
    # A plain terminal (profile setting), which may run next to the folder's agent.
    terminal: bool
    # The model chosen at start, for profiles that offer a choice; None otherwise.
    chosen_model: str | None


def session_id_for(path: Path, terminal: bool) -> str:
    """Readable, unique tmux session name for a folder's agent or its terminal.

    tmux forbids '.' and ':' in session names, and folder names alone are not
    unique across nested directories, hence the sanitized name plus a path hash.
    """
    readable = re.sub(r"[^A-Za-z0-9_-]", "_", path.name)
    digest = hashlib.sha1(str(path).encode()).hexdigest()[:6]
    return f"{readable}-{digest}{TERMINAL_ID_SUFFIX if terminal else ''}"


def exact_target(session_id: str) -> str:
    """tmux target matching exactly this session (no prefix match), valid for all commands."""
    return f"={session_id}:"


def build_command(arguments: list[str], name: str, model: str | None) -> list[str]:
    command = [argument.replace(NAME_PLACEHOLDER, name) for argument in arguments]
    if model is None:
        if any(MODEL_PLACEHOLDER in argument for argument in command):
            raise MissingModelError(name)
        return command
    return [argument.replace(MODEL_PLACEHOLDER, model) for argument in command]


def environment_options(env: dict[str, str]) -> list[str]:
    """tmux options setting the agent's environment."""
    return [option for name, value in env.items() for option in ("-e", f"{name}={value}")]


class SessionManager:
    def __init__(self, socket_name: str, agents: dict[str, AgentProfile]) -> None:
        self._socket_name = socket_name
        self._agents = agents

    def list(self) -> list[AgentSession]:
        result = self._tmux("list-sessions", "-F", LIST_FORMAT, check=False)
        if result.returncode != 0:
            if any(marker in result.stderr for marker in NO_SERVER_MARKERS):
                return []
            raise SessionError(result.stderr.strip())
        return [self._parse_line(line) for line in result.stdout.splitlines()]

    def find_by_path(self, path: Path, terminal: bool) -> AgentSession | None:
        """The folder's agent, or its terminal: at most one of each per folder."""
        return next((s for s in self.list() if s.path == path and s.terminal == terminal), None)

    def _is_terminal(self, profile_name: str) -> bool:
        profile = self._agents.get(profile_name)
        return profile is not None and profile.terminal

    def start(
        self,
        profile_name: str,
        path: Path,
        resume: bool,
        conversation: str | None = None,
        model: str | None = None,
        env: dict[str, str] | None = None,
    ) -> AgentSession:
        """Start an agent in `path`; at most one agent session exists per folder, and one
        terminal next to it.

        A session whose agent has already exited is started again in place, so it keeps its
        id (open terminals and workspace columns stay valid). `conversation` resumes that
        earlier conversation (the caller has checked that it exists); `resume` the last one.
        `model` fills {model} (profiles with a choice of models); `env` is set for the agent.
        """
        env = env or {}
        command = self._command(profile_name, path, resume, conversation, model)
        terminal = self._is_terminal(profile_name)
        existing = self.find_by_path(path, terminal)
        if existing is not None:
            if existing.running:
                raise SessionAlreadyRunningError(existing.id)
            return self._respawn(existing, profile_name, command, model, env)

        session_id = session_id_for(path, terminal)
        # One tmux invocation, so remain-on-exit is active before the agent can exit
        # and its exit status stays visible. The status bar would only repeat what the
        # app shows and costs a terminal line on small screens. Mouse mode turns wheel
        # and touch scrolling in the browser terminal into scrolling the agent's history.
        # set-clipboard on lets an agent's copy (OSC 52) through to the browser's clipboard,
        # focus-events on tells the agent whether its terminal has the focus (Claude asks).
        self._tmux(
            "start-server", ";",
            "set-option", "-g", "remain-on-exit", "on", ";",
            "set-option", "-g", "status", "off", ";",
            "set-option", "-g", "mouse", "on", ";",
            "set-option", "-g", "set-clipboard", "on", ";",
            "set-option", "-s", "focus-events", "on", ";",
            "new-session", "-d", "-s", session_id, "-c", str(path),
            "-e", f"{SESSION_ENV}={session_id}", *environment_options(env), *command, ";",
            "set-option", "-t", exact_target(session_id), PROFILE_OPTION, profile_name, ";",
            "set-option", "-t", exact_target(session_id), PATH_OPTION, str(path), ";",
            "set-option", "-t", exact_target(session_id), MODEL_OPTION, model or "",
        )  # fmt: skip
        session = self.find_by_path(path, terminal)
        if session is None:
            raise SessionError(f"tmux session {session_id} vanished right after start")
        return session

    def restart(self, session: AgentSession, env: dict[str, str]) -> AgentSession:
        """Resume a running agent in its own session (it reads some settings only at start),
        with the model it was started with."""
        command = self._command(session.profile, session.path, True, None, session.chosen_model)
        return self._respawn(session, session.profile, command, session.chosen_model, env)

    def _command(
        self,
        profile_name: str,
        path: Path,
        resume: bool,
        conversation: str | None,
        model: str | None,
    ) -> builtins.list[str]:
        # builtins: inside this class, "list" is the method listing the sessions.
        profile = self._agents.get(profile_name)
        if profile is None:
            raise UnknownProfileError(profile_name)
        if conversation is not None and profile.conversations is not None:
            arguments = [
                argument.replace(CONVERSATION_PLACEHOLDER, conversation)
                for argument in profile.conversations.resume
            ]
        else:
            arguments = profile.resume if resume else profile.start
        return build_command(arguments, path.name, model)

    def _respawn(
        self,
        session: AgentSession,
        profile_name: str,
        command: builtins.list[str],
        model: str | None,
        env: dict[str, str],
    ) -> AgentSession:
        """Replace the session's process (ending a running one); attached terminals stay."""
        self._tmux(
            "respawn-pane", "-k", "-t", exact_target(session.id), "-c", str(session.path),
            "-e", f"{SESSION_ENV}={session.id}", *environment_options(env), *command, ";",
            "set-option", "-t", exact_target(session.id), MODEL_OPTION, model or "", ";",
            "set-option", "-t", exact_target(session.id), PROFILE_OPTION, profile_name,
        )  # fmt: skip
        respawned = self.find_by_path(session.path, self._is_terminal(profile_name))
        if respawned is None:
            raise SessionError(f"tmux session {session.id} vanished right after restart")
        return respawned

    def type_line(self, session_id: str, line: str, submit_delay_ms: int) -> None:
        """Type a line into the agent and submit it, as the user would."""
        self._tmux("send-keys", "-t", exact_target(session_id), "-l", line)
        # Enter separately, so the agent sees typed text plus submit, not one pasted block.
        time.sleep(submit_delay_ms / MILLISECONDS_PER_SECOND)
        self._tmux("send-keys", "-t", exact_target(session_id), "-l", "\r")

    def text(self, session_id: str, history_lines: int) -> str:
        """The session's screen and history as plain text; wrapped lines are joined again."""
        result = self._tmux(
            "capture-pane", "-p", "-J", "-S", f"-{history_lines}", "-t", exact_target(session_id),
            check=False,
        )  # fmt: skip
        if result.returncode != 0:
            raise SessionNotFoundError(session_id)
        return result.stdout.rstrip("\n")

    def stop(self, session_id: str) -> None:
        result = self._tmux("kill-session", "-t", exact_target(session_id), check=False)
        if result.returncode != 0:
            raise SessionNotFoundError(session_id)

    def _parse_line(self, line: str) -> AgentSession:
        session_id, profile, path, model, pane_dead, dead_status, created = line.split(
            FIELD_SEPARATOR
        )
        running = pane_dead != "1"
        return AgentSession(
            id=session_id,
            profile=profile,
            path=Path(path),
            running=running,
            # Empty when the process died from a signal, or tmux has not collected it yet.
            exit_status=int(dead_status) if dead_status else None,
            created=float(created),
            terminal=self._is_terminal(profile),
            chosen_model=model or None,
        )

    def _tmux(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["tmux", "-L", self._socket_name, *arguments],
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise SessionError(result.stderr.strip())
        return result
