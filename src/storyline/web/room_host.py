"""The rooms a server process has open, and who is watching them."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from pydantic_ai import Agent
from pydantic_ai.models import Model

from storyline.room import RoomEvent, RoomSnapshot, StoryRoom
from storyline.web.errors import StoryNotFoundError
from storyline.web.user_workspaces import UserWorkspaces
from storyline.workspace import Story, StoryLibrary, StorySelectionError

logger = logging.getLogger(__name__)

SHUTDOWN_GRACE_SECONDS = 5.0

type RoomKey = tuple[str, str]
"""A user id and a story name."""


class SubscriptionClosedError(Exception):
    """Raised by ``RoomSubscription.next_event`` once the subscription has ended."""


class RoomSubscription:
    """A room's snapshot and every event after it: nothing lost, nothing repeated.

    Events wait in an unbounded queue, so a slow reader never holds up the room's turn.
    """

    def __init__(self, *, snapshot: RoomSnapshot, events: asyncio.Queue[RoomEvent | None], detach: Callable[[], None]) -> None:
        self.snapshot = snapshot
        self._events = events
        self._detach = detach
        self._detached = False

    async def next_event(self, *, timeout: float | None = None) -> RoomEvent | None:
        """Return the next event, or ``None`` if none arrived within ``timeout`` seconds."""
        try:
            event = await asyncio.wait_for(self._events.get(), timeout)
        except TimeoutError:
            return None
        if event is None:
            self._events.put_nowait(None)
            raise SubscriptionClosedError
        return event

    def end(self) -> None:
        """Make the reader stop once it has read what was already sent (the server is shutting down)."""
        self._events.put_nowait(None)

    def close(self) -> None:
        """Stop receiving events and let the room go if no one else needs it."""
        if not self._detached:
            self._detached = True
            self._detach()


@dataclass
class _OpenRoom:
    key: RoomKey
    room: StoryRoom
    holders: int = 0
    """Subscriptions and operations currently using the room."""
    subscriptions: set[RoomSubscription] = field(default_factory=set)
    watcher: asyncio.Task[None] | None = None
    """Waits for a running turn to end when nobody else holds the room."""


class RoomHost:
    """Opens each (user, story) room on first use and releases it when it is idle and unwatched.

    A room with a running turn stays open with no one watching, so closing a browser tab does not stop the writer.
    """

    def __init__(self, *, workspaces: UserWorkspaces, agent: Agent[Story, str], default_model_name: str, model: Model | str | None = None) -> None:
        self._workspaces = workspaces
        self._agent = agent
        self._default_model_name = default_model_name
        self._model = model
        self._rooms: dict[RoomKey, _OpenRoom] = {}
        self._opening = asyncio.Lock()

    @property
    def open_rooms(self) -> int:
        """How many rooms are open now."""
        return len(self._rooms)

    async def subscribe(self, user_id: str, story_name: str) -> RoomSubscription:
        """Open the story as the user's active one and return its current snapshot with the events that follow it."""
        async with self._opening:
            opened = await self._hold(user_id, story_name, remember_as_active=True)
            events: asyncio.Queue[RoomEvent | None] = asyncio.Queue()

            async def deliver(event: RoomEvent) -> None:
                events.put_nowait(event)

            # No await between taking the snapshot and attaching the listener, so no event falls between them.
            remove_listener = opened.room.add_listener(deliver)
            snapshot = opened.room.snapshot()

        def detach() -> None:
            remove_listener()
            opened.subscriptions.discard(subscription)
            self._release_hold(opened)

        subscription = RoomSubscription(snapshot=snapshot, events=events, detach=detach)
        opened.subscriptions.add(subscription)
        return subscription

    @asynccontextmanager
    async def use(self, user_id: str, story_name: str) -> AsyncIterator[StoryRoom]:
        """Hold the user's room for the story while an operation runs on it."""
        async with self._opening:
            opened = await self._hold(user_id, story_name, remember_as_active=False)
        try:
            yield opened.room
        finally:
            self._release_hold(opened)

    async def wait_until_idle(self) -> None:
        """Return once no open room has a turn running and the rooms nobody holds have been released."""
        rooms = list(self._rooms.values())
        await asyncio.gather(*(opened.room.wait_until_idle() for opened in rooms))
        watchers = [opened.watcher for opened in rooms if opened.watcher is not None]
        await asyncio.gather(*watchers, return_exceptions=True)

    async def shutdown(self, *, grace_seconds: float = SHUTDOWN_GRACE_SECONDS) -> None:
        """Interrupt running turns and give them a moment to save their work, then end every subscription."""
        rooms = list(self._rooms.values())
        for opened in rooms:
            opened.room.interrupt()
        try:
            await asyncio.wait_for(self.wait_until_idle(), grace_seconds)
        except TimeoutError:
            logger.warning("Some turns were still running %.1f seconds after shutdown began.", grace_seconds)
        for opened in rooms:
            for subscription in tuple(opened.subscriptions):
                subscription.end()
            if opened.watcher is not None:
                opened.watcher.cancel()

    async def _hold(self, user_id: str, story_name: str, *, remember_as_active: bool) -> _OpenRoom:
        """Return the open room, opening it if needed, with one more holder on it. Callers hold ``_opening``."""
        key = (user_id, story_name)
        opened = self._rooms.get(key)
        if opened is None or remember_as_active:
            story = await self._open_story(user_id, story_name, remember_as_active=remember_as_active)
            if opened is None:
                room = await StoryRoom.open(story=story, agent=self._agent, default_model_name=self._default_model_name, model=self._model)
                opened = self._rooms[key] = _OpenRoom(key=key, room=room)
        opened.holders += 1
        return opened

    async def _open_story(self, user_id: str, story_name: str, *, remember_as_active: bool) -> Story:
        workspace = self._workspaces.workspace_for(user_id)
        try:
            if remember_as_active:
                return await StoryLibrary(workspace).switch(name=story_name)
            return await workspace.open_story(name=story_name)
        except StorySelectionError as error:
            raise StoryNotFoundError(str(error)) from error

    def _release_hold(self, opened: _OpenRoom) -> None:
        opened.holders -= 1
        if opened.holders > 0 or self._rooms.get(opened.key) is not opened:
            return
        if not opened.room.busy:
            del self._rooms[opened.key]
        elif opened.watcher is None:
            opened.watcher = asyncio.get_running_loop().create_task(self._release_when_idle(opened))

    async def _release_when_idle(self, opened: _OpenRoom) -> None:
        try:
            await opened.room.wait_until_idle()
        finally:
            opened.watcher = None
        if opened.holders == 0 and self._rooms.get(opened.key) is opened:
            del self._rooms[opened.key]
