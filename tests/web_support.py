"""Shared helpers for the web interface tests: fake users, scripted models, app builders and a live server."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import TypeAdapter
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import create_writer_agent
from storyline.room import RoomEvent, RoomSnapshot
from storyline.web.app import create_app
from storyline.web.auth import SingleUserAuthenticator
from storyline.web.errors import AuthenticationError
from storyline.web.room_host import RoomHost
from storyline.web.user_workspaces import DirectoryUserWorkspaces, LocalUserWorkspaces
from storyline.workspace.file_workspace import FileWorkspace

DEFAULT_MODEL = "openrouter:default/model"
ALICE = {"Authorization": "Bearer alice-token"}
BOB = {"Authorization": "Bearer bob-token"}
SERVER_STOP_SECONDS = 1.5
EVENT_ADAPTER: TypeAdapter[RoomEvent] = TypeAdapter(RoomEvent)


class FakeAuthenticator:
    """Knows a few bearer tokens and the users they belong to."""

    def __init__(self, users: Mapping[str, str] | None = None) -> None:
        self._users = users or {"alice-token": "alice", "bob-token": "bob"}

    async def authenticate(self, headers: Mapping[str, str]) -> str:
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or token not in self._users:
            raise AuthenticationError("Sign in to use Storyline.")
        return self._users[token]


class ScriptedWriter:
    """A fake writer model: streams the given chunks, and can be held between two of them until released."""

    def __init__(self, *chunks: str, hold_after: int | None = None) -> None:
        self._chunks = chunks
        self._hold_after = hold_after
        self.release = asyncio.Event()
        self.holding = asyncio.Event()
        self.requests = 0
        self.model = FunctionModel(stream_function=self._stream)

    async def _stream(self, _: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        self.requests += 1
        for index, chunk in enumerate(self._chunks):
            if self._hold_after == index:
                self.holding.set()
                await self.release.wait()
            yield chunk


def local_app(tmp_path: Path, *, model: FunctionModel | None = None, static_dir: Path | None = None, keepalive_seconds: float = 15.0) -> FastAPI:
    """An app with authentication off: one local user working in ``tmp_path/workspace``."""
    return create_app(
        authenticator=SingleUserAuthenticator(),
        workspaces=LocalUserWorkspaces(FileWorkspace(root=tmp_path / "workspace")),
        agent=create_writer_agent(),
        default_model_name=DEFAULT_MODEL,
        model=model,
        static_dir=static_dir or tmp_path / "no-frontend",
        keepalive_seconds=keepalive_seconds,
    )


def multi_user_app(tmp_path: Path, *, model: FunctionModel | None = None) -> FastAPI:
    """An app with authentication on (fake bearer tokens) and one workspace per user under ``tmp_path/data``."""
    return create_app(
        authenticator=FakeAuthenticator(),
        workspaces=DirectoryUserWorkspaces(tmp_path / "data"),
        agent=create_writer_agent(),
        default_model_name=DEFAULT_MODEL,
        model=model,
        static_dir=tmp_path / "no-frontend",
    )


def room_host(workspace_root: Path, *, model: FunctionModel | None = None) -> RoomHost:
    """A room host for the one local user, working in ``workspace_root``."""
    return RoomHost(
        workspaces=LocalUserWorkspaces(FileWorkspace(root=workspace_root)),
        agent=create_writer_agent(),
        default_model_name=DEFAULT_MODEL,
        model=model,
    )


def rooms_of(app: FastAPI) -> RoomHost:
    rooms = app.state.rooms
    assert isinstance(rooms, RoomHost)
    return rooms


@asynccontextmanager
async def http_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Talk to the app in-process, running its startup and shutdown. Streaming responses cannot be read this way."""
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client


@dataclass(frozen=True)
class SseMessage:
    event: str
    data: str

    def room_event(self) -> RoomEvent:
        return EVENT_ADAPTER.validate_json(self.data)

    def snapshot(self) -> RoomSnapshot:
        assert self.event == "snapshot"
        return RoomSnapshot.model_validate_json(self.data)


def parse_sse(text: str) -> list[SseMessage]:
    """Decode a text/event-stream body into its messages; comment lines are skipped."""
    messages: list[SseMessage] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        fields = {name: value.removeprefix(" ") for name, _, value in (line.partition(":") for line in block.split("\n") if line and not line.startswith(":"))}
        if "event" in fields:
            messages.append(SseMessage(event=fields["event"], data=fields.get("data", "")))
    return messages


@asynccontextmanager
async def live_server(app: FastAPI) -> AsyncIterator[str]:
    """Serve the app on an ephemeral local port with uvicorn and yield its base URL."""
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", ws="none"))
    task = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    task.result()
                await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        done, _ = await asyncio.wait({task}, timeout=SERVER_STOP_SECONDS)
        if not done:
            # On Windows, a client that resets its connection (a closed browser tab does) can leave asyncio's server
            # waiting forever for that connection to finish closing; the test is over, so stop waiting.
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


class EventStream:
    """A live SSE connection, read message by message."""

    def __init__(self, response: httpx.Response) -> None:
        self._lines = response.aiter_lines()
        self.response = response
        self._block: list[str] = []

    async def next_message(self, timeout: float = 5.0) -> SseMessage | str:
        """Return the next message, or the text of a comment (e.g. ``: keepalive``)."""
        async with asyncio.timeout(timeout):
            async for line in self._lines:
                if line:
                    self._block.append(line)
                    continue
                block, self._block = self._block, []
                if len(block) == 1 and block[0].startswith(":"):
                    return block[0]
                parsed = parse_sse("\n".join(block) + "\n\n")
                if parsed:
                    return parsed[0]
        raise AssertionError("The stream ended.")

    async def next_event(self, timeout: float = 5.0) -> SseMessage:
        while True:
            message = await self.next_message(timeout)
            if isinstance(message, SseMessage):
                return message

    async def read_until(self, event_name: str, timeout: float = 5.0) -> list[SseMessage]:
        """Read messages up to and including the first one named ``event_name``."""
        seen: list[SseMessage] = []
        async with asyncio.timeout(timeout):
            while True:
                message = await self.next_event(timeout)
                seen.append(message)
                if message.event == event_name:
                    return seen


@asynccontextmanager
async def open_stream(base_url: str, story: str, headers: Mapping[str, str] | None = None) -> AsyncIterator[EventStream]:
    async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
        async with client.stream("GET", f"/api/stories/{story}/events", headers=dict(headers or {})) as response:
            yield EventStream(response)
