"""Workspace interface and shared value types."""

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic_ai.messages import ModelMessage

LoreAction = Literal["append", "replace", "delete"]


class WorkspaceConfigurationError(ValueError):
    """Raised when the workspace has not been configured."""


class WorkspaceEditError(ValueError):
    """Raised when a requested workspace change is invalid."""


class ScriptEditError(WorkspaceEditError):
    """Raised when an edit does not fit within the current script."""


class LoreEditError(WorkspaceEditError):
    """Raised when a lore edit is invalid."""


class ConversationHistoryError(ValueError):
    """Raised when saved conversation history cannot be restored."""


@dataclass(frozen=True)
class ScriptEdit:
    """A completed range replacement in the script."""

    start_offset: int
    end_offset: int
    original_length: int
    new_length: int


@dataclass(frozen=True)
class LoreFile:
    """A discoverable Markdown lore file and its searchable metadata."""

    filename: str
    summary: str | None
    keywords: str | None


@dataclass(frozen=True)
class LoreEdit:
    """A completed edit to a lore file."""

    filename: str
    action: LoreAction
    original_length: int
    new_length: int


class ScriptWorkspace(Protocol):
    """Storage interface used by the writing agent and terminal UI."""

    async def read_script(self) -> str:
        """Return the current contents of ``script.md``."""

    async def apply_edit(
        self,
        *,
        start_offset: int,
        replacement: str,
        end_offset: int | None = None,
    ) -> ScriptEdit:
        """Replace a range, deriving its end from replacement length when omitted."""

    async def list_lore(self) -> tuple[LoreFile, ...]:
        """Return every Markdown lore file with its summary and keywords."""

    async def read_lore(self, *, filename: str) -> str:
        """Return the full text of one Markdown lore file."""

    async def edit_lore(
        self,
        *,
        filename: str,
        action: LoreAction,
        content: str | None = None,
        start_offset: int | None = None,
        end_offset: int | None = None,
    ) -> LoreEdit:
        """Append to, replace within, or delete a Markdown lore file."""

    async def read_message_history(self) -> list[ModelMessage]:
        """Return the complete persisted Pydantic AI conversation history."""

    async def write_message_history(self, *, message_history: list[ModelMessage]) -> None:
        """Persist the complete Pydantic AI conversation history."""
