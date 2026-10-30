"""The room protocol: what any interface can ask of a story's room, and what the room tells it.

Every interface (terminal, web) offers each ``Operation`` and renders each ``RoomEvent`` and the ``RoomSnapshot``.
The models are plain data, so the same values cross a process boundary unchanged. Each interface has a parity test
(``tests/test_tui_parity.py``, ``tests/test_web_parity.py``, ``frontend/src/protocol/parity.test.ts``) that fails
when it misses an operation or an event.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from storyline.workspace import AgendaItem


class Operation(StrEnum):
    """Everything a person can do in Storyline, whichever interface they use."""

    LIST_STORIES = "list_stories"
    LIST_PRESETS = "list_presets"
    """The kinds of story a new story can be created as."""
    CREATE_STORY = "create_story"
    """Create a story as one of the presets; the default preset when none is named."""
    OPEN_STORY = "open_story"
    SEND_PROMPT = "send_prompt"
    """Start a turn; while the writer works, queue the prompt for its next step."""
    INTERRUPT = "interrupt"
    SET_MODEL = "set_model"
    UNDO_LAST_TURN = "undo_last_turn"
    CLEAR_CONVERSATION = "clear_conversation"
    READ_SCRIPT = "read_script"
    LIST_LORE = "list_lore"
    READ_LORE = "read_lore"


class _Data(BaseModel):
    model_config = ConfigDict(frozen=True)


# Conversation entries


class MessageEntry(_Data):
    """Something the user or the writer said."""

    kind: Literal["message"] = "message"
    role: Literal["user", "writer"]
    text: str
    reply_id: str | None = None
    """Set while the writer is still streaming this reply; ``ReplyDelta`` events with the same id extend it."""


class ToolCallEntry(_Data):
    """A tool the writer used, with its result once there is one."""

    kind: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    arguments: str
    result: str | None = None
    outcome: str = "working"
    """``working`` until the tool returns; then the tool's outcome, ``retry`` or ``interrupted``."""
    sealed: bool = False
    """The call reads or changes what is hidden from the user; interfaces fold its arguments and result behind a spoiler warning."""


type Entry = Annotated[MessageEntry | ToolCallEntry, Field(discriminator="kind")]

type Activity = Literal["idle", "thinking", "writing", "using_tool"]


# Events


class UserMessageAdded(_Data):
    """A prompt from the user entered the conversation: sent to start a turn, or read by the writer from the queue."""

    type: Literal["user_message_added"] = "user_message_added"
    text: str


class ReplyStarted(_Data):
    """The writer began a reply."""

    type: Literal["reply_started"] = "reply_started"
    reply_id: str


class ReplyDelta(_Data):
    """More text for a reply that has started."""

    type: Literal["reply_delta"] = "reply_delta"
    reply_id: str
    text: str


class ReplyFinished(_Data):
    """A reply is complete."""

    type: Literal["reply_finished"] = "reply_finished"
    reply_id: str


class ToolCallStarted(_Data):
    """The writer called a tool."""

    type: Literal["tool_call_started"] = "tool_call_started"
    tool_call_id: str
    tool_name: str
    arguments: str
    sealed: bool = False
    """See ``ToolCallEntry.sealed``."""


class ToolCallFinished(_Data):
    """A tool call returned."""

    type: Literal["tool_call_finished"] = "tool_call_finished"
    tool_call_id: str
    result: str
    outcome: str
    sealed: bool = False
    """See ``ToolCallEntry.sealed``."""


class ActivityChanged(_Data):
    """What the writer is doing now; ``idle`` means it is the user's move."""

    type: Literal["activity_changed"] = "activity_changed"
    activity: Activity
    tool_name: str | None = None


class QueueChanged(_Data):
    """The prompts sent while the writer works that it has not read yet."""

    type: Literal["queue_changed"] = "queue_changed"
    prompts: tuple[str, ...]


class AgendaChanged(_Data):
    """The agenda as it is now."""

    type: Literal["agenda_changed"] = "agenda_changed"
    items: tuple[AgendaItem, ...]


class ClockView(_Data):
    """A clock as the user sees it: what is building and how far along it is."""

    id: str
    name: str
    segments: int
    filled: int


class ClocksChanged(_Data):
    """The story's clocks as they are now: the visible ones, and how many more are hidden."""

    type: Literal["clocks_changed"] = "clocks_changed"
    clocks: tuple[ClockView, ...]
    hidden: int = 0


class StoryFilesChanged(_Data):
    """The writer changed the story's files; an interface showing them should read them again."""

    type: Literal["story_files_changed"] = "story_files_changed"
    script: bool = False
    lore: bool = False


class TurnFinished(_Data):
    """The writer's turn ended."""

    type: Literal["turn_finished"] = "turn_finished"
    outcome: Literal["completed", "interrupted", "failed"]
    error: str | None = None


class ConversationReplaced(_Data):
    """The conversation changed as a whole (undo, clear); show these entries instead of what was shown."""

    type: Literal["conversation_replaced"] = "conversation_replaced"
    entries: tuple[Entry, ...]
    hidden_entries: int = 0


class DraftRestored(_Data):
    """Text handed back to the user's input: an undone prompt, or queued prompts an interrupted turn never read."""

    type: Literal["draft_restored"] = "draft_restored"
    text: str


class ModelChanged(_Data):
    """The story's model changed; a running turn finishes on the previous one."""

    type: Literal["model_changed"] = "model_changed"
    model_name: str


class Notice(_Data):
    """Something the room has to tell the user that is not part of the conversation."""

    type: Literal["notice"] = "notice"
    level: Literal["info", "error"]
    text: str


EVENT_TYPES: tuple[type[_Data], ...] = (
    UserMessageAdded,
    ReplyStarted,
    ReplyDelta,
    ReplyFinished,
    ToolCallStarted,
    ToolCallFinished,
    ActivityChanged,
    QueueChanged,
    AgendaChanged,
    ClocksChanged,
    StoryFilesChanged,
    TurnFinished,
    ConversationReplaced,
    DraftRestored,
    ModelChanged,
    Notice,
)

type RoomEvent = Annotated[
    UserMessageAdded
    | ReplyStarted
    | ReplyDelta
    | ReplyFinished
    | ToolCallStarted
    | ToolCallFinished
    | ActivityChanged
    | QueueChanged
    | AgendaChanged
    | ClocksChanged
    | StoryFilesChanged
    | TurnFinished
    | ConversationReplaced
    | DraftRestored
    | ModelChanged
    | Notice,
    Field(discriminator="type"),
]


# Snapshot


class ArchivedConversation(_Data):
    """Saved history that could not be read and was moved aside when the story was opened."""

    reason: str
    archive_name: str


class RoomSnapshot(_Data):
    """Everything an interface needs to draw a room as it is right now; events carry it forward from there."""

    story: str
    preset: str
    """The id of the preset the story runs as, e.g. ``co-writing``."""
    model_name: str
    model_from_story: bool
    """Whether the model is the one remembered in the story rather than the default."""
    entries: tuple[Entry, ...]
    hidden_entries: int
    """Older entries left out of ``entries``."""
    agenda: tuple[AgendaItem, ...]
    agenda_error: str | None = None
    clocks: tuple[ClockView, ...] = ()
    """The visible clocks; see ``ClocksChanged``."""
    hidden_clocks: int = 0
    activity: Activity = "idle"
    tool_name: str | None = None
    queue: tuple[str, ...] = ()
    archived_conversation: ArchivedConversation | None = None


def event_type_name(event_type: type[_Data]) -> str:
    """Return the wire name of an event class, e.g. ``reply_delta``."""
    return str(event_type.model_fields["type"].default)


def protocol_schema() -> dict[str, object]:
    """Describe the protocol for interfaces written in other languages."""
    return {
        "operations": [operation.value for operation in Operation],
        "events": [event_type_name(event_type) for event_type in EVENT_TYPES],
        "event_schema": TypeAdapter(RoomEvent).json_schema(),
        "snapshot_schema": RoomSnapshot.model_json_schema(),
    }
