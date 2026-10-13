"""One story's conversation with the writer agent.

A ``WritingSession`` owns what every interface needs around the agent: reading and repairing the saved conversation,
remembering the model in the story, and starting turns. A ``WritingTurn`` is one run of the agent: it builds the turn
prompt, streams the run's events, saves the conversation as it grows, and takes prompts typed while it works.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Self
from uuid import uuid4

from pydantic_ai import Agent, AgentRun
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import AgentStreamEvent, EnqueuedMessagesEvent, HandleResponseEvent, ModelMessage, ModelRequest, UserPromptPart
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage

from storyline.agent.history import actionable_history, without_last_turn
from storyline.agent.models import resolve_model, validate_model_name
from storyline.agent.story_context import turn_prompt
from storyline.agent.writer import DEFAULT_MODEL_NAME
from storyline.workspace import ConversationHistoryError, Story


@dataclass(frozen=True)
class PromptDelivered:
    """A prompt enqueued with ``WritingTurn.enqueue`` has reached the running agent."""

    enqueue_id: str


type TurnEvent = AgentStreamEvent | HandleResponseEvent | PromptDelivered


class TurnOutcome(StrEnum):
    """How a turn ended."""

    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclass(frozen=True)
class ArchivedHistory:
    """Saved history that could not be read and was moved aside."""

    reason: str
    archive_name: str


class SavedHistory:
    """The conversation as saved in a story: only what the next turn can run on."""

    def __init__(self, story: Story, messages: list[ModelMessage]) -> None:
        self._story = story
        self._messages = messages

    @property
    def messages(self) -> list[ModelMessage]:
        return list(self._messages)

    async def save(self, messages: list[ModelMessage]) -> None:
        """Save the conversation, dropping tool calls without results so an interrupted run never leaves the story broken."""
        self._messages = actionable_history(messages)
        await self._story.write_message_history(message_history=self._messages)


@dataclass
class _EnqueuedPrompt:
    id: str
    text: str
    delivery_id: str | None = None
    """The id the running agent reports once it has read the prompt."""
    delivered: bool = False


class WritingTurn:
    """One run of the writer agent on a prompt."""

    def __init__(
        self,
        *,
        story: Story,
        agent: Agent[Story, str],
        history: SavedHistory,
        prompt: str,
        model_name: str,
        model: Model | str | None,
    ) -> None:
        self._story = story
        self._agent = agent
        self._history = history
        self._prompt = prompt
        self._model_name = model_name
        self._model_override = model
        self._run: AgentRun[Story, str] | None = None
        self._cancel_requested = False
        self._enqueued: list[_EnqueuedPrompt] = []
        self._outcome: TurnOutcome | None = None
        self._error: Exception | None = None
        self._reply = ""
        self._new_messages: list[ModelMessage] = []
        self._usage = RunUsage()

    @property
    def outcome(self) -> TurnOutcome | None:
        """How the turn ended; ``None`` until it has."""
        return self._outcome

    @property
    def error(self) -> Exception | None:
        """The error that failed the turn."""
        return self._error

    @property
    def reply(self) -> str:
        """The agent's final reply, once the turn completed."""
        return self._reply

    @property
    def new_messages(self) -> list[ModelMessage]:
        """The messages this turn added, once it completed."""
        return list(self._new_messages)

    @property
    def usage(self) -> RunUsage:
        """What the completed turn used."""
        return self._usage

    @property
    def undelivered_prompts(self) -> tuple[str, ...]:
        """Prompts enqueued that the agent never read, in the order they were enqueued."""
        return tuple(prompt.text for prompt in self._enqueued if not prompt.delivered)

    def enqueue(self, text: str) -> str:
        """Hand the agent a prompt to read at its next model request, even before the run has started.

        Returns an id that the ``PromptDelivered`` event repeats once the agent has read it.
        """
        prompt = _EnqueuedPrompt(id=uuid4().hex, text=text)
        self._enqueued.append(prompt)
        self._hand_over(prompt)
        return prompt.id

    def cancel(self) -> None:
        """Stop the turn; what the agent completed so far is kept."""
        self._cancel_requested = True
        if self._run is not None:
            self._run.cancel()

    async def run(self) -> None:
        """Run the turn to its end without streaming; read ``outcome`` afterwards."""
        async for _ in self._drive(stream=False):
            pass

    def events(self) -> AsyncIterator[TurnEvent]:
        """Run the turn, yielding its events as they happen; read ``outcome`` once the iterator ends."""
        return self._drive(stream=True)

    async def _drive(self, *, stream: bool) -> AsyncIterator[TurnEvent]:
        run: AgentRun[Story, str] | None = None
        try:
            if self._model_override is None:
                await self._story.write_model_name(model_name=self._model_name)
            model = self._model_override if self._model_override is not None else resolve_model(self._model_name)
            prompt = await turn_prompt(self._story, self._prompt)
            previous = self._history.messages
            # The prompt is kept from the start, so a turn that dies before it saves anything still leaves what the user asked.
            await self._history.save([*previous, ModelRequest(parts=[UserPromptPart(content=prompt)])])
            async with self._agent.iter(prompt, deps=self._story, message_history=previous, model=model) as run:
                self._run = run
                for prompt in self._enqueued:
                    self._hand_over(prompt)
                if self._cancel_requested:
                    run.cancel()
                async for node in run:
                    if Agent.is_model_request_node(node) or Agent.is_call_tools_node(node):
                        if stream:
                            async with node.stream(run.ctx) as events:
                                async for event in events:
                                    yield self._translate(event)
                    if Agent.is_call_tools_node(node):
                        await self._history.save(run.all_messages())
                self._run = None
            await self._history.save(run.all_messages())
            self._reply = run.result.output if run.result is not None else ""
            self._new_messages = run.new_messages()
            self._usage = run.usage
            self._outcome = TurnOutcome.COMPLETED
        except RunCancelled as error:
            await self._history.save(error.all_messages())
            self._outcome = TurnOutcome.INTERRUPTED
        except asyncio.CancelledError:
            self._outcome = TurnOutcome.INTERRUPTED
            if run is not None:
                await self._history.save(run.all_messages())
            raise
        except Exception as error:
            self._error = error
            self._outcome = TurnOutcome.FAILED
            if run is not None:
                await self._history.save(run.all_messages())
        finally:
            self._run = None

    def _hand_over(self, prompt: _EnqueuedPrompt) -> None:
        if self._run is not None and prompt.delivery_id is None:
            prompt.delivery_id = self._run.enqueue(prompt.text)

    def _translate(self, event: AgentStreamEvent | HandleResponseEvent) -> TurnEvent:
        if isinstance(event, EnqueuedMessagesEvent):
            for prompt in self._enqueued:
                if prompt.delivery_id == event.enqueue_id:
                    prompt.delivered = True
                    return PromptDelivered(enqueue_id=prompt.id)
        return event


class WritingSession:
    """A story's conversation with the writer: its history, its model and the turns that extend them."""

    def __init__(
        self,
        *,
        story: Story,
        agent: Agent[Story, str],
        history: SavedHistory,
        model_name: str,
        model_from_story: bool,
        archived_history: ArchivedHistory | None,
        model: Model | str | None,
    ) -> None:
        self._story = story
        self._agent = agent
        self._history = history
        self._model_name = model_name
        self._model_override = model
        self.model_from_story = model_from_story
        """Whether the model was the one remembered in the story rather than the default."""
        self.archived_history = archived_history
        """Set when the saved history was unreadable and was moved aside to start a new conversation."""

    @classmethod
    async def open(
        cls,
        *,
        story: Story,
        agent: Agent[Story, str],
        default_model_name: str = DEFAULT_MODEL_NAME,
        model: Model | str | None = None,
    ) -> Self:
        """Open a story's conversation, repairing or archiving saved history that a run could not continue from.

        ``model`` runs turns on that model instead of the one ``model_name`` names, and the story does not remember it.
        """
        archived: ArchivedHistory | None = None
        try:
            saved = await story.read_message_history()
        except ConversationHistoryError as error:
            archived = ArchivedHistory(reason=str(error), archive_name=await story.archive_message_history())
            saved = []
        history = SavedHistory(story, actionable_history(saved))
        if history.messages != saved:
            await history.save(history.messages)
        remembered = await story.read_model_name()
        return cls(
            story=story,
            agent=agent,
            history=history,
            model_name=remembered or default_model_name,
            model_from_story=remembered is not None,
            archived_history=archived,
            model=model,
        )

    @property
    def story(self) -> Story:
        return self._story

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def message_history(self) -> list[ModelMessage]:
        """A copy of the saved conversation."""
        return self._history.messages

    async def set_model(self, model_name: str) -> None:
        """Use a model from the next turn on and remember it in the story; raise ``ModelNameError`` for a name no turn could run on."""
        validate_model_name(model_name)
        self._model_name = model_name
        await self._story.write_model_name(model_name=model_name)

    async def clear(self) -> None:
        """Start a new conversation; the story's script and lore are unchanged."""
        await self._history.save([])

    async def undo_last_turn(self) -> str | None:
        """Remove the last turn from the conversation and return what the user wrote in it, or None when there is none.

        Only the conversation changes: whatever the agent wrote to the story's files in that turn stays.
        """
        removed = without_last_turn(self._history.messages)
        if removed is None:
            return None
        await self._history.save(removed.history)
        return removed.prompt

    def turn(self, prompt: str) -> WritingTurn:
        """Prepare a turn on the current model and conversation; nothing runs until its events are consumed."""
        return WritingTurn(
            story=self._story,
            agent=self._agent,
            history=self._history,
            prompt=prompt,
            model_name=self._model_name,
            model=self._model_override,
        )
