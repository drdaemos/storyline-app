"""Playing a scenario against the writer agent and recording what each turn changed."""

import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent
from pydantic_ai.messages import BaseToolCallPart, ModelMessage, ModelResponse
from pydantic_ai.models import Model

from storyline.agent import WritingSession
from storyline.evals.scenarios import Scenario
from storyline.presets import BUNDLED_PRESETS, DEFAULT_PRESET_ID, setup_for
from storyline.registry import MECHANICS
from storyline.workspace import Story
from storyline.workspace.file_story import FileStory
from storyline.workspace.text_edit import paragraphs


class ToolCallRecord(BaseModel):
    """One tool call the agent made, including native tools such as web search."""

    model_config = ConfigDict(frozen=True)

    name: str
    arguments: str


class TurnRecord(BaseModel):
    """One user message, the agent's reply, and the story files before and after the turn."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    reply: str
    tool_calls: tuple[ToolCallRecord, ...]
    script_before: str
    script_after: str
    lore_before: dict[str, str]
    lore_after: dict[str, str]
    input_tokens: int
    output_tokens: int
    requests: int

    @property
    def new_prose(self) -> str:
        """Paragraphs of script.md that this turn added or rewrote."""
        before = {paragraph.text for paragraph in paragraphs(self.script_before)}
        return "\n\n".join(paragraph.text for paragraph in paragraphs(self.script_after) if paragraph.text not in before)

    @property
    def changed_lore(self) -> tuple[str, ...]:
        """Lore files this turn created, changed or deleted."""
        names = sorted(set(self.lore_before) | set(self.lore_after))
        return tuple(name for name in names if self.lore_before.get(name) != self.lore_after.get(name))


class ScenarioRun(BaseModel):
    """Everything one run of a scenario produced, saved for later checks and comparisons."""

    model_config = ConfigDict(frozen=True)

    case_name: str
    scenario: Scenario
    model_name: str
    prompt_version: str
    turns: tuple[TurnRecord, ...]
    preset: str = DEFAULT_PRESET_ID
    """The preset the story ran as, read from its setup after the seed was copied."""

    @property
    def script(self) -> str:
        return self.turns[-1].script_after

    @property
    def lore(self) -> dict[str, str]:
        return self.turns[-1].lore_after


class ScenarioRunner:
    """Runs scenarios against one agent and model, each in its own story directory."""

    def __init__(self, agent: Agent[Story, str], *, model: Model | str, seeds_dir: Path) -> None:
        self._agent = agent
        self._model = model
        self._seeds_dir = seeds_dir

    async def run(self, scenario: Scenario, story_dir: Path) -> tuple[TurnRecord, ...]:
        """Play every turn in a fresh copy of the scenario's seed story and return what each turn did."""
        if scenario.seed is None:
            story_dir.mkdir(parents=True)
        else:
            shutil.copytree(self._seeds_dir / scenario.seed, story_dir)
        story = FileStory(story_dir)
        if scenario.seed is None and scenario.preset is not None:
            await story.write_setup(setup=setup_for(BUNDLED_PRESETS.get(scenario.preset), MECHANICS))

        session = await WritingSession.open(story=story, agent=self._agent, model=self._model, registry=MECHANICS)
        turns: list[TurnRecord] = []
        for turn in scenario.turns:
            script_before, lore_before = await _story_files(story)
            writing = session.turn(turn.prompt)
            await writing.run()
            if writing.error is not None:
                raise writing.error
            script_after, lore_after = await _story_files(story)
            usage = writing.usage
            turns.append(
                TurnRecord(
                    prompt=turn.prompt,
                    reply=writing.reply,
                    tool_calls=_tool_calls(writing.new_messages),
                    script_before=script_before,
                    script_after=script_after,
                    lore_before=lore_before,
                    lore_after=lore_after,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    requests=usage.requests,
                )
            )
        return tuple(turns)


async def story_preset(story_dir: Path) -> str:
    """The id of the preset the story in this directory runs as; co-writing when it records none."""
    return (await FileStory(story_dir).read_setup()).preset


async def _story_files(story: Story) -> tuple[str, dict[str, str]]:
    lore = {lore_file.filename: await story.read_lore(filename=lore_file.filename) for lore_file in await story.list_lore()}
    return await story.read_script(), lore


def _tool_calls(messages: list[ModelMessage]) -> tuple[ToolCallRecord, ...]:
    return tuple(
        ToolCallRecord(name=part.tool_name, arguments=part.args_as_json_str())
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, BaseToolCallPart)
    )
