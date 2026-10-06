"""Abstract workspace interface and application factory."""

from storyline.workspace.contracts import (
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
]
