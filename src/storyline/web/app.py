"""Web application: the room protocol over HTTP and server-sent events."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic_ai import Agent
from pydantic_ai.models import Model

from storyline.agent import DEFAULT_MODEL_NAME, create_writer_agent
from storyline.web.auth import Authenticator
from storyline.web.errors import register_error_handlers
from storyline.web.room_host import RoomHost
from storyline.web.routes import create_api_router
from storyline.web.service import StoryService
from storyline.web.settings import DATA_DIR_ENV_VAR, WebSettings
from storyline.web.sse import KEEPALIVE_SECONDS
from storyline.web.static_files import default_static_dir, mount_frontend
from storyline.web.user_workspaces import UserWorkspaces
from storyline.workspace import WORKSPACE_ENV_VAR, Story

APP_FACTORY_PATH = "storyline.web.app:create_app_from_environment"
GRACEFUL_SHUTDOWN_SECONDS = 5


def create_app(
    *,
    authenticator: Authenticator,
    workspaces: UserWorkspaces,
    agent: Agent[Story, str],
    default_model_name: str = DEFAULT_MODEL_NAME,
    model: Model | str | None = None,
    static_dir: Path | None = None,
    keepalive_seconds: float = KEEPALIVE_SECONDS,
) -> FastAPI:
    """Build the web app around its collaborators; ``model`` runs every turn on that model (tests pass a fake)."""
    rooms = RoomHost(workspaces=workspaces, agent=agent, default_model_name=default_model_name, model=model)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await rooms.shutdown()

    app = FastAPI(lifespan=lifespan)
    app.state.rooms = rooms
    register_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Return a minimal service health response."""
        return {"status": "ok"}

    service = StoryService(workspaces=workspaces, rooms=rooms)
    app.include_router(create_api_router(authenticator=authenticator, service=service, keepalive_seconds=keepalive_seconds))
    mount_frontend(app, static_dir if static_dir is not None else default_static_dir())
    return app


def create_app_from_environment() -> FastAPI:
    """Build the app the way ``storyline serve`` runs it; uvicorn calls this as an app factory."""
    settings = WebSettings.from_environment()
    return create_app(
        authenticator=settings.authenticator(),
        workspaces=settings.user_workspaces(),
        agent=create_writer_agent(model_name=settings.default_model_name),
        default_model_name=settings.default_model_name,
        static_dir=settings.frontend_dir(),
    )


def run_server(*, port: int, reload: bool, host: str = "127.0.0.1", workspace: str | None = None, data_dir: str | None = None) -> None:
    """Serve the app.

    The app is built by a factory in the server process (which a reload starts afresh), so configuration travels in
    environment variables: ``workspace`` and ``data_dir`` set theirs. Raises if the configuration cannot work.
    """
    if workspace:
        os.environ[WORKSPACE_ENV_VAR] = workspace
    if data_dir:
        os.environ[DATA_DIR_ENV_VAR] = data_dir
    settings = WebSettings.from_environment()
    settings.authenticator()
    settings.user_workspaces()
    uvicorn.run(APP_FACTORY_PATH, factory=True, host=host, port=port, reload=reload, timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS)
