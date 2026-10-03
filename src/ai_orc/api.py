"""HTTP API of AI-Orc."""

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ai_orc import files
from ai_orc.auth import Clock, Credentials, LoginGuard, TokenSigner, verify_password
from ai_orc.config import Config, TerminalConfig
from ai_orc.scope import AccessScope, OutsideScopeError
from ai_orc.sessions import (
    AgentSession,
    SessionAlreadyRunningError,
    SessionManager,
    SessionNotFoundError,
    UnknownProfileError,
)
from ai_orc.terminal import bridge
from ai_orc.trash import RestoreConflictError, Trash, TrashEntryNotFoundError, home_trash_dir

SESSION_COOKIE = "ai_orc_session"
# Custom WebSocket close codes (4000-4999 are free for applications).
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN_ORIGIN = 4403
WS_CLOSE_SESSION_NOT_FOUND = 4404
SECONDS_PER_DAY = 86400
SECONDS_PER_MINUTE = 60


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
    files.FileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    files.NotTextError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    SessionNotFoundError: status.HTTP_404_NOT_FOUND,
    UnknownProfileError: status.HTTP_404_NOT_FOUND,
    TrashEntryNotFoundError: status.HTTP_404_NOT_FOUND,
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
    scope = AccessScope(
        config.files.base_dir,
        Path.home(),
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

    app = FastAPI(title="AI-Orc", docs_url=None, redoc_url=None, openapi_url=None)

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
    def agents() -> list[dict[str, str]]:
        return [{"name": name, "label": p.label} for name, p in config.agents.items()]

    @app.get("/api/terminal", dependencies=authenticated)
    def terminal_settings() -> TerminalConfig:
        return config.terminal

    @app.get("/api/sessions", dependencies=authenticated)
    def list_sessions() -> list[AgentSession]:
        return sessions.list()

    @app.post("/api/sessions", dependencies=authenticated)
    def start_session(body: StartSessionRequest) -> AgentSession:
        path = scope.resolve(body.path)
        if not path.is_dir():
            raise NotADirectoryError(str(path))
        return sessions.start(body.profile, path, body.resume)

    @app.delete(
        "/api/sessions/{session_id}",
        dependencies=authenticated,
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def stop_session(session_id: str) -> None:
        sessions.stop(session_id)

    @app.websocket("/api/sessions/{session_id}/terminal")
    async def terminal(websocket: WebSocket, session_id: str) -> None:
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
        await bridge(websocket, config.tmux.socket_name, session_id)

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
        # Mounted last, so the API routes above take precedence.
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="pwa")

    return app


def _error_handler(status_code: int) -> Any:
    async def handle(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            {"error": type(error).__name__, "detail": str(error)}, status_code=status_code
        )

    return handle
