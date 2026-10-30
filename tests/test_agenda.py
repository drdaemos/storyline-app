"""Tests for the agenda: storage, pure operations, the agent tools and the story snapshot."""

from collections.abc import Callable

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import create_writer_agent, story_snapshot, turn_prompt
from storyline.agent.story_context import AGENDA_CHARACTERS
from storyline.registry import MECHANICS
from storyline.workspace import AgendaError, AgendaItem, render_agenda, replace_agenda, update_agenda_item
from storyline.workspace.file_story import AGENDA_FILENAME, FileStory

type ModelFunction = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


def _call_tools_then_reply(*calls: ToolCallPart) -> tuple[ModelFunction, list[ToolReturnPart]]:
    results: list[ToolReturnPart] = []

    def model_response(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        results[:] = [part for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, ToolReturnPart)]
        if len(results) < len(calls):
            return ModelResponse(parts=[calls[len(results)]])
        return ModelResponse(parts=[TextPart(content="Done.")])

    return model_response, results


# Storage


@pytest.mark.asyncio
async def test_agenda_round_trips_and_is_empty_before_the_first_write(tmp_path) -> None:
    story = FileStory(tmp_path)
    assert await story.read_agenda() == ()

    items = (AgendaItem(title="The city", status="settled", outcome="Buffalo"), AgendaItem(title="Who she is"))
    await story.write_agenda(items=items)

    assert await FileStory(tmp_path).read_agenda() == items
    assert [path.name for path in tmp_path.iterdir()] == [AGENDA_FILENAME]


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["not json", '{"title": "x"}', '[{"id": "a"}]', '[{"title": "x", "status": "later"}]'])
async def test_invalid_agenda_file_is_reported_as_an_agenda_error(tmp_path, content: str) -> None:
    (tmp_path / AGENDA_FILENAME).write_text(content, encoding="utf-8")

    with pytest.raises(AgendaError):
        await FileStory(tmp_path).read_agenda()


# Operations


def test_agenda_items_get_short_distinct_ids_and_need_a_title() -> None:
    first, second = AgendaItem(title="One"), AgendaItem(title="Two")

    assert len(first.id) == 8
    assert first.id != second.id
    assert first.status == "open"
    assert first.outcome == ""
    with pytest.raises(ValueError):
        AgendaItem(title="")


def test_replacing_the_agenda_keeps_given_ids_and_rejects_duplicates() -> None:
    kept = AgendaItem(id="keep", title="The city", status="working")

    agenda = replace_agenda([AgendaItem(title="New first"), kept])

    assert agenda[1] == kept
    with pytest.raises(AgendaError, match="keep"):
        replace_agenda([kept, AgendaItem(id="keep", title="Again")])


def test_settling_requires_an_outcome() -> None:
    item = AgendaItem(id="a", title="The city")

    with pytest.raises(AgendaError, match="outcome"):
        replace_agenda([AgendaItem(id="a", title="The city", status="settled")])
    with pytest.raises(AgendaError, match="outcome"):
        update_agenda_item([item], "a", status="settled")

    (settled,) = update_agenda_item([item], "a", status="settled", outcome="Buffalo")
    assert (settled.status, settled.outcome, settled.title) == ("settled", "Buffalo", "The city")


def test_updating_one_item_leaves_the_others_and_unknown_ids_list_valid_ones() -> None:
    items = [AgendaItem(id="a", title="One"), AgendaItem(id="b", title="Two")]

    updated = update_agenda_item(items, "b", title="Second", status="waiting")

    assert updated[0] == items[0]
    assert (updated[1].title, updated[1].status) == ("Second", "waiting")
    with pytest.raises(AgendaError, match="a, b"):
        update_agenda_item(items, "zzz", status="dropped")


def test_rendered_agenda_lists_status_id_title_and_outcome() -> None:
    items = [
        AgendaItem(id="id3", title="The city", status="settled", outcome="Buffalo"),
        AgendaItem(id="id4", title="Who she is", status="waiting"),
    ]

    assert render_agenda(items) == "[settled] id3 The city — Buffalo\n[waiting] id4 Who she is"
    assert render_agenda([]) == "The agenda is empty."


# Agent tools


@pytest.mark.asyncio
async def test_writer_agent_sets_and_updates_the_agenda(tmp_path) -> None:
    story = FileStory(tmp_path)
    first = AgendaItem(title="The city")
    await story.write_agenda(items=[first])
    model, results = _call_tools_then_reply(
        ToolCallPart(
            tool_name="set_agenda",
            args={"items": [{"id": first.id, "title": "The city", "status": "working"}, {"title": "Who she is"}]},
        ),
        ToolCallPart(tool_name="update_agenda_item", args={"item_id": first.id, "status": "settled", "outcome": "Buffalo"}),
    )

    await create_writer_agent().run("Plan.", deps=story, model=FunctionModel(model))

    agenda = await story.read_agenda()
    assert [part.outcome for part in results] == ["success", "success"]
    assert [(item.title, item.status) for item in agenda] == [("The city", "settled"), ("Who she is", "open")]
    assert agenda[0].id == first.id
    assert agenda[0].outcome == "Buffalo"
    assert agenda[1].id in str(results[-1].content)
    assert "Buffalo" in str(results[-1].content)


@pytest.mark.asyncio
async def test_agenda_tools_return_invalid_changes_to_the_model(tmp_path) -> None:
    story = FileStory(tmp_path)
    item = AgendaItem(title="The city")
    await story.write_agenda(items=[item])
    model, results = _call_tools_then_reply(
        ToolCallPart(tool_name="update_agenda_item", args={"item_id": "nope", "status": "working"}),
        ToolCallPart(tool_name="update_agenda_item", args={"item_id": item.id, "status": "settled"}),
        ToolCallPart(tool_name="set_agenda", args={"items": [{"id": "a", "title": "One"}, {"id": "a", "title": "Two"}]}),
    )

    await create_writer_agent().run("Plan.", deps=story, model=FunctionModel(model))

    assert [part.outcome for part in results] == ["failed", "failed", "failed"]
    assert item.id in str(results[0].content)
    assert await story.read_agenda() == (item,)


# Snapshot


def test_story_snapshot_shows_the_agenda_and_collaboration_agreement() -> None:
    agenda = (
        AgendaItem(id="id1", title="The city", status="settled", outcome="Buffalo"),
        AgendaItem(id="id2", title="Who she is", status="waiting"),
    )

    snapshot = story_snapshot("Opening.", guides={"collaboration.md": "Options for main characters."}, agenda=agenda, registry=MECHANICS)

    assert "Options for main characters." in snapshot
    assert "id1" in snapshot
    assert "Buffalo" in snapshot
    assert "Who she is" in snapshot
    assert "collaboration.md does not exist yet." not in snapshot


def test_story_snapshot_marks_missing_collaboration_and_empty_agenda() -> None:
    snapshot = story_snapshot("Opening.", registry=MECHANICS)

    assert "collaboration.md does not exist yet." in snapshot
    assert "The agenda is empty." in snapshot


def test_story_snapshot_cuts_an_oversized_agenda() -> None:
    agenda = tuple(AgendaItem(title="x" * 200) for _ in range(40))

    snapshot = story_snapshot("Opening.", agenda=agenda, registry={})

    assert len(snapshot) < AGENDA_CHARACTERS + 1000


@pytest.mark.asyncio
async def test_turn_prompt_carries_the_agenda_and_collaboration_file(tmp_path) -> None:
    story = FileStory(tmp_path)
    await story.write_agenda(items=[AgendaItem(title="Tone of the book")])
    await story.write_lore(filename="collaboration.md", content="---\nsummary: Agreement.\nkeywords: trust\n---\nPropose, then wait.")

    snapshot = str((await turn_prompt(story, "Continue.", registry=MECHANICS))[0])

    assert "Tone of the book" in snapshot
    assert "Propose, then wait." in snapshot
    assert "keywords: trust" not in snapshot


@pytest.mark.asyncio
async def test_parallel_agenda_updates_all_land(tmp_path) -> None:
    story = FileStory(tmp_path)
    items = [AgendaItem(id=f"i{number}", title=f"Item {number}") for number in range(6)]
    await story.write_agenda(items=items)
    calls = [ToolCallPart(tool_name="update_agenda_item", args={"item_id": item.id, "status": "dropped"}) for item in items]

    def model_response(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(parts=calls)
        return ModelResponse(parts=[TextPart(content="Done.")])

    await create_writer_agent().run("Drop everything.", deps=story, model=FunctionModel(model_response))

    assert [item.status for item in await story.read_agenda()] == ["dropped"] * len(items)
