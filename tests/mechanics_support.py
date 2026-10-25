"""Helpers for tests of the roleplay mechanics: a scripted writer that calls tools, and a story set up for a preset."""

import json
from collections.abc import AsyncIterator, Callable, Mapping
from pathlib import Path

from pydantic_ai import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from storyline.agent import TurnOutcome, WritingSession, create_writer_agent
from storyline.mechanics import Mechanic
from storyline.registry import MECHANICS
from storyline.workspace import StorySetup
from storyline.workspace.file_story import FileStory

LORE = "---\nsummary: {summary}\nkeywords: k\n---\nBody.\n"

type ToolCall = tuple[str, dict[str, object]]


def tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    """Every tool result in the messages, in order."""
    return [part for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, ToolReturnPart)]


def user_prompts(messages: list[ModelMessage]) -> list[str]:
    """The text of every user prompt part in the messages, in order."""
    contents = [part.content for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, UserPromptPart)]
    return [str(item) for content in contents for item in ([content] if isinstance(content, str) else content)]


def writer_calling(*calls: ToolCall, outputs: Callable[[list[ModelMessage], AgentInfo], ModelResponse] | None = None) -> FunctionModel:
    """A writer that makes the given tool calls in order, one per request, then says it is done.

    A request that asks for structured output (a reviewer sharing this model) goes to ``outputs`` when given.
    """

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if info.output_tools and outputs is not None:
            return outputs(messages, info)
        made = len(tool_returns(messages))
        if made < len(calls):
            name, arguments = calls[made]
            return ModelResponse(parts=[ToolCallPart(tool_name=name, args=arguments, tool_call_id=f"call-{made}")])
        return ModelResponse(parts=[TextPart(content="Done.")])

    return FunctionModel(respond)


def streaming_writer_calling(*calls: ToolCall) -> FunctionModel:
    """Like ``writer_calling`` for a room, which streams."""

    async def stream(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        made = len(tool_returns(messages))
        if made < len(calls):
            name, arguments = calls[made]
            yield {0: DeltaToolCall(name=name, json_args=json.dumps(arguments), tool_call_id=f"call-{made}")}
        else:
            yield "Done."

    return FunctionModel(stream_function=stream)


async def story_with(path: Path, preset: str = "roleplay", mechanics: tuple[str, ...] = ("persona", "sealed", "cast", "clocks", "oracle", "review")) -> FileStory:
    """A story on disk recorded as this preset with these mechanics, and a sealed file for the cast."""
    story = FileStory(path)
    await story.write_setup(setup=StorySetup(preset=preset, mechanics=mechanics))
    await story.write_lore(filename="sealed/vera.md", content=LORE.format(summary="What Vera wants."))
    return story


async def run_turn(story: FileStory, model: FunctionModel, prompt: str = "Go.", *, replacing: Mapping[str, Mechanic] | None = None) -> tuple[WritingSession, TurnOutcome | None, list[ToolReturnPart]]:
    """Run one turn of the writer on ``model``; ``replacing`` swaps registered mechanics for instances the test configured."""
    session = await WritingSession.open(story=story, agent=create_writer_agent(), model=model, registry={**MECHANICS, **(replacing or {})})
    turn = session.turn(prompt)
    await turn.run()
    return session, turn.outcome, tool_returns(turn.new_messages)
