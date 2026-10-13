"""One story's room: the conversation with the writer as every interface sees it.

A ``StoryRoom`` takes the operations a person can perform on an open story and tells its listeners what happened as
``RoomEvent`` values. It owns what used to live in an interface: the steering queue, the mapping from agent events
to conversation entries, and the state needed to draw the room at any moment (``snapshot``). An interface only
calls operations and renders events, so two interfaces on the same room cannot drift apart.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Self
from uuid import uuid4

from pydantic_ai import Agent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.models import Model

from storyline.agent import DEFAULT_MODEL_NAME, PromptDelivered, TurnEvent, TurnOutcome, WritingSession, WritingTurn
from storyline.agent.writer_tools import AGENDA_TOOL_NAMES, LORE_WRITING_TOOL_NAMES, SCRIPT_WRITING_TOOL_NAMES
from storyline.room.protocol import (
    Activity,
    ActivityChanged,
    AgendaChanged,
    ArchivedConversation,
    ConversationReplaced,
    DraftRestored,
    Entry,
    MessageEntry,
    ModelChanged,
    Notice,
    QueueChanged,
    ReplyDelta,
    ReplyFinished,
    ReplyStarted,
    RoomEvent,
    RoomSnapshot,
    StoryFilesChanged,
    ToolCallEntry,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    UserMessageAdded,
)
from storyline.room.transcript import tool_result_summary, transcript_entries
from storyline.workspace import AgendaError, AgendaItem, LoreFile, Story

logger = logging.getLogger(__name__)

RESTORED_ENTRY_LIMIT = 40
"""How many of a saved conversation's latest entries a snapshot carries."""

type Listener = Callable[[RoomEvent], Awaitable[None]]
type TaskSpawner = Callable[[Coroutine[None, None, None]], object]
"""Runs the room's turns in the background; an interface passes its own to keep them in its task lifecycle."""


class RoomBusyError(ValueError):
    """Raised when an operation needs the writer to be idle and it is working."""

    def __init__(self) -> None:
        super().__init__("The writer is working; wait or interrupt first.")


@dataclass
class _QueuedPrompt:
    """A prompt sent while the writer was working, waiting to be read."""

    text: str
    enqueue_id: str | None = None


@dataclass
class _LiveReply:
    """The reply the writer is streaming, and where it sits among the live entries."""

    reply_id: str
    index: int
    text: str = ""


class StoryRoom:
    """The operations on one open story and the events they cause."""

    def __init__(
        self,
        *,
        session: WritingSession,
        spawn: TaskSpawner | None = None,
        entry_limit: int = RESTORED_ENTRY_LIMIT,
    ) -> None:
        self._session = session
        self._spawn = spawn or self._spawn_task
        self._entry_limit = entry_limit
        self._listeners: list[Listener] = []
        self._tasks: set[asyncio.Task[None]] = set()
        self._busy = False
        self._idle = asyncio.Event()
        self._idle.set()
        self._turn: WritingTurn | None = None
        self._queue: list[_QueuedPrompt] = []
        self._activity: Activity = "idle"
        self._tool_name: str | None = None
        self._agenda: tuple[AgendaItem, ...] = ()
        self._agenda_error: str | None = None
        self._saved_entries: list[Entry] = transcript_entries(session.message_history)
        self._live_entries: list[Entry] = []
        """Entries of the running turn; the saved conversation catches up with them when the turn ends."""
        self._reply: _LiveReply | None = None
        self._tool_entries: dict[str, int] = {}

    @classmethod
    async def open(
        cls,
        *,
        story: Story,
        agent: Agent[Story, str],
        default_model_name: str = DEFAULT_MODEL_NAME,
        model: Model | str | None = None,
        spawn: TaskSpawner | None = None,
        entry_limit: int = RESTORED_ENTRY_LIMIT,
    ) -> Self:
        """Open a story's room: restore its conversation and read its agenda."""
        session = await WritingSession.open(story=story, agent=agent, default_model_name=default_model_name, model=model)
        room = cls(session=session, spawn=spawn, entry_limit=entry_limit)
        await room._read_agenda()
        return room

    # State

    @property
    def story(self) -> Story:
        return self._session.story

    @property
    def model_name(self) -> str:
        return self._session.model_name

    @property
    def busy(self) -> bool:
        """Whether the writer is working on a turn."""
        return self._busy

    def snapshot(self) -> RoomSnapshot:
        """Return the room as it is now, including whatever the running turn has produced so far."""
        entries = [*self._saved_entries, *self._live_entries]
        shown = entries[-self._entry_limit :]
        archived = self._session.archived_history
        return RoomSnapshot(
            story=self.story.name,
            model_name=self.model_name,
            model_from_story=self._session.model_from_story,
            entries=tuple(shown),
            hidden_entries=len(entries) - len(shown),
            agenda=self._agenda,
            agenda_error=self._agenda_error,
            activity=self._activity,
            tool_name=self._tool_name,
            queue=self._queued_texts(),
            archived_conversation=ArchivedConversation(reason=archived.reason, archive_name=archived.archive_name) if archived is not None else None,
        )

    def add_listener(self, listener: Listener) -> Callable[[], None]:
        """Call ``listener`` with every event from now on; the returned function stops it."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    async def wait_until_idle(self) -> None:
        """Return once no turn is running."""
        await self._idle.wait()

    # Operations

    async def send_prompt(self, text: str) -> None:
        """Start a turn on ``text``; while the writer works, queue it for the writer's next step instead."""
        if self._busy:
            self._queue.append(_QueuedPrompt(text=text))
            self._hand_over_queue()
            await self._emit(QueueChanged(prompts=self._queued_texts()))
            return
        self._busy = True
        self._idle.clear()
        self._turn = self._session.turn(text)
        await self._add_user_message(text)
        self._spawn(self._run_turns())

    def interrupt(self) -> None:
        """Stop the running turn; what the writer completed so far is kept."""
        if self._turn is not None:
            self._turn.cancel()

    async def set_model(self, model_name: str) -> None:
        """Use a model from the next turn on and remember it in the story."""
        await self._session.set_model(model_name)
        await self._emit(ModelChanged(model_name=model_name))

    async def undo_last_turn(self) -> bool:
        """Remove the last turn and hand its prompt back as a draft; False when there is nothing to undo.

        Only the conversation changes: whatever the writer wrote to the story's files in that turn stays.
        """
        self._require_idle()
        prompt = await self._session.undo_last_turn()
        if prompt is None:
            return False
        await self._replace_conversation()
        await self._emit(DraftRestored(text=prompt))
        return True

    async def clear_conversation(self) -> None:
        """Start a new conversation; the story's script and lore are unchanged."""
        self._require_idle()
        await self._session.clear()
        await self._replace_conversation()

    async def read_script(self) -> str:
        """Return the story text."""
        return await self.story.read_script()

    async def list_lore(self) -> tuple[LoreFile, ...]:
        """Return every lore file with its summary and keywords."""
        return await self.story.list_lore()

    async def read_lore(self, filename: str) -> str:
        """Return the full text of one lore file."""
        return await self.story.read_lore(filename=filename)

    # Turns

    async def _run_turns(self) -> None:
        """Run the prepared turn and the follow-up turns its unread prompts call for, then go idle."""
        try:
            while self._turn is not None:
                turn = self._turn
                await self._run_turn(turn)
                outcome = turn.outcome or TurnOutcome.FAILED
                self._end_turn()
                await self._refresh_agenda()
                await self._settle_queue(outcome)
                if self._turn is None:
                    # Announcing idle can take a while; prompts sent meanwhile are queued, so look once more before stopping.
                    await self._set_activity("idle")
                    await self._settle_queue(outcome)
        except asyncio.CancelledError:
            # The interface running this task is shutting down: leave the room consistent without telling anyone.
            self._end_turn()
            self._queue.clear()
            self._activity, self._tool_name = "idle", None
            raise
        finally:
            self._turn = None
            self._busy = False
            self._idle.set()

    async def _run_turn(self, turn: WritingTurn) -> None:
        await self._set_activity("thinking")
        self._hand_over_queue()
        async for event in turn.events():
            await self._handle(event)
        await self._finish_reply()
        outcome = turn.outcome or TurnOutcome.FAILED
        await self._emit(TurnFinished(outcome=outcome.value, error=str(turn.error) if turn.error is not None else None))

    def _end_turn(self) -> None:
        """Let the saved conversation take over from the entries the turn produced."""
        self._turn = None
        self._reply = None
        self._live_entries = []
        self._tool_entries = {}
        self._saved_entries = transcript_entries(self._session.message_history)

    async def _settle_queue(self, outcome: TurnOutcome) -> None:
        """Deal with prompts nobody read: after a completed turn they start the next one, otherwise they go back to the user."""
        while self._queue and self._turn is None:
            unread = "\n\n".join(queued.text for queued in self._queue)
            self._queue.clear()
            follow_up = outcome is TurnOutcome.COMPLETED
            if follow_up:
                self._turn = self._session.turn(unread)
            await self._emit(QueueChanged(prompts=()))
            if follow_up:
                await self._add_user_message(unread)
            else:
                await self._emit(DraftRestored(text=unread))

    async def _handle(self, event: TurnEvent) -> None:
        if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
            await self._set_activity("writing")
            await self._finish_reply()
            await self._extend_reply(event.part.content)
        elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
            await self._extend_reply(event.delta.content_delta)
        elif isinstance(event, FunctionToolCallEvent):
            await self._finish_reply()
            await self._set_activity("using_tool", event.part.tool_name)
            entry = ToolCallEntry(tool_call_id=event.part.tool_call_id, tool_name=event.part.tool_name, arguments=event.part.args_as_json_str())
            self._tool_entries[entry.tool_call_id] = len(self._live_entries)
            self._live_entries.append(entry)
            await self._emit(ToolCallStarted(tool_call_id=entry.tool_call_id, tool_name=entry.tool_name, arguments=entry.arguments))
        elif isinstance(event, FunctionToolResultEvent):
            await self._set_activity("thinking")
            result, outcome = tool_result_summary(event.part)
            index = self._tool_entries.get(event.part.tool_call_id)
            if index is not None:
                self._live_entries[index] = self._live_entries[index].model_copy(update={"result": result, "outcome": outcome})
            await self._emit(ToolCallFinished(tool_call_id=event.part.tool_call_id, result=result, outcome=outcome))
            await self._after_tool(event.part.tool_name, outcome)
        elif isinstance(event, PromptDelivered):
            await self._deliver(event.enqueue_id)

    async def _after_tool(self, tool_name: str | None, outcome: str) -> None:
        """Tell listeners what a finished tool changed."""
        if tool_name in AGENDA_TOOL_NAMES:
            await self._refresh_agenda()
        script = outcome == "success" and tool_name in SCRIPT_WRITING_TOOL_NAMES
        lore = outcome == "success" and tool_name in LORE_WRITING_TOOL_NAMES
        if script or lore:
            await self._emit(StoryFilesChanged(script=script, lore=lore))

    async def _extend_reply(self, text: str) -> None:
        if self._reply is None:
            self._reply = _LiveReply(reply_id=uuid4().hex, index=len(self._live_entries))
            self._live_entries.append(MessageEntry(role="writer", text="", reply_id=self._reply.reply_id))
            await self._emit(ReplyStarted(reply_id=self._reply.reply_id))
        if text:
            reply = self._reply
            reply.text += text
            self._live_entries[reply.index] = self._live_entries[reply.index].model_copy(update={"text": reply.text})
            await self._emit(ReplyDelta(reply_id=reply.reply_id, text=text))

    async def _finish_reply(self) -> None:
        reply, self._reply = self._reply, None
        if reply is not None:
            self._live_entries[reply.index] = self._live_entries[reply.index].model_copy(update={"reply_id": None})
            await self._emit(ReplyFinished(reply_id=reply.reply_id))

    async def _add_user_message(self, text: str) -> None:
        self._live_entries.append(MessageEntry(role="user", text=text))
        await self._emit(UserMessageAdded(text=text))

    # Steering queue

    def _hand_over_queue(self) -> None:
        """Hand queued prompts to the running turn, which reads them at the writer's next model request."""
        if self._turn is not None:
            for queued in self._queue:
                if queued.enqueue_id is None:
                    queued.enqueue_id = self._turn.enqueue(queued.text)

    async def _deliver(self, enqueue_id: str) -> None:
        delivered = [queued for queued in self._queue if queued.enqueue_id == enqueue_id]
        for queued in delivered:
            self._queue.remove(queued)
            await self._finish_reply()
            await self._add_user_message(queued.text)
        await self._emit(QueueChanged(prompts=self._queued_texts()))

    def _queued_texts(self) -> tuple[str, ...]:
        return tuple(queued.text for queued in self._queue)

    # Helpers

    def _require_idle(self) -> None:
        if self._busy:
            raise RoomBusyError

    async def _replace_conversation(self) -> None:
        self._saved_entries = transcript_entries(self._session.message_history)
        shown = self._saved_entries[-self._entry_limit :]
        await self._emit(ConversationReplaced(entries=tuple(shown), hidden_entries=len(self._saved_entries) - len(shown)))

    async def _read_agenda(self) -> bool:
        """Read the agenda into the room's state and return whether it changed."""
        before = (self._agenda, self._agenda_error)
        try:
            self._agenda, self._agenda_error = await self.story.read_agenda(), None
        except AgendaError as error:
            self._agenda, self._agenda_error = (), str(error)
        return (self._agenda, self._agenda_error) != before

    async def _refresh_agenda(self) -> None:
        if not await self._read_agenda():
            return
        if self._agenda_error is not None:
            await self._emit(Notice(level="error", text=self._agenda_error))
        await self._emit(AgendaChanged(items=self._agenda))

    async def _set_activity(self, activity: Activity, tool_name: str | None = None) -> None:
        if (activity, tool_name) == (self._activity, self._tool_name):
            return
        self._activity, self._tool_name = activity, tool_name
        await self._emit(ActivityChanged(activity=activity, tool_name=tool_name))

    async def _emit(self, event: RoomEvent) -> None:
        for listener in tuple(self._listeners):
            try:
                await listener(event)
            except Exception:
                logger.exception("A room listener failed on %s", event.type)

    def _spawn_task(self, turns: Coroutine[None, None, None]) -> None:
        task = asyncio.get_running_loop().create_task(turns)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
