"""HTTP API of Agent-Orc."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_orc import files
from agent_orc.approvals import ApprovalNotFoundError, ApprovalRequest, decide, open_requests
from agent_orc.attachments import store_attachment
from agent_orc.auth import Clock, Credentials, LoginGuard, TokenSigner, verify_password
from agent_orc.changes import (
    ChangeNotFoundError,
    NotAGitRepositoryError,
    file_changes,
    file_diff,
)
from agent_orc.config import Config, LiveEffortConfig, TerminalConfig
from agent_orc.context import QUOTA_SOURCES, session_busy, session_status, store_activity
from agent_orc.dictation import (
    Device,
    DictationServiceError,
    GpuUnavailableError,
    UnsupportedAudioError,
    transcribe,
)
from agent_orc.effort import (
    EFFORT_STORES,
    PERMISSION_STORES,
    InvalidEffortError,
    InvalidPermissionModeError,
    Reasoning,
    set_reasoning_live,
)
from agent_orc.history import (
    CONVERSATION_SEARCHES,
    CONVERSATION_SOURCES,
    ConversationNotFoundError,
)
from agent_orc.push import (
    add_subscription,
    agent_message,
    application_server_key,
    remove_subscription,
    send_to_all,
)
from agent_orc.scope import AccessScope, OutsideScopeError
from agent_orc.sessions import (
    AgentSession,
    SessionAlreadyRunningError,
    SessionManager,
    SessionNotFoundError,
    UnknownProfileError,
)
from agent_orc.state import read_card_order, read_workspaces, write_card_order, write_workspaces
from agent_orc.terminal import bridge
from agent_orc.trash import RestoreConflictError, Trash, TrashEntryNotFoundError, home_trash_dir
from agent_orc.trust import FOLDER_TRUST

SESSION_COOKIE = "agent_orc_session"
# Written by the frontend build next to index.html (frontend/vite.config.ts); sent with every
# response, so an open app notices that a newer build has been installed.
BUILD_ID_FILE = "build-id.txt"
BUILD_ID_HEADER = "X-Build-Id"
# Custom WebSocket close codes (4000-4999 are free for applications).
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN_ORIGIN = 4403
WS_CLOSE_SESSION_NOT_FOUND = 4404
SECONDS_PER_DAY = 86400
SECONDS_PER_MINUTE = 60
# How often effort changes waiting for a busy agent are checked.
PENDING_EFFORT_CHECK_SECONDS = 2

logger = logging.getLogger(__name__)


class FolderBusyError(RuntimeError):
    """An agent session runs in this folder or below it."""


# Single place mapping domain errors to HTTP status codes.
ERROR_STATUS: dict[type[Exception], int] = {
    OutsideScopeError: status.HTTP_403_FORBIDDEN,
    FileNotFoundError: status.HTTP_404_NOT_FOUND,
    NotADirectoryError: status.HTTP_400_BAD_REQUEST,
    IsADirectoryError: status.HTTP_400_BAD_REQUEST,
    FileExistsError: status.HTTP_409_CONFLICT,
    RestoreConflictError: status.HTTP_409_CONFLICT,
    files.FileConflictError: status.HTTP_409_CONFLICT,
    FolderBusyError: status.HTTP_409_CONFLICT,
    SessionAlreadyRunningError: status.HTTP_409_CONFLICT,
    files.InvalidNameError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidEffortError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidPermissionModeError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ApprovalNotFoundError: status.HTTP_404_NOT_FOUND,
    ChangeNotFoundError: status.HTTP_404_NOT_FOUND,
    NotAGitRepositoryError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    files.FileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    files.NotTextError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    SessionNotFoundError: status.HTTP_404_NOT_FOUND,
    UnknownProfileError: status.HTTP_404_NOT_FOUND,
    TrashEntryNotFoundError: status.HTTP_404_NOT_FOUND,
    ConversationNotFoundError: status.HTTP_404_NOT_FOUND,
    UnsupportedAudioError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    GpuUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
    DictationServiceError: status.HTTP_502_BAD_GATEWAY,
}


class PasswordRequest(BaseModel):
    password: str


class PathRequest(BaseModel):
    path: str


class CreateFolderRequest(BaseModel):
    parent: str
    name: str


class RenameRequest(BaseModel):
    path: str
    new_name: str


class WriteFileRequest(BaseModel):
    path: str
    content: str
    # None creates a new file; otherwise the version the editor loaded.
    expected_version: str | None


class StartSessionRequest(BaseModel):
    profile: str
    path: str
    resume: bool
    # Stored as the folder's reasoning; effort None: the agent's own default.
    effort: str | None
    ultracode: bool
    # Resume this earlier conversation (from GET /api/conversations) instead.
    conversation: str | None


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    """As the browser's PushSubscription.toJSON() gives it."""

    endpoint: str
    keys: PushKeys


class ApprovalDecision(BaseModel):
    request: str
    allow: bool


class PermissionModeRequest(BaseModel):
    mode: str


class EffortRequest(BaseModel):
    effort: str | None
    ultracode: bool
    # False: wait until the agent has finished its current answer (no tokens wasted).
    immediately: bool


class CardOrderRequest(BaseModel):
    # Folders of the agent cards, in the order the user arranged them.
    folders: list[str]


class Workspace(BaseModel):
    """Several agents side by side, as the workspace page arranges them."""

    # Open agents (session ids), in column order.
    tabs: list[str]
    # How many columns fill the screen.
    visible: int
    # Columns set wider or narrower, as a share of the screen width.
    widths: dict[str, float]
    active: str | None


class TrashEntryRequest(BaseModel):
    id: str


def create_app(
    config: Config,
    credentials: Credentials,
    *,
    static_dir: Path | None,
    clock: Clock = time.time,
) -> FastAPI:
    """Build the app; static_dir holds the built PWA (None serves the API only, for tests)."""
    sessions = SessionManager(config.tmux.socket_name, config.agents)
    home = Path.home()
    scope = AccessScope(
        config.files.base_dir,
        home,
        config.files.unlock_minutes * SECONDS_PER_MINUTE,
        clock,
    )
    trash = Trash(home_trash_dir())
    signer = TokenSigner(credentials.secret_key, config.auth.session_days * SECONDS_PER_DAY, clock)
    guard = LoginGuard(
        config.auth.max_failed_logins, config.auth.lockout_minutes * SECONDS_PER_MINUTE, clock
    )
    name_pattern = config.files.name_pattern
    max_edit_bytes = config.files.max_edit_bytes

    # Reasoning changes waiting until their (busy) agent has finished its answer.
    pending_effort: dict[str, Reasoning] = {}

    def find_session(session_id: str) -> AgentSession | None:
        return next((s for s in sessions.list() if s.id == session_id), None)

    def live_effort(profile_name: str) -> LiveEffortConfig | None:
        profile = config.agents.get(profile_name)
        return profile.effort.live if profile and profile.effort else None

    def apply_effort(session: AgentSession, reasoning: Reasoning) -> AgentSession:
        """Store the folder's reasoning (read at every start) and hand it to the agent: typed
        into a running agent that can switch in place, otherwise by resuming it."""
        pending_effort.pop(session.id, None)
        previous = folder_reasoning(session.profile, session.path)
        store_effort(session.profile, session.path, reasoning)
        live = live_effort(session.profile)
        if session.running and live is not None:
            submit_delay = config.terminal.submit_delay_ms
            set_reasoning_live(
                lambda line: sessions.type_line(session.id, line, submit_delay),
                live,
                previous,
                reasoning,
            )
            return session
        restarted = sessions.restart(session)
        # The ended agent cannot report that it stopped working.
        store_activity(session.id, busy=False)
        return restarted

    def apply_pending_efforts() -> None:
        for session_id, reasoning in list(pending_effort.items()):
            session = find_session(session_id)
            if session is None:
                pending_effort.pop(session_id, None)
            elif not session.running or not session_busy(session):
                apply_effort(session, reasoning)

    async def watch_pending_efforts() -> None:
        while True:
            await asyncio.sleep(PENDING_EFFORT_CHECK_SECONDS)
            try:
                # Off the event loop: switching in place waits a few seconds (effort.py).
                await asyncio.to_thread(apply_pending_efforts)
            except Exception:
                # Keep watching the other sessions; this one is dropped and logged.
                logger.exception("applying a pending effort change failed")
                pending_effort.clear()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        watcher = asyncio.create_task(watch_pending_efforts())
        yield
        watcher.cancel()

    app = FastAPI(
        title="Agent-Orc", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )

    for error_type, status_code in ERROR_STATUS.items():
        app.add_exception_handler(error_type, _error_handler(status_code))

    def require_login(request: Request) -> None:
        if not is_logged_in(request.cookies.get(SESSION_COOKIE)):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    def is_logged_in(token: str | None) -> bool:
        return token is not None and signer.is_valid(token)

    def check_password(password: str) -> None:
        locked = guard.seconds_locked()
        if locked > 0:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, headers={"Retry-After": str(int(locked) + 1)}
            )
        if not verify_password(password, credentials.password_hash):
            guard.record_failure()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)
        guard.record_success()

    def ensure_no_session_inside(path: Path) -> None:
        for session in sessions.list():
            if session.path.is_relative_to(path):
                raise FolderBusyError(str(session.path))

    def validate_effort(profile_name: str, reasoning: Reasoning) -> None:
        """An agent accepts only the levels (and ultracode) its profile offers."""
        profile = config.agents.get(profile_name)
        effort = profile.effort if profile else None
        # An agent with levels always gets one of them; one without gets none.
        valid = reasoning.effort is None if effort is None else reasoning.effort in effort.levels
        if not valid:
            raise InvalidEffortError(str(reasoning.effort))
        if reasoning.ultracode and not (effort and effort.ultracode):
            raise InvalidEffortError("ultracode")

    def store_effort(profile_name: str, folder: Path, reasoning: Reasoning) -> None:
        validate_effort(profile_name, reasoning)
        profile = config.agents.get(profile_name)
        if profile and profile.effort:
            EFFORT_STORES[profile.effort.store].write(folder, reasoning)

    def folder_reasoning(profile_name: str, folder: Path) -> Reasoning:
        profile = config.agents.get(profile_name)
        if profile is None or profile.effort is None:
            return Reasoning(effort=None, ultracode=False)
        stored = EFFORT_STORES[profile.effort.store].read(folder)
        # A folder without a level of its own has the configured one; starting there writes it.
        effort = stored.effort if stored.effort is not None else profile.effort.default
        return Reasoning(effort=effort, ultracode=stored.ultracode)

    def scope_state() -> dict[str, Any]:
        return {
            "root": str(scope.root),
            "base_dir": str(scope.base_dir),
            "seconds_unlocked": scope.seconds_unlocked(),
            "unlock_minutes": config.files.unlock_minutes,
        }

    @app.post("/api/login", status_code=status.HTTP_204_NO_CONTENT)
    def login(body: PasswordRequest, response: Response) -> None:
        check_password(body.password)
        response.set_cookie(
            SESSION_COOKIE,
            signer.issue(),
            max_age=config.auth.session_days * SECONDS_PER_DAY,
            httponly=True,
            secure=config.server.cookie_secure,
            samesite="strict",
        )

    @app.post("/api/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(response: Response) -> None:
        response.delete_cookie(SESSION_COOKIE)

    authenticated = [Depends(require_login)]

    @app.get("/api/me", dependencies=authenticated)
    def me() -> dict[str, bool]:
        return {"authenticated": True}

    @app.get("/api/scope", dependencies=authenticated)
    def get_scope() -> dict[str, Any]:
        return scope_state()

    @app.post("/api/scope/unlock", dependencies=authenticated)
    def unlock(body: PasswordRequest) -> dict[str, Any]:
        check_password(body.password)
        scope.unlock()
        return scope_state()

    @app.post("/api/scope/lock", dependencies=authenticated)
    def lock() -> dict[str, Any]:
        scope.lock()
        return scope_state()

    @app.get("/api/agents", dependencies=authenticated)
    def agents() -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "label": p.label,
                "effort_levels": p.effort.levels if p.effort else [],
                "ultracode": bool(p.effort and p.effort.ultracode),
                # Switches its reasoning in place, without a restart.
                "effort_live": bool(p.effort and p.effort.live),
                "permission_modes": p.permission.modes if p.permission else [],
            }
            for name, p in config.agents.items()
        ]

    @app.get("/api/terminal", dependencies=authenticated)
    def terminal_settings() -> TerminalConfig:
        return config.terminal

    @app.get("/api/card-order", dependencies=authenticated)
    def card_order() -> list[str]:
        """Kept on the server, so the arrangement is the same on every device."""
        return read_card_order()

    @app.put("/api/card-order", dependencies=authenticated, status_code=status.HTTP_204_NO_CONTENT)
    def arrange_cards(body: CardOrderRequest) -> None:
        write_card_order(body.folders)

    @app.get("/api/workspaces", dependencies=authenticated)
    def workspaces() -> dict[str, Workspace]:
        """Named workspaces, kept on the server so every device and browser tab can open them."""
        return {name: Workspace(**stored) for name, stored in read_workspaces().items()}

    @app.put(
        "/api/workspaces/{name}", dependencies=authenticated, status_code=status.HTTP_204_NO_CONTENT
    )
    def store_workspace(name: str, body: Workspace) -> None:
        stored = read_workspaces()
        stored[name] = body.model_dump()
        write_workspaces(stored)

    @app.delete(
        "/api/workspaces/{name}", dependencies=authenticated, status_code=status.HTTP_204_NO_CONTENT
    )
    def delete_workspace(name: str) -> None:
        stored = read_workspaces()
        stored.pop(name, None)
        write_workspaces(stored)

    @app.get("/api/push/key", dependencies=authenticated)
    def push_key() -> dict[str, str]:
        """The public key a device subscribes with (Push API applicationServerKey)."""
        return {"key": application_server_key()}

    @app.post(
        "/api/push/subscriptions",
        dependencies=authenticated,
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def subscribe(body: PushSubscription) -> None:
        add_subscription(body.model_dump())

    @app.delete(
        "/api/push/subscriptions",
        dependencies=authenticated,
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def unsubscribe(endpoint: str) -> None:
        remove_subscription(endpoint)

    @app.post("/api/push/test", dependencies=authenticated)
    def push_test() -> dict[str, int]:
        """A sample "finished" message to every subscribed device."""
        message = agent_message("test", "", "Agent-Orc", "")
        return {"delivered": send_to_all(message, config.push)}

    @app.get("/api/quota", dependencies=authenticated)
    def quota() -> list[dict[str, Any]]:
        """Usage limits per agent profile that reports them; windows are empty until it has."""
        return [
            {
                "profile": name,
                "label": profile.label,
                "windows": QUOTA_SOURCES[profile.quota]() or {},
            }
            for name, profile in config.agents.items()
            if profile.quota is not None
        ]

    @app.get("/api/dictation", dependencies=authenticated)
    def dictation_settings() -> dict[str, Any]:
        # The browser's own speech recognition listens in the same language.
        return {
            "language": config.dictation.language,
            "whisper": config.dictation.whisper_url is not None,
        }

    @app.post("/api/dictation", dependencies=authenticated)
    async def dictate(request: Request, device: Device) -> dict[str, str]:
        """Transcribe the recorded audio in the request body."""
        audio = await request.body()
        content_type = request.headers.get("content-type", "")
        # The Whisper call blocks for seconds, on the CPU even longer.
        text = await asyncio.to_thread(transcribe, audio, content_type, device, config.dictation)
        return {"text": text}

    @app.get("/api/sessions", dependencies=authenticated)
    def list_sessions() -> list[dict[str, Any]]:
        requests = open_requests()
        return [session_entry(s, requests) for s in sessions.list()]

    def session_entry(session: AgentSession, requests: list[ApprovalRequest]) -> dict[str, Any]:
        empty = {"model": None, "context_tokens": None, "context_window": None}
        pending = pending_effort.get(session.id)
        status = session_status(session)
        folder = folder_reasoning(session.profile, session.path)
        return {
            **asdict(session),
            **empty,
            **status,
            # As the agent reports it; before its first report, the folder's level it started with.
            "effort": status.get("effort") or folder.effort,
            "busy": session_busy(session),
            # As stored for the folder; the agent reads it at start.
            "ultracode": folder.ultracode,
            "permission_mode": folder_permission_mode(session.profile, session.path),
            # Waiting for the user's answer; normally at most one, as Claude asks one at a time.
            "approvals": [asdict(r) for r in requests if r.session == session.id],
            "effort_pending": pending is not None,
            "pending_effort": pending.effort if pending else None,
            "pending_ultracode": pending.ultracode if pending else None,
        }

    @app.post("/api/sessions", dependencies=authenticated)
    def start_session(body: StartSessionRequest) -> AgentSession:
        path = scope.resolve(body.path)
        if not path.is_dir():
            raise NotADirectoryError(str(path))
        profile = config.agents.get(body.profile)
        if profile and profile.trust:
            FOLDER_TRUST[profile.trust](home, path)
        if body.conversation is not None:
            ids = {c["id"] for c in conversations_of(body.profile, path)}
            if body.conversation not in ids:
                raise ConversationNotFoundError(body.conversation)
        effort = body.effort
        if effort is None and profile and profile.effort:
            # Started without a choice: the folder's level, or else the configured one.
            effort = folder_reasoning(body.profile, path).effort
        store_effort(body.profile, path, Reasoning(effort, body.ultracode))
        if profile and profile.permission:
            # A folder without a mode of its own starts in the configured one, so the card
            # shows the mode the agent really runs in, whatever the user's own setting says.
            store = PERMISSION_STORES[profile.permission.store]
            if store.read(path) is None:
                store.write(path, profile.permission.default)
        return sessions.start(body.profile, path, body.resume, body.conversation)

    def conversations_of(profile_name: str, folder: Path) -> list[dict[str, Any]]:
        profile = config.agents.get(profile_name)
        if profile is None or profile.conversations is None:
            return []
        listing = CONVERSATION_SOURCES[profile.conversations.source](home, folder, clock)
        return [asdict(conversation) for conversation in listing]

    @app.get("/api/conversations", dependencies=authenticated)
    def list_conversations(profile: str, path: str) -> list[dict[str, Any]]:
        return conversations_of(profile, scope.resolve(path))

    @app.get("/api/conversations/search", dependencies=authenticated)
    def search_conversations(profile: str, path: str, query: str) -> list[dict[str, Any]]:
        """Earlier conversations in the folder whose messages contain the query."""
        agent = config.agents.get(profile)
        if agent is None or agent.conversations is None:
            return []
        search = CONVERSATION_SEARCHES[agent.conversations.source]
        return [asdict(hit) for hit in search(home, scope.resolve(path), query)]

    @app.post(
        "/api/sessions/{session_id}/approval",
        dependencies=authenticated,
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def answer_approval(session_id: str, body: ApprovalDecision) -> None:
        """The user's answer to a permission request, handed to the waiting hook."""
        if not any(r.id == body.request and r.session == session_id for r in open_requests()):
            raise ApprovalNotFoundError(body.request)
        decide(body.request, body.allow)

    def session_folder(session_id: str) -> Path:
        session = find_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session.path

    @app.get("/api/sessions/{session_id}/changes", dependencies=authenticated)
    def list_changes(session_id: str) -> list[dict[str, str]]:
        """Files the agent changed in its project (git working tree against the last commit)."""
        return [asdict(change) for change in file_changes(session_folder(session_id))]

    @app.get("/api/sessions/{session_id}/changes/diff", dependencies=authenticated)
    def change_diff(session_id: str, path: str) -> dict[str, Any]:
        return asdict(file_diff(session_folder(session_id), path))

    def folder_permission_mode(profile_name: str, folder: Path) -> str | None:
        profile = config.agents.get(profile_name)
        if profile is None or profile.permission is None:
            return None
        return PERMISSION_STORES[profile.permission.store].read(folder)

    @app.put(
        "/api/sessions/{session_id}/permission-mode",
        dependencies=authenticated,
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def change_permission_mode(session_id: str, body: PermissionModeRequest) -> None:
        """Takes effect at the agent's next start, like the effort of a running agent."""
        session = find_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        profile = config.agents.get(session.profile)
        permission = profile.permission if profile else None
        if permission is None or body.mode not in permission.modes:
            raise InvalidPermissionModeError(body.mode)
        PERMISSION_STORES[permission.store].write(session.path, body.mode)

    @app.post("/api/sessions/{session_id}/effort", dependencies=authenticated)
    def change_effort(session_id: str, body: EffortRequest) -> dict[str, bool]:
        """Change the effort now, or once the busy agent has finished its answer."""
        session = find_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        reasoning = Reasoning(body.effort, body.ultracode)
        validate_effort(session.profile, reasoning)
        # Typing into a busy agent would mix with its work: an agent that switches in place
        # always waits for the end of its answer.
        immediately = body.immediately and live_effort(session.profile) is None
        if immediately or not session.running or not session_busy(session):
            apply_effort(session, reasoning)
            return {"applied": True}
        pending_effort[session_id] = reasoning
        return {"applied": False}

    @app.delete(
        "/api/sessions/{session_id}/effort",
        dependencies=authenticated,
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def cancel_effort_change(session_id: str) -> None:
        pending_effort.pop(session_id, None)

    @app.get("/api/effort", dependencies=authenticated)
    def folder_effort(profile: str, path: str) -> Reasoning:
        return folder_reasoning(profile, scope.resolve(path))

    @app.post("/api/sessions/{session_id}/attachments", dependencies=authenticated)
    async def attach(session_id: str, name: str, request: Request) -> dict[str, str]:
        """Store the file in the request body in the agent's folder; returns its path there."""
        session = find_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        content = await request.body()
        return {"path": str(store_attachment(session.path, name, content, clock))}

    @app.get("/api/sessions/{session_id}/text", dependencies=authenticated)
    def session_text(session_id: str) -> dict[str, str]:
        """Plain text of the terminal, for selecting and copying on a phone."""
        return {"text": sessions.text(session_id, config.terminal.text_history_lines)}

    @app.delete(
        "/api/sessions/{session_id}",
        dependencies=authenticated,
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def stop_session(session_id: str) -> None:
        sessions.stop(session_id)

    @app.websocket("/api/sessions/{session_id}/terminal")
    async def terminal(websocket: WebSocket, session_id: str, cols: int, rows: int) -> None:
        """The browser sends its terminal size along (cols, rows), so tmux starts at it."""
        if not is_logged_in(websocket.cookies.get(SESSION_COOKIE)):
            await websocket.close(WS_CLOSE_UNAUTHORIZED)
            return
        # Browsers send cookies on cross-site WebSocket handshakes too; the Origin check
        # stops other web pages from opening a terminal with the user's login.
        if urlsplit(websocket.headers.get("origin", "")).netloc != websocket.headers.get("host"):
            await websocket.close(WS_CLOSE_FORBIDDEN_ORIGIN)
            return
        if all(session.id != session_id for session in sessions.list()):
            await websocket.close(WS_CLOSE_SESSION_NOT_FOUND)
            return
        await websocket.accept()
        await bridge(websocket, config.tmux.socket_name, session_id, cols, rows)

    @app.get("/api/files", dependencies=authenticated)
    def list_files(path: str) -> list[files.FileEntry]:
        return files.list_directory(scope.resolve(path))

    @app.post("/api/files/folder", dependencies=authenticated)
    def create_folder(body: CreateFolderRequest) -> dict[str, str]:
        folder = files.create_folder(scope.resolve(body.parent), body.name, name_pattern)
        return {"path": str(folder)}

    @app.post("/api/files/rename", dependencies=authenticated)
    def rename(body: RenameRequest) -> dict[str, str]:
        path = scope.resolve(body.path)
        ensure_no_session_inside(path)
        return {"path": str(files.rename(path, body.new_name, name_pattern))}

    @app.get("/api/files/content", dependencies=authenticated)
    def read_file(path: str) -> files.TextFile:
        return files.read_text(scope.resolve(path), max_edit_bytes)

    @app.put("/api/files/content", dependencies=authenticated)
    def write_file(body: WriteFileRequest) -> dict[str, str]:
        path = scope.resolve(body.path)
        version = files.write_text(path, body.content, body.expected_version, max_edit_bytes)
        return {"version": version}

    @app.post("/api/files/trash", dependencies=authenticated)
    def move_to_trash(body: PathRequest) -> dict[str, Any]:
        path = scope.resolve(body.path)
        if path in (scope.base_dir, scope.home):
            raise OutsideScopeError(str(path))
        ensure_no_session_inside(path)
        return asdict(trash.move(path))

    @app.get("/api/trash", dependencies=authenticated)
    def list_trash() -> list[dict[str, Any]]:
        return [asdict(entry) for entry in trash.list()]

    @app.post("/api/trash/restore", dependencies=authenticated)
    def restore(body: TrashEntryRequest) -> dict[str, str]:
        # Restoring writes to the original location, which must be in scope.
        scope.resolve(str(trash.entry(body.id).original_path.parent))
        return {"path": str(trash.restore(body.id))}

    @app.delete(
        "/api/trash/{entry_id}", dependencies=authenticated, status_code=status.HTTP_204_NO_CONTENT
    )
    def delete_from_trash(entry_id: str) -> None:
        trash.delete(entry_id)

    @app.delete("/api/trash", dependencies=authenticated, status_code=status.HTTP_204_NO_CONTENT)
    def empty_trash() -> None:
        trash.empty()

    if static_dir is not None:
        build_id_file = static_dir / BUILD_ID_FILE

        @app.middleware("http")
        async def send_build_id(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            response = await call_next(request)
            # Read every time: an update may replace the files while this server runs, and the
            # header must name the build a reload would actually get.
            response.headers[BUILD_ID_HEADER] = build_id_file.read_text(encoding="utf-8")
            return response

        # Mounted last, so the API routes above take precedence.
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="pwa")

    return app


def _error_handler(status_code: int) -> Any:
    async def handle(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            {"error": type(error).__name__, "detail": str(error)}, status_code=status_code
        )

    return handle
