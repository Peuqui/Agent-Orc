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
    TerminalConfig,
)

# Every agent gets its session id in this environment variable, so helpers it runs
# (e.g. the status line command) know which session they belong to.
SESSION_ENV = "AGENT_ORC_SESSION"
PROFILE_OPTION = "@orc_profile"
PATH_OPTION = "@orc_path"
# The model chosen at start (profiles with a choice); a restart takes the same.
MODEL_OPTION = "@orc_model"
# Sets a further agent in a folder apart from the first (empty for the first one).
SUFFIX_OPTION = "@orc_suffix"
# What a suffix may hold: it becomes part of the tmux session name (no '.' or ':') and of the
# agent's name elsewhere (e.g. its AI-Connect peer name), so it stays as typed in both.
SUFFIX_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
# Marks a folder's terminal apart from its agent in the session name.
TERMINAL_ID_SUFFIX = "-terminal"
FIELD_SEPARATOR = "\t"
LIST_FORMAT = FIELD_SEPARATOR.join(
    [
        "#{session_name}",
        "#{" + PROFILE_OPTION + "}",
        "#{" + PATH_OPTION + "}",
        "#{" + MODEL_OPTION + "}",
        "#{" + SUFFIX_OPTION + "}",
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


class InvalidSuffixError(SessionError):
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
    # Sets a further agent in the folder apart from the first; None for the first.
    suffix: str | None

    @property
    def name(self) -> str:
        return agent_name(self.path, self.suffix)


def agent_name(path: Path, suffix: str | None) -> str:
    """The agent's name: its folder's, with the suffix of a further agent in the folder."""
    return path.name if suffix is None else f"{path.name}-{suffix}"


def check_suffix(suffix: str | None) -> None:
    if suffix is not None and not SUFFIX_PATTERN.fullmatch(suffix):
        raise InvalidSuffixError(suffix)


def session_id_for(path: Path, terminal: bool, suffix: str | None) -> str:
    """Readable, unique tmux session name for a folder's agent or its terminal.

    tmux forbids '.' and ':' in session names, and folder names alone are not
    unique across nested directories, hence the sanitized name plus a path hash.
    """
    readable = re.sub(r"[^A-Za-z0-9_-]", "_", agent_name(path, suffix))
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


def text_pieces(text: str, size: int) -> list[str]:
    """The text cut into pieces of at most `size` characters (typed one after the other)."""
    return [text[start : start + size] for start in range(0, len(text), size)]


class SessionManager:
    def __init__(
        self, socket_name: str, agents: dict[str, AgentProfile], terminal: TerminalConfig
    ) -> None:
        self._socket_name = socket_name
        self._agents = agents
        self._terminal = terminal

    def list(self) -> list[AgentSession]:
        result = self._tmux("list-sessions", "-F", LIST_FORMAT, check=False)
        if result.returncode != 0:
            if any(marker in result.stderr for marker in NO_SERVER_MARKERS):
                return []
            raise SessionError(result.stderr.strip())
        return [self._parse_line(line) for line in result.stdout.splitlines()]

    def find(self, path: Path, terminal: bool, suffix: str | None) -> AgentSession | None:
        """The folder's agent with this suffix (None: the first one), or the folder's terminal."""
        return next(
            (
                s
                for s in self.list()
                if s.path == path and s.terminal == terminal and s.suffix == suffix
            ),
            None,
        )

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
        suffix: str | None = None,
    ) -> AgentSession:
        """Start an agent in `path`: the folder's first one, or a further one set apart by
        `suffix`; one terminal runs next to them.

        A session whose agent has already exited is started again in place, so it keeps its
        id (open terminals and workspace columns stay valid). `conversation` resumes that
        earlier conversation (the caller has checked that it exists); `resume` the last one.
        `model` fills {model} (profiles with a choice of models); `env` is set for the agent.
        """
        env = env or {}
        check_suffix(suffix)
        command = self._command(profile_name, path, suffix, resume, conversation, model)
        terminal = self._is_terminal(profile_name)
        existing = self.find(path, terminal, suffix)
        if existing is not None:
            if existing.running:
                raise SessionAlreadyRunningError(existing.id)
            return self._respawn(existing, profile_name, command, model, env)

        session_id = session_id_for(path, terminal, suffix)
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
            "set-option", "-t", exact_target(session_id), MODEL_OPTION, model or "", ";",
            "set-option", "-t", exact_target(session_id), SUFFIX_OPTION, suffix or "",
        )  # fmt: skip
        session = self.find(path, terminal, suffix)
        if session is None:
            raise SessionError(f"tmux session {session_id} vanished right after start")
        return session

    def restart(
        self,
        session: AgentSession,
        env: dict[str, str],
        conversation: str | None,
        model: str | None = None,
    ) -> AgentSession:
        """Resume a running agent in its own session (it reads some settings only at start),
        with its own `conversation` if known, and the model it was started with, or `model` if
        it has none stored."""
        chosen = session.chosen_model if model is None else model
        command = self._command(
            session.profile, session.path, session.suffix, True, conversation, chosen
        )
        return self._respawn(session, session.profile, command, chosen, env)

    def change_profile(
        self,
        session: AgentSession,
        profile_name: str,
        resume: bool,
        model: str | None,
        env: dict[str, str],
        conversation: str | None,
    ) -> AgentSession:
        """Replace the agent by another profile's in the same session (ending a running one;
        open terminals and workspace columns stay valid). `resume` continues its `conversation`
        (or the folder's last), which only a profile with the same conversations can do."""
        command = self._command(
            profile_name, session.path, session.suffix, resume, conversation, model
        )
        return self._respawn(session, profile_name, command, model, env)

    def _command(
        self,
        profile_name: str,
        path: Path,
        suffix: str | None,
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
            # The folder's last conversation belongs to its first agent: a further one only goes
            # on with its own (by id, above), so it starts anew without one.
            arguments = profile.resume if resume and suffix is None else profile.start
        return build_command(arguments, agent_name(path, suffix), model)

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
        respawned = self.find(session.path, self._is_terminal(profile_name), session.suffix)
        if respawned is None:
            raise SessionError(f"tmux session {session.id} vanished right after restart")
        return respawned

    def set_model(self, session_id: str, model: str) -> None:
        """Note the model a running agent now runs with (it was switched in place)."""
        self._tmux("set-option", "-t", exact_target(session_id), MODEL_OPTION, model)

    def type_line(self, session_id: str, line: str) -> None:
        """Type a line into the agent and submit it, as the user would."""
        for piece in text_pieces(line, self._terminal.type_chunk_chars):
            self._tmux("send-keys", "-t", exact_target(session_id), "-l", piece)
            time.sleep(self._terminal.type_chunk_delay_ms / MILLISECONDS_PER_SECOND)
        # Enter separately, so the agent sees typed text plus submit, not one pasted block.
        time.sleep(self._terminal.submit_delay_ms / MILLISECONDS_PER_SECOND)
        self.press_enter(session_id)

    def press_enter(self, session_id: str) -> None:
        self._tmux("send-keys", "-t", exact_target(session_id), "-l", "\r")

    def paste_text(self, session_id: str, text: str) -> None:
        """Put text into the agent's input without submitting it, as one paste (bracketed, if
        the agent asked for that), so the user can read it there and send it themselves."""
        buffer = f"agent-orc-{session_id}"
        self._tmux("set-buffer", "-b", buffer, "--", text)
        # -r keeps the line breaks as they are, -d drops the buffer afterwards.
        self._tmux("paste-buffer", "-p", "-r", "-d", "-b", buffer, "-t", exact_target(session_id))

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
        session_id, profile, path, model, suffix, pane_dead, dead_status, created = line.split(
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
            suffix=suffix or None,
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
