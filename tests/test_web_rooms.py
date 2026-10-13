"""Tests for the room host: lazy opening, snapshot-plus-events subscriptions, and releasing idle rooms."""

import asyncio
from pathlib import Path

import pytest

from storyline.room import (
    MessageEntry,
    ReplyDelta,
    RoomEvent,
    RoomSnapshot,
    TurnFinished,
    UserMessageAdded,
)
from storyline.web.errors import StoryNotFoundError
from storyline.web.room_host import RoomHost, RoomSubscription, SubscriptionClosedError
from storyline.workspace.file_workspace import FileWorkspace
from tests.web_support import ScriptedWriter, room_host

LOCAL = "local"


async def _workspace_with_story(tmp_path: Path, name: str = "harbor") -> FileWorkspace:
    workspace = FileWorkspace(root=tmp_path / "workspace")
    await workspace.create_story(name=name)
    return workspace


async def _events_until_turn_finished(subscription: RoomSubscription) -> list[RoomEvent]:
    events: list[RoomEvent] = []
    async with asyncio.timeout(5):
        while True:
            event = await subscription.next_event()
            assert event is not None
            events.append(event)
            if isinstance(event, TurnFinished):
                return events


def _reply_text(snapshot: RoomSnapshot, events: list[RoomEvent]) -> str:
    """Rebuild the writer's reply the way a client does: the snapshot's partial reply extended by the deltas after it."""
    partial = "".join(entry.text for entry in snapshot.entries if isinstance(entry, MessageEntry) and entry.role == "writer")
    return partial + "".join(event.text for event in events if isinstance(event, ReplyDelta))


@pytest.mark.asyncio
async def test_a_subscriber_gets_the_snapshot_and_then_every_event_of_a_turn(tmp_path) -> None:
    await _workspace_with_story(tmp_path)
    writer = ScriptedWriter("Once ", "upon ", "a time.")
    host = room_host(tmp_path / "workspace", model=writer.model)

    subscription = await host.subscribe(LOCAL, "harbor")
    async with host.use(LOCAL, "harbor") as room:
        await room.send_prompt("Begin.")
    events = await _events_until_turn_finished(subscription)

    assert subscription.snapshot.story == "harbor"
    assert subscription.snapshot.entries == ()
    assert events[0] == UserMessageAdded(text="Begin.")
    assert _reply_text(subscription.snapshot, events) == "Once upon a time."
    assert events[-1] == TurnFinished(outcome="completed")
    subscription.close()


@pytest.mark.asyncio
async def test_every_subscriber_of_a_room_gets_every_event(tmp_path) -> None:
    await _workspace_with_story(tmp_path)
    host = room_host(tmp_path / "workspace", model=ScriptedWriter("One ", "reply.").model)

    first = await host.subscribe(LOCAL, "harbor")
    second = await host.subscribe(LOCAL, "harbor")
    async with host.use(LOCAL, "harbor") as room:
        await room.send_prompt("Go.")
    first_events = await _events_until_turn_finished(first)
    second_events = await _events_until_turn_finished(second)

    assert first_events == second_events
    assert host.open_rooms == 1
    first.close()
    second.close()


@pytest.mark.asyncio
async def test_a_subscriber_joining_mid_turn_gets_the_partial_turn_in_its_snapshot_and_misses_nothing(tmp_path) -> None:
    await _workspace_with_story(tmp_path)
    writer = ScriptedWriter("Once ", "upon ", "a time.", hold_after=1)
    host = room_host(tmp_path / "workspace", model=writer.model)
    early = await host.subscribe(LOCAL, "harbor")
    async with host.use(LOCAL, "harbor") as room:
        await room.send_prompt("Begin.")
    await asyncio.wait_for(writer.holding.wait(), 5)

    late = await host.subscribe(LOCAL, "harbor")
    writer.release.set()
    late_events = await _events_until_turn_finished(late)

    assert [entry.text for entry in late.snapshot.entries if isinstance(entry, MessageEntry)] == ["Begin.", "Once "]
    assert late.snapshot.activity == "writing"
    assert _reply_text(late.snapshot, late_events) == "Once upon a time."
    assert _reply_text(early.snapshot, await _events_until_turn_finished(early)) == "Once upon a time."
    early.close()
    late.close()


@pytest.mark.asyncio
async def test_a_turn_survives_having_no_subscribers_and_the_room_is_released_when_it_ends(tmp_path) -> None:
    workspace = await _workspace_with_story(tmp_path)
    writer = ScriptedWriter("Saved ", "reply.", hold_after=1)
    host = room_host(tmp_path / "workspace", model=writer.model)
    subscription = await host.subscribe(LOCAL, "harbor")
    async with host.use(LOCAL, "harbor") as room:
        await room.send_prompt("Begin.")
    await asyncio.wait_for(writer.holding.wait(), 5)

    subscription.close()
    assert host.open_rooms == 1

    writer.release.set()
    await asyncio.wait_for(host.wait_until_idle(), 5)

    assert host.open_rooms == 0
    story = await workspace.open_story(name="harbor")
    saved = await story.read_message_history()
    assert "Saved reply." in str(saved[-1])
    reopened = await host.subscribe(LOCAL, "harbor")
    assert [entry.text for entry in reopened.snapshot.entries if isinstance(entry, MessageEntry)] == ["Begin.", "Saved reply."]
    reopened.close()


@pytest.mark.asyncio
async def test_a_room_used_for_one_operation_is_released_afterwards(tmp_path) -> None:
    await _workspace_with_story(tmp_path)
    host = room_host(tmp_path / "workspace")

    async with host.use(LOCAL, "harbor") as room:
        assert host.open_rooms == 1
        assert await room.read_script() == ""

    assert host.open_rooms == 0


@pytest.mark.asyncio
async def test_a_room_stays_open_while_anything_holds_it(tmp_path) -> None:
    await _workspace_with_story(tmp_path)
    host = room_host(tmp_path / "workspace")

    subscription = await host.subscribe(LOCAL, "harbor")
    async with host.use(LOCAL, "harbor"):
        pass
    assert host.open_rooms == 1

    subscription.close()
    subscription.close()
    assert host.open_rooms == 0


@pytest.mark.asyncio
async def test_concurrent_first_uses_share_one_room(tmp_path) -> None:
    await _workspace_with_story(tmp_path)
    host = room_host(tmp_path / "workspace")

    subscriptions = await asyncio.gather(*(host.subscribe(LOCAL, "harbor") for _ in range(5)))

    assert host.open_rooms == 1
    for subscription in subscriptions:
        subscription.close()
    assert host.open_rooms == 0


@pytest.mark.asyncio
async def test_unknown_stories_are_not_found(tmp_path) -> None:
    await _workspace_with_story(tmp_path)
    host = room_host(tmp_path / "workspace")

    with pytest.raises(StoryNotFoundError):
        await host.subscribe(LOCAL, "missing")
    with pytest.raises(StoryNotFoundError):
        async with host.use(LOCAL, "missing"):
            pass
    assert host.open_rooms == 0


@pytest.mark.asyncio
async def test_subscribing_makes_the_story_active_but_using_it_does_not(tmp_path) -> None:
    workspace = await _workspace_with_story(tmp_path, "harbor")
    await workspace.create_story(name="mill")
    host = room_host(tmp_path / "workspace")
    assert await workspace.read_active_story() is None

    async with host.use(LOCAL, "harbor"):
        pass
    assert await workspace.read_active_story() is None

    (await host.subscribe(LOCAL, "mill")).close()
    assert await workspace.read_active_story() == "mill"


@pytest.mark.asyncio
async def test_shutdown_interrupts_running_turns_and_then_ends_subscriptions(tmp_path) -> None:
    workspace = await _workspace_with_story(tmp_path)
    writer = ScriptedWriter("Started ", "never finished.", hold_after=1)
    host = room_host(tmp_path / "workspace", model=writer.model)
    subscription = await host.subscribe(LOCAL, "harbor")
    async with host.use(LOCAL, "harbor") as room:
        await room.send_prompt("Begin.")
    await asyncio.wait_for(writer.holding.wait(), 5)

    await asyncio.wait_for(host.shutdown(), 5)

    events = await _events_until_turn_finished(subscription)
    assert events[-1] == TurnFinished(outcome="interrupted")
    with pytest.raises(SubscriptionClosedError):
        while True:  # whatever was already sent is still delivered; then the stream ends
            await subscription.next_event(timeout=1)
    assert "Started" in str((await (await workspace.open_story(name="harbor")).read_message_history())[-1])


@pytest.mark.asyncio
async def test_a_quiet_subscription_reports_a_timeout_instead_of_an_event(tmp_path) -> None:
    await _workspace_with_story(tmp_path)
    host: RoomHost = room_host(tmp_path / "workspace")
    subscription = await host.subscribe(LOCAL, "harbor")

    assert await subscription.next_event(timeout=0.01) is None
    subscription.close()
