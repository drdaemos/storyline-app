"""Abstract workspace interface and application factory."""

from storyline.workspace.agenda import render_agenda, replace_agenda, update_agenda_item
from storyline.workspace.contracts import (
    AgendaError,
    AgendaItem,
    AgendaStatus,
    ConversationHistoryError,
    LoreEditError,
    LoreFile,
    Story,
    StorySelectionError,
    TextEdit,
    TextEditError,
    Workspace,
    WorkspaceConfigurationError,
    WorkspaceEditError,
)
from storyline.workspace.factory import WORKSPACE_ENV_VAR, open_workspace
from storyline.workspace.library import StoryLibrary

__all__ = [
    "WORKSPACE_ENV_VAR",
    "AgendaError",
    "AgendaItem",
    "AgendaStatus",
    "ConversationHistoryError",
    "LoreEditError",
    "LoreFile",
    "Story",
    "StoryLibrary",
    "StorySelectionError",
    "TextEdit",
    "TextEditError",
    "Workspace",
    "WorkspaceConfigurationError",
    "WorkspaceEditError",
    "open_workspace",
    "render_agenda",
    "replace_agenda",
    "update_agenda_item",
]
