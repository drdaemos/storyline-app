"""Workspace interface and shared value types."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_ai.messages import ModelMessage


class WorkspaceConfigurationError(ValueError):
    """Raised when the workspace has not been configured."""


class WorkspaceEditError(ValueError):
    """Raised when a requested workspace change is invalid."""


class TextEditError(WorkspaceEditError):
    """Raised when an edit cannot be located in, or applied to, a document."""


class LoreEditError(WorkspaceEditError):
    """Raised when a lore file cannot be read or changed."""


class AgendaError(WorkspaceEditError):
    """Raised when the agenda cannot be read, or a requested agenda change is invalid."""


class ClockError(WorkspaceEditError):
    """Raised when the clocks cannot be read, or a requested clock change is invalid."""


class RollLogError(WorkspaceEditError):
    """Raised when the log of oracle rolls cannot be read."""


class ConversationHistoryError(ValueError):
    """Raised when saved conversation history cannot be restored."""


class StorySelectionError(ValueError):
    """Raised when a story cannot be created or opened under the requested name."""


class StorySetupError(StorySelectionError):
    """Raised when a story's setup record (story.json) cannot be read."""


@dataclass(frozen=True)
class TextEdit:
    """A completed change to the script or a lore file."""

    filename: str
    original_length: int
    new_length: int
    snippet: str
    """The changed text with some surrounding context, as it now reads."""


@dataclass(frozen=True)
class LoreFile:
    """A discoverable Markdown lore file and its searchable metadata."""

    filename: str
    """Relative to the story directory with ``/`` separators: ``city.md``, or ``sealed/vera.md`` for a sealed file."""
    summary: str | None
    keywords: str | None
    sealed: bool = False
    """Kept in ``sealed/``: read by the writer, hidden from the user unless they choose to peek."""


type AgendaStatus = Literal["open", "working", "waiting", "settled", "dropped"]


def _new_agenda_id() -> str:
    return uuid4().hex[:8]


class AgendaItem(BaseModel):
    """One thing the writer and the user still have to work through, or have worked through."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=_new_agenda_id, min_length=1)
    title: str = Field(min_length=1)
    status: AgendaStatus = "open"
    outcome: str = ""
    """The decision in a few words, once the item is settled."""


class Clock(BaseModel):
    """Something that builds over time in the story, filled one segment at a time."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=_new_agenda_id, min_length=1)
    name: str = Field(min_length=1)
    segments: int = Field(ge=2, le=12)
    filled: int = Field(default=0, ge=0)
    """Never more than ``segments``; a clock is full when they are equal."""
    visible: bool
    """Whether the user sees it; a hidden clock belongs to what is sealed."""
    when_full: str = ""
    """What happens when the clock fills, as the writer means it to land."""

    @model_validator(mode="after")
    def _filled_within_segments(self) -> Self:
        if self.filled > self.segments:
            raise ValueError(f"A clock of {self.segments} segments cannot have {self.filled} filled.")
        return self

    @property
    def full(self) -> bool:
        return self.filled == self.segments


class Roll(BaseModel):
    """One oracle roll: the question, the odds it was rolled at and what came up."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1)
    odds: str
    """The name of the odds the roll was made at, e.g. ``likely``."""
    die: int = Field(ge=1, le=100)
    answer: Literal["yes", "no"]
    strong: bool = False
    at: datetime
    """When the roll was made."""


class StorySetup(BaseModel):
    """What kind of story this is: the preset it was created with and the mechanics switched on."""

    model_config = ConfigDict(frozen=True)

    preset: str = "co-writing"
    mechanics: tuple[str, ...] = ()


class Story(Protocol):
    """One self-contained story package: its script, lore and conversation history."""

    @property
    def name(self) -> str:
        """Return the story's name within its workspace."""

    async def read_script(self) -> str:
        """Return the current contents of ``script.md``."""

    async def append_script(self, *, text: str) -> TextEdit:
        """Add text to the end of the script."""

    async def replace_in_script(self, *, find: str, replace: str) -> TextEdit:
        """Replace the one passage of the script that matches ``find``."""

    async def list_lore(self) -> tuple[LoreFile, ...]:
        """Return every Markdown lore file with its summary and keywords."""

    async def read_lore(self, *, filename: str) -> str:
        """Return the full text of one Markdown lore file."""

    async def write_lore(self, *, filename: str, content: str) -> TextEdit:
        """Create a lore file or replace all of its content."""

    async def append_lore(self, *, filename: str, text: str) -> TextEdit:
        """Add text to the end of an existing lore file."""

    async def replace_in_lore(self, *, filename: str, find: str, replace: str) -> TextEdit:
        """Replace the one passage of a lore file that matches ``find``."""

    async def delete_lore(self, *, filename: str) -> None:
        """Remove a lore file."""

    async def read_agenda(self) -> tuple[AgendaItem, ...]:
        """Return the agenda in order; empty when none has been written."""

    async def write_agenda(self, *, items: Sequence[AgendaItem]) -> None:
        """Replace the whole agenda."""

    async def read_clocks(self) -> tuple[Clock, ...]:
        """Return the story's clocks in order; empty when there are none. Raise ``ClockError`` when they are unreadable."""

    async def change_clocks(self, *, change: Callable[[tuple[Clock, ...]], Sequence[Clock]]) -> tuple[Clock, ...]:
        """Read, change and write the clocks as one step, so concurrent changes never overwrite each other."""

    async def read_rolls(self) -> tuple[Roll, ...]:
        """Return the logged oracle rolls, newest first; empty when there are none. Raise ``RollLogError`` when the log is unreadable."""

    async def change_rolls(self, *, change: Callable[[tuple[Roll, ...]], Sequence[Roll]]) -> tuple[Roll, ...]:
        """Read, change and write the roll log as one step, so concurrent rolls never overwrite each other."""

    async def change_agenda(self, *, change: Callable[[tuple[AgendaItem, ...]], Sequence[AgendaItem]]) -> tuple[AgendaItem, ...]:
        """Read, change and write the agenda as one step, so concurrent changes never overwrite each other."""

    async def read_model_name(self) -> str | None:
        """Return the model this story was last worked on with, or None when it has not been used yet."""

    async def write_model_name(self, *, model_name: str) -> None:
        """Remember the model this story is being worked on with."""

    async def read_setup(self) -> StorySetup:
        """Return the story's setup record; a story without one is a default co-written story. Raise ``StorySetupError`` when it is unreadable."""

    async def write_setup(self, *, setup: StorySetup) -> None:
        """Record the story's setup."""

    async def read_message_history(self) -> list[ModelMessage]:
        """Return the complete persisted Pydantic AI conversation history."""

    async def archive_message_history(self) -> str:
        """Move unreadable saved history aside and return where it went."""

    async def write_message_history(self, *, message_history: list[ModelMessage]) -> None:
        """Persist the complete Pydantic AI conversation history."""


class Workspace(Protocol):
    """Storage interface for the collection of stories in one workspace."""

    async def list_stories(self) -> tuple[str, ...]:
        """Return the names of every story, sorted."""

    async def create_story(self, *, name: str) -> Story:
        """Create a new, empty story."""

    async def open_story(self, *, name: str) -> Story:
        """Open an existing story."""

    async def read_active_story(self) -> str | None:
        """Return the name of the story that was active last, if one was recorded."""

    async def write_active_story(self, *, name: str) -> None:
        """Record the story that is active now."""
