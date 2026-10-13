"""The server-sent events stream of a story's room."""

import asyncio
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from storyline.room import RoomEvent, RoomSnapshot, event_type_name
from storyline.web.room_host import RoomSubscription, SubscriptionClosedError

KEEPALIVE_SECONDS = 15.0
KEEPALIVE_MESSAGE = ": keepalive\n\n"
SNAPSHOT_EVENT_NAME = "snapshot"


def snapshot_message(snapshot: RoomSnapshot) -> str:
    """Encode the snapshot as the first message of a stream."""
    return _message(SNAPSHOT_EVENT_NAME, snapshot.model_dump_json())


def event_message(event: RoomEvent) -> str:
    """Encode a room event as one message named after the event's type."""
    return _message(event_type_name(type(event)), event.model_dump_json())


async def stream_messages(subscription: RoomSubscription, *, keepalive_seconds: float = KEEPALIVE_SECONDS) -> AsyncIterator[str]:
    """Yield the snapshot, then every event as it arrives, with a keepalive comment whenever the room is quiet."""
    try:
        yield snapshot_message(subscription.snapshot)
        while True:
            try:
                event = await subscription.next_event(timeout=keepalive_seconds)
            except SubscriptionClosedError:
                return
            yield KEEPALIVE_MESSAGE if event is None else event_message(event)
    finally:
        subscription.close()


class EventStreamResponse(StreamingResponse):
    """A ``text/event-stream`` response that unsubscribes when the client goes away, however that happens."""

    def __init__(self, subscription: RoomSubscription, *, keepalive_seconds: float = KEEPALIVE_SECONDS) -> None:
        super().__init__(
            stream_messages(subscription, keepalive_seconds=keepalive_seconds),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
        self._subscription = subscription

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Servers that follow ASGI 2.4+ only tell a response the client left when it next writes, which a quiet stream
        # may not do for a long time; listening for the disconnect ends the stream (and the subscription) at once.
        streaming = asyncio.create_task(self.stream_response(send))
        disconnected = asyncio.create_task(_wait_for_disconnect(receive))
        try:
            await asyncio.wait({streaming, disconnected}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (streaming, disconnected):
                task.cancel()
            await asyncio.gather(streaming, disconnected, return_exceptions=True)
            self._subscription.close()


async def _wait_for_disconnect(receive: Receive) -> None:
    while (await receive())["type"] != "http.disconnect":
        pass


def _message(event_name: str, data: str) -> str:
    return f"event: {event_name}\ndata: {data}\n\n"
