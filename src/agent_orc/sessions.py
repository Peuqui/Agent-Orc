"""Agent sessions, each one a tmux session on Agent-Orc's own tmux server."""

import builtins
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agent_orc.config import CONVERSATION_PLACEHOLDER, NAME_PLACEHOLDER, AgentProfile

# Every agent gets its session id in this environment variable, so helpers it runs
# (e.g. the status line command) know which session they belong to.
SESSION_ENV = "AGENT_ORC_SESSION"
PROFILE_OPTION = "@orc_profile"
PATH_OPTION = "@orc_path"
FIELD_SEPARATOR = "\t"
LIST_FORMAT = FIELD_SEPARATOR.join(
    [
        "#{session_name}",
        "#{" + PROFILE_OPTION + "}",
        "#{" + PATH_OPTION + "}",
        "#{pane_dead}",
        "#{pane_dead_status}",
        "#{session_created}",
    ]
)
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


@dataclass(frozen=True)
class AgentSession:
    id: str
    profile: str
    path: Path
    running: bool
    exit_status: int | None
    # Unix time the tmux session was created.
    created: float


def session_id_for(path: Path) -> str:
    """Readable, unique tmux session name for a folder.

    tmux forbids '.' and ':' in session names, and folder names alone are not
    unique across nested directories, hence the sanitized name plus a path hash.
    """
    readable = re.sub(r"[^A-Za-z0-9_-]", "_", path.name)
    digest = hashlib.sha1(str(path).encode()).hexdigest()[:6]
    return f"{readable}-{digest}"


def exact_target(session_id: str) -> str:
    """tmux target matching exactly this session (no prefix match), valid for all commands."""
    return f"={session_id}:"


def build_command(arguments: list[str], name: str) -> list[str]:
    return [argument.replace(NAME_PLACEHOLDER, name) for argument in arguments]


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

    def find_by_path(self, path: Path) -> AgentSession | None:
        return next((s for s in self.list() if s.path == path), None)

    def start(
        self, profile_name: str, path: Path, resume: bool, conversation: str | None = None
    ) -> AgentSession:
        """Start an agent in `path`; at most one agent session exists per folder.

        A session whose agent has already exited is started again in place, so it keeps its
        id (open terminals and workspace columns stay valid). `conversation` resumes that
        earlier conversation (the caller has checked that it exists); `resume` the last one.
        """
        command = self._command(profile_name, path, resume, conversation)
        existing = self.find_by_path(path)
        if existing is not None:
            if existing.running:
                raise SessionAlreadyRunningError(existing.id)
            return self._respawn(existing, profile_name, command)

        session_id = session_id_for(path)
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
            "-e", f"{SESSION_ENV}={session_id}", *command, ";",
            "set-option", "-t", exact_target(session_id), PROFILE_OPTION, profile_name, ";",
            "set-option", "-t", exact_target(session_id), PATH_OPTION, str(path),
        )  # fmt: skip
        session = self.find_by_path(path)
        if session is None:
            raise SessionError(f"tmux session {session_id} vanished right after start")
        return session

    def restart(self, session: AgentSession) -> AgentSession:
        """Resume a running agent in its own session (it reads some settings only at start)."""
        command = self._command(session.profile, session.path, resume=True, conversation=None)
        return self._respawn(session, session.profile, command)

    def _command(
        self, profile_name: str, path: Path, resume: bool, conversation: str | None
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
        return build_command(arguments, path.name)

    def _respawn(
        self, session: AgentSession, profile_name: str, command: builtins.list[str]
    ) -> AgentSession:
        """Replace the session's process (ending a running one); attached terminals stay."""
        self._tmux(
            "respawn-pane", "-k", "-t", exact_target(session.id), "-c", str(session.path),
            "-e", f"{SESSION_ENV}={session.id}", *command, ";",
            "set-option", "-t", exact_target(session.id), PROFILE_OPTION, profile_name,
        )  # fmt: skip
        respawned = self.find_by_path(session.path)
        if respawned is None:
            raise SessionError(f"tmux session {session.id} vanished right after restart")
        return respawned

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
        session_id, profile, path, pane_dead, dead_status, created = line.split(FIELD_SEPARATOR)
        running = pane_dead != "1"
        return AgentSession(
            id=session_id,
            profile=profile,
            path=Path(path),
            running=running,
            # Empty when the process died from a signal, or tmux has not collected it yet.
            exit_status=int(dead_status) if dead_status else None,
            created=float(created),
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
