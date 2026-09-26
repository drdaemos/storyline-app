"""Workspace interface and shared value types."""

from dataclasses import dataclass
from typing import Protocol

from pydantic_ai.messages import ModelMessage


class WorkspaceConfigurationError(ValueError):
    """Raised when the workspace has not been configured."""


class WorkspaceEditError(ValueError):
    """Raised when a requested workspace change is invalid."""


class TextEditError(WorkspaceEditError):
    """Raised when an edit cannot be located in, or applied to, a document."""


class LoreEditError(WorkspaceEditError):
    """Raised when a lore file cannot be read or changed."""


class ConversationHistoryError(ValueError):
    """Raised when saved conversation history cannot be restored."""


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


class ScriptWorkspace(Protocol):
    """Storage interface used by the writing agent and terminal UI."""

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

    async def read_message_history(self) -> list[ModelMessage]:
        """Return the complete persisted Pydantic AI conversation history."""

    async def archive_message_history(self) -> str:
        """Move unreadable saved history aside and return where it went."""

    async def write_message_history(self, *, message_history: list[ModelMessage]) -> None:
        """Persist the complete Pydantic AI conversation history."""
