"""Workspace interface and shared value types."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
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
    summary: str | None
    keywords: str | None


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
