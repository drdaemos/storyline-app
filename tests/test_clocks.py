"""Tests for clocks: storage, the pure operations, the writer's tools, the snapshot section and what the room tells interfaces."""

import pytest
from pydantic import ValidationError

from storyline.agent import TurnOutcome, create_writer_agent, tool_call_is_sealed, turn_prompt
from storyline.mechanics import resolve_mechanics
from storyline.mechanics.clocks import CLOCK_TOOL_NAMES
from storyline.registry import MECHANICS
from storyline.room import ClocksChanged, ClockView, Notice, RoomEvent, StoryRoom, ToolCallStarted
from storyline.workspace import Clock, ClockError, remove_clock, render_clocks, set_clock, tick_clock
from storyline.workspace.file_story import CLOCKS_FILENAME, FileStory
from tests.mechanics_support import run_turn, story_with, streaming_writer_calling, writer_calling


def _clock(**fields: object) -> Clock:
    values: dict[str, object] = {"name": "Suspicion", "segments": 6, "visible": True} | fields
    return Clock.model_validate(values)


# Storage


@pytest.mark.asyncio
async def test_clocks_round_trip_and_a_story_without_any_has_none(tmp_path) -> None:
    story = FileStory(tmp_path)
    assert await story.read_clocks() == ()

    clocks = (_clock(filled=2, when_full="She calls the guard."), _clock(name="The debt", visible=False))
    await story.change_clocks(change=lambda _: clocks)

    assert await FileStory(tmp_path).read_clocks() == clocks
    assert [path.name for path in tmp_path.iterdir()] == [CLOCKS_FILENAME]


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["not json", '{"name": "x"}', '[{"name": "x"}]', '[{"name": "x", "segments": 1, "visible": true}]', '[{"name": "x", "segments": 4, "filled": 5, "visible": true}]'])
async def test_an_invalid_clocks_file_is_reported_as_a_clock_error(tmp_path, content: str) -> None:
    (tmp_path / CLOCKS_FILENAME).write_text(content, encoding="utf-8")

    with pytest.raises(ClockError):
        await FileStory(tmp_path).read_clocks()


def test_a_clock_cannot_have_more_filled_than_segments() -> None:
    with pytest.raises(ValidationError):
        _clock(segments=4, filled=5)


# Operations


def test_creating_a_clock_adds_it_empty_with_an_id() -> None:
    clocks = set_clock((), name=" Suspicion ", segments=4, visible=False, when_full=" She leaves. ")

    [clock] = clocks
    assert (clock.name, clock.segments, clock.filled, clock.visible, clock.when_full) == ("Suspicion", 4, 0, False, "She leaves.")
    assert clock.id


def test_changing_a_clock_keeps_what_it_filled_within_its_new_size() -> None:
    clock = _clock(filled=5)

    [kept] = set_clock((clock,), name="Suspicion", segments=8, visible=True, when_full="", clock_id=clock.id)
    [clamped] = set_clock((clock,), name="Suspicion", segments=4, visible=False, when_full="", clock_id=clock.id)

    assert kept.filled == 5 and kept.id == clock.id
    assert clamped.filled == 4 and clamped.visible is False


@pytest.mark.parametrize("segments", [1, 13, 0, -3])
def test_a_clock_needs_two_to_twelve_segments(segments: int) -> None:
    with pytest.raises(ClockError, match="segments"):
        set_clock((), name="Suspicion", segments=segments, visible=True, when_full="")


def test_a_clock_needs_a_name_and_an_existing_id_to_change() -> None:
    with pytest.raises(ClockError, match="name"):
        set_clock((), name="  ", segments=4, visible=True, when_full="")
    with pytest.raises(ClockError, match="ghost"):
        set_clock((_clock(),), name="Suspicion", segments=4, visible=True, when_full="", clock_id="ghost")


def test_ticking_stays_between_empty_and_full_and_rolls_back_with_a_negative_number() -> None:
    clock = _clock(segments=4, filled=3)

    [full] = tick_clock((clock,), clock.id, by=5)
    [back] = tick_clock((full,), clock.id, by=-2)
    [empty] = tick_clock((back,), clock.id, by=-9)

    assert (full.filled, full.full) == (4, True)
    assert back.filled == 2
    assert empty.filled == 0


def test_ticking_by_nothing_or_an_unknown_clock_is_refused() -> None:
    clock = _clock()
    with pytest.raises(ClockError):
        tick_clock((clock,), clock.id, by=0)
    with pytest.raises(ClockError, match=clock.id):
        tick_clock((clock,), "ghost", by=1)


def test_removing_a_clock_leaves_the_others() -> None:
    first, second = _clock(name="First"), _clock(name="Second")

    assert remove_clock((first, second), first.id) == (second,)
    with pytest.raises(ClockError):
        remove_clock((first,), "ghost")


def test_rendering_lists_every_clock_with_its_id_and_hidden_ones_too() -> None:
    visible, hidden = _clock(name="Seen", filled=6, when_full="The bell rings."), _clock(name="Unseen", visible=False)

    rendered = render_clocks((visible, hidden))

    assert visible.id in rendered and hidden.id in rendered
    assert "6/6" in rendered and "0/6" in rendered
    assert "hidden" in rendered and "The bell rings." in rendered
    assert render_clocks(()).strip()


# The writer's tools


async def _clock_tool_results(tmp_path, *calls):
    story = await story_with(tmp_path)
    _, outcome, results = await run_turn(story, writer_calling(*calls))
    assert outcome is TurnOutcome.COMPLETED
    return story, results


@pytest.mark.asyncio
async def test_set_clock_creates_a_clock_and_lists_all_clocks_with_ids(tmp_path) -> None:
    story, [created] = await _clock_tool_results(tmp_path, ("set_clock", {"name": "Suspicion", "segments": 6, "visible": False, "when_full": "She calls the guard."}))

    [clock] = await story.read_clocks()
    assert (clock.name, clock.segments, clock.visible) == ("Suspicion", 6, False)
    assert clock.id in str(created.content) and "Suspicion" in str(created.content)


@pytest.mark.asyncio
async def test_set_clock_with_an_id_changes_that_clock(tmp_path) -> None:
    story = await story_with(tmp_path)
    clock = _clock(filled=5)
    await story.change_clocks(change=lambda _: (clock,))

    _, outcome, [result] = await run_turn(story, writer_calling(("set_clock", {"clock_id": clock.id, "name": "Suspicion", "segments": 4, "visible": True, "when_full": "x"})))

    [changed] = await story.read_clocks()
    assert outcome is TurnOutcome.COMPLETED and (changed.segments, changed.filled) == (4, 4)
    assert result.outcome == "success"


@pytest.mark.asyncio
async def test_ticking_reports_the_new_state_and_what_happens_when_it_fills(tmp_path) -> None:
    story = await story_with(tmp_path)
    clock = _clock(segments=3, filled=1, when_full="The guard raises the alarm.")
    await story.change_clocks(change=lambda _: (clock,))

    _, _, [partial, filled, rolled_back] = await run_turn(
        story,
        writer_calling(
            ("tick_clock", {"clock_id": clock.id, "reason": "She dawdled."}),
            ("tick_clock", {"clock_id": clock.id, "reason": "A roll went wrong.", "by": 5}),
            ("tick_clock", {"clock_id": clock.id, "reason": "A distraction.", "by": -1}),
        ),
    )

    assert "2/3" in str(partial.content) and "The guard raises the alarm." not in str(partial.content).split("\n")[0]
    assert "3/3" in str(filled.content) and "full" in str(filled.content).lower() and "The guard raises the alarm." in str(filled.content)
    assert "2/3" in str(rolled_back.content) and "It is full" not in str(rolled_back.content)
    assert (await story.read_clocks())[0].filled == 2


@pytest.mark.asyncio
async def test_a_bad_tick_fails_the_tool_and_not_the_turn(tmp_path) -> None:
    story = await story_with(tmp_path)

    _, outcome, [unknown, no_reason] = await run_turn(
        story, writer_calling(("tick_clock", {"clock_id": "ghost", "reason": "Because."}), ("tick_clock", {"clock_id": "ghost", "reason": " "}))
    )

    assert outcome is TurnOutcome.COMPLETED
    assert unknown.outcome == "failed" and "ghost" in str(unknown.content)
    assert no_reason.outcome == "failed"


@pytest.mark.asyncio
async def test_remove_clock_removes_it_and_lists_the_rest(tmp_path) -> None:
    story = await story_with(tmp_path)
    first, second = _clock(name="First"), _clock(name="Second")
    await story.change_clocks(change=lambda _: (first, second))

    _, _, [result] = await run_turn(story, writer_calling(("remove_clock", {"clock_id": first.id})))

    assert await story.read_clocks() == (second,)
    assert second.id in str(result.content) and first.id not in str(result.content)


@pytest.mark.asyncio
async def test_an_unreadable_clocks_file_fails_the_tool(tmp_path) -> None:
    story = await story_with(tmp_path)
    (tmp_path / CLOCKS_FILENAME).write_text("not json", encoding="utf-8")

    _, outcome, [result] = await run_turn(story, writer_calling(("set_clock", {"name": "Suspicion", "segments": 4, "visible": True, "when_full": ""})))

    assert outcome is TurnOutcome.COMPLETED and result.outcome == "failed"
    assert (tmp_path / CLOCKS_FILENAME).read_text(encoding="utf-8") == "not json"


# Snapshot and sealing


@pytest.mark.asyncio
async def test_the_snapshot_lists_every_clock_for_the_writer(tmp_path) -> None:
    story = await story_with(tmp_path)
    seen, hidden = _clock(name="Seen", filled=2, when_full="The bell rings."), _clock(name="Unseen", visible=False)
    await story.change_clocks(change=lambda _: (seen, hidden))
    mechanics = resolve_mechanics(["clocks"], MECHANICS)

    snapshot = str((await turn_prompt(story, "Go.", mechanics, registry=MECHANICS))[0])

    for clock in (seen, hidden):
        line = next(line for line in snapshot.splitlines() if clock.id in line)
        assert clock.name in line and f"{clock.filled}/{clock.segments}" in line
    assert "hidden" in next(line for line in snapshot.splitlines() if hidden.id in line)
    assert "The bell rings." in snapshot


@pytest.mark.asyncio
async def test_the_snapshot_says_so_when_the_clocks_are_unreadable(tmp_path) -> None:
    (tmp_path / CLOCKS_FILENAME).write_text("not json", encoding="utf-8")

    snapshot = str((await turn_prompt(FileStory(tmp_path), "Go.", resolve_mechanics(["clocks"], MECHANICS), registry=MECHANICS))[0])

    assert CLOCKS_FILENAME in snapshot


@pytest.mark.parametrize("tool_name", sorted(CLOCK_TOOL_NAMES))
def test_every_clock_tool_call_is_sealed(tool_name: str) -> None:
    assert tool_call_is_sealed(tool_name, {}, resolve_mechanics(["clocks"], MECHANICS)) is True
    assert tool_call_is_sealed(tool_name, {}, ()) is False


def test_the_clock_tool_names_are_the_tools_of_the_mechanic() -> None:
    toolset = MECHANICS["clocks"].toolset

    assert toolset is not None and set(toolset.tools) == CLOCK_TOOL_NAMES


def test_clocks_need_the_sealed_mechanic() -> None:
    assert [mechanic.id for mechanic in resolve_mechanics(["clocks"], MECHANICS)] == ["sealed", "clocks"]


# The room


class _Events:
    def __init__(self) -> None:
        self.events: list[RoomEvent] = []

    async def __call__(self, event: RoomEvent) -> None:
        self.events.append(event)

    def of[E](self, event_type: type[E]) -> list[E]:
        return [event for event in self.events if isinstance(event, event_type)]


async def _play(story: FileStory, *calls) -> tuple[StoryRoom, _Events]:
    room = await StoryRoom.open(story=story, agent=create_writer_agent(), model=streaming_writer_calling(*calls))
    events = _Events()
    room.add_listener(events)
    await room.send_prompt("Go.")
    await room.wait_until_idle()
    return room, events


@pytest.mark.asyncio
async def test_a_clock_tool_tells_listeners_the_visible_clocks_and_how_many_are_hidden(tmp_path) -> None:
    story = await story_with(tmp_path)
    room, events = await _play(
        story,
        ("set_clock", {"name": "The patrol", "segments": 4, "visible": True, "when_full": "They arrive."}),
        ("set_clock", {"name": "Her plan", "segments": 6, "visible": False, "when_full": "She strikes."}),
    )

    [visible] = [clock for clock in await story.read_clocks() if clock.visible]
    final = events.of(ClocksChanged)[-1]
    assert final.clocks == (ClockView(id=visible.id, name="The patrol", segments=4, filled=0),)
    assert final.hidden == 1
    snapshot = room.snapshot()
    assert (snapshot.clocks, snapshot.hidden_clocks) == (final.clocks, 1)
    assert all("Her plan" not in view.name for view in snapshot.clocks)
    assert all(started.sealed for started in events.of(ToolCallStarted))


@pytest.mark.asyncio
async def test_clocks_changed_is_sent_only_when_what_the_user_sees_changed(tmp_path) -> None:
    story = await story_with(tmp_path)
    hidden = _clock(name="Her plan", visible=False)
    await story.change_clocks(change=lambda _: (hidden,))

    room, events = await _play(story, ("tick_clock", {"clock_id": hidden.id, "reason": "Time passed."}))

    assert events.of(ClocksChanged) == []
    assert (room.snapshot().clocks, room.snapshot().hidden_clocks) == ((), 1)


@pytest.mark.asyncio
async def test_a_visible_tick_changes_the_filled_count_in_the_event(tmp_path) -> None:
    story = await story_with(tmp_path)
    clock = _clock(name="The patrol", segments=4)
    await story.change_clocks(change=lambda _: (clock,))

    room, events = await _play(story, ("tick_clock", {"clock_id": clock.id, "reason": "Time passed.", "by": 2}))

    assert events.of(ClocksChanged) == [ClocksChanged(clocks=(ClockView(id=clock.id, name="The patrol", segments=4, filled=2),), hidden=0)]
    assert room.snapshot().clocks[0].filled == 2


@pytest.mark.asyncio
async def test_a_failed_clock_tool_sends_nothing(tmp_path) -> None:
    story = await story_with(tmp_path)

    _, events = await _play(story, ("tick_clock", {"clock_id": "ghost", "reason": "Time passed."}))

    assert events.of(ClocksChanged) == []


@pytest.mark.asyncio
async def test_the_snapshot_carries_the_clocks_when_the_room_opens(tmp_path) -> None:
    story = await story_with(tmp_path)
    seen = _clock(name="The patrol", segments=4, filled=1)
    await story.change_clocks(change=lambda _: (seen, _clock(visible=False), _clock(visible=False)))

    snapshot = (await StoryRoom.open(story=story, agent=create_writer_agent())).snapshot()

    assert snapshot.clocks == (ClockView(id=seen.id, name="The patrol", segments=4, filled=1),)
    assert snapshot.hidden_clocks == 2


@pytest.mark.asyncio
async def test_a_story_without_clocks_has_none(tmp_path) -> None:
    snapshot = (await StoryRoom.open(story=FileStory(tmp_path), agent=create_writer_agent())).snapshot()

    assert (snapshot.clocks, snapshot.hidden_clocks) == ((), 0)


@pytest.mark.asyncio
async def test_clocks_that_become_unreadable_give_a_notice_and_empty_clocks(tmp_path) -> None:
    story = await story_with(tmp_path)
    await story.change_clocks(change=lambda _: (_clock(),))
    room = await StoryRoom.open(story=story, agent=create_writer_agent(), model=streaming_writer_calling(("set_clock", {"name": "x", "segments": 4, "visible": True, "when_full": ""})))
    events = _Events()
    room.add_listener(events)
    assert len(room.snapshot().clocks) == 1

    (tmp_path / CLOCKS_FILENAME).write_text("not json", encoding="utf-8")
    await room.send_prompt("Go.")
    await room.wait_until_idle()

    [notice] = events.of(Notice)
    assert notice.level == "error" and CLOCKS_FILENAME in notice.text
    assert events.of(ClocksChanged) == [ClocksChanged(clocks=(), hidden=0)]
    assert room.snapshot().clocks == ()
