"""Abstract workspace interface and application factory."""

from storyline.workspace.contracts import (
    ConversationHistoryError,
    LoreEditError,
    LoreFile,
    ScriptWorkspace,
    TextEdit,
    TextEditError,
    WorkspaceConfigurationError,
    WorkspaceEditError,
)
from storyline.workspace.factory import WORKSPACE_ENV_VAR, open_workspace

__all__ = [
    "WORKSPACE_ENV_VAR",
    "ConversationHistoryError",
    "LoreEditError",
    "LoreFile",
    "ScriptWorkspace",
    "TextEdit",
    "TextEditError",
    "WorkspaceConfigurationError",
    "WorkspaceEditError",
    "open_workspace",
]
