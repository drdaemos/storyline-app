"""Tests for the events stream, over a real local socket (an in-process transport would buffer an endless response)."""

import asyncio

import httpx
import pytest

from storyline.room import MessageEntry
from storyline.workspace.file_workspace import FileWorkspace
from tests.web_support import ALICE, BOB, ScriptedWriter, SseMessage, live_server, local_app, multi_user_app, open_stream, rooms_of


async def _create_story(base_url: str, name: str, headers: dict[str, str] | None = None) -> None:
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.post("/api/stories", json={"name": name}, headers=headers)
        assert response.status_code == 201


async def _post(base_url: str, path: str, json: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
    async with httpx.AsyncClient(base_url=base_url) as client:
        return await client.post(path, json=json, headers=headers)


def _writer_texts(snapshot_message: SseMessage) -> list[str]:
    return [entry.text for entry in snapshot_message.snapshot().entries if isinstance(entry, MessageEntry) and entry.role == "writer"]


async def _until(condition) -> None:
    async with asyncio.timeout(5):
        while not condition():
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_the_stream_starts_with_a_snapshot_and_carries_a_turn_as_named_events(tmp_path) -> None:
    app = local_app(tmp_path, model=ScriptedWriter("Fog ", "rolled in.").model)
    async with live_server(app) as base_url:
        await _create_story(base_url, "harbor")
        async with open_stream(base_url, "harbor") as stream:
            assert stream.response.status_code == 200
            assert stream.response.headers["content-type"].startswith("text/event-stream")
            first = await stream.next_event()
            assert first.event == "snapshot"
            assert first.snapshot().story == "harbor"
            assert first.snapshot().entries == ()

            accepted = await _post(base_url, "/api/stories/harbor/prompts", {"text": "Begin."})
            messages = await stream.read_until("turn_finished")

    assert accepted.status_code == 202
    names = [message.event for message in messages]
    assert names[0] == "user_message_added"
    assert {"reply_started", "reply_delta", "reply_finished", "activity_changed"} <= set(names)
    assert all(message.room_event().type == message.event for message in messages)
    assert "".join(message.room_event().text for message in messages if message.event == "reply_delta") == "Fog rolled in."
    assert messages[-1].room_event().outcome == "completed"


@pytest.mark.asyncio
async def test_a_second_tab_opening_mid_turn_gets_the_partial_turn_and_both_tabs_see_the_rest(tmp_path) -> None:
    writer = ScriptedWriter("Once ", "upon ", "a time.", hold_after=1)
    app = local_app(tmp_path, model=writer.model)
    async with live_server(app) as base_url:
        await _create_story(base_url, "harbor")
        async with open_stream(base_url, "harbor") as first_tab:
            await first_tab.next_event()
            await _post(base_url, "/api/stories/harbor/prompts", {"text": "Begin."})
            await asyncio.wait_for(writer.holding.wait(), 5)

            async with open_stream(base_url, "harbor") as second_tab:
                snapshot = await second_tab.next_event()
                writer.release.set()
                second_messages = await second_tab.read_until("turn_finished")
            first_messages = await first_tab.read_until("turn_finished")

    assert _writer_texts(snapshot) == ["Once "]
    assert snapshot.snapshot().activity == "writing"
    deltas = "".join(message.room_event().text for message in second_messages if message.event == "reply_delta")
    assert "Once " + deltas == "Once upon a time."
    assert [message.event for message in second_messages] == [message.event for message in first_messages][-len(second_messages) :]


@pytest.mark.asyncio
async def test_a_turn_goes_on_after_the_tab_closes_and_a_reconnecting_tab_gets_a_fresh_snapshot(tmp_path) -> None:
    writer = ScriptedWriter("Saved ", "reply.", hold_after=1)
    app = local_app(tmp_path, model=writer.model)
    async with live_server(app) as base_url:
        await _create_story(base_url, "harbor")
        async with open_stream(base_url, "harbor") as tab:
            await tab.next_event()
            await _post(base_url, "/api/stories/harbor/prompts", {"text": "Begin."})
            await asyncio.wait_for(writer.holding.wait(), 5)
        await asyncio.sleep(0.05)
        assert rooms_of(app).open_rooms == 1

        writer.release.set()
        await asyncio.wait_for(rooms_of(app).wait_until_idle(), 5)
        assert rooms_of(app).open_rooms == 0

        async with open_stream(base_url, "harbor") as reconnected:
            snapshot = await reconnected.next_event()

    assert _writer_texts(snapshot) == ["Saved reply."]
    assert snapshot.snapshot().activity == "idle"


@pytest.mark.asyncio
async def test_a_disconnecting_client_is_unsubscribed_and_an_idle_room_is_released(tmp_path) -> None:
    app = local_app(tmp_path)
    async with live_server(app) as base_url:
        await _create_story(base_url, "harbor")
        async with open_stream(base_url, "harbor") as stream:
            await stream.next_event()
            assert rooms_of(app).open_rooms == 1

        await _until(lambda: rooms_of(app).open_rooms == 0)


@pytest.mark.asyncio
async def test_a_quiet_stream_sends_keepalive_comments(tmp_path) -> None:
    app = local_app(tmp_path, keepalive_seconds=0.05)
    async with live_server(app) as base_url:
        await _create_story(base_url, "harbor")
        async with open_stream(base_url, "harbor") as stream:
            assert isinstance(await stream.next_message(), SseMessage)
            assert await stream.next_message() == ": keepalive"
            assert await stream.next_message() == ": keepalive"


@pytest.mark.asyncio
async def test_opening_the_stream_records_the_story_as_active(tmp_path) -> None:
    app = local_app(tmp_path)
    async with live_server(app) as base_url:
        await _create_story(base_url, "harbor")
        await _create_story(base_url, "mill")
        async with open_stream(base_url, "harbor") as stream:
            await stream.next_event()
            async with httpx.AsyncClient(base_url=base_url) as client:
                listed = await client.get("/api/stories")

    assert listed.json() == {"stories": ["harbor", "mill"], "active": "harbor"}


@pytest.mark.asyncio
async def test_the_stream_of_an_unknown_story_is_not_found(tmp_path) -> None:
    async with live_server(local_app(tmp_path)) as base_url:
        async with httpx.AsyncClient(base_url=base_url) as client:
            response = await client.get("/api/stories/missing/events")

    assert response.status_code == 404
    assert response.json()["detail"]


@pytest.mark.asyncio
async def test_each_user_sees_only_their_own_stream(tmp_path) -> None:
    writer = ScriptedWriter("Alice's reply.")
    app = multi_user_app(tmp_path, model=writer.model)
    async with live_server(app) as base_url:
        await _create_story(base_url, "harbor", ALICE)
        async with httpx.AsyncClient(base_url=base_url) as client:
            anonymous = await client.get("/api/stories/harbor/events")
            bob = await client.get("/api/stories/harbor/events", headers=BOB)
        async with open_stream(base_url, "harbor", ALICE) as alice_stream:
            assert (await alice_stream.next_event()).snapshot().story == "harbor"
            await _post(base_url, "/api/stories/harbor/prompts", {"text": "Begin."}, ALICE)
            messages = await alice_stream.read_until("turn_finished")

    assert anonymous.status_code == 401
    assert bob.status_code == 404
    assert messages[-1].room_event().outcome == "completed"
    assert await (await FileWorkspace(root=tmp_path / "data" / "users" / "alice").open_story(name="harbor")).read_message_history()
