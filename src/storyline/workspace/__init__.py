"""Abstract workspace interface and application factory."""

from storyline.workspace.contracts import (
    ConversationHistoryError,
    LoreAction,
    LoreEdit,
    LoreEditError,
    LoreFile,
    ScriptEdit,
    ScriptEditError,
    ScriptWorkspace,
    WorkspaceConfigurationError,
    WorkspaceEditError,
)
from storyline.workspace.factory import WORKSPACE_ENV_VAR, open_workspace

__all__ = [
    "WORKSPACE_ENV_VAR",
    "ConversationHistoryError",
    "LoreAction",
    "LoreEdit",
    "LoreEditError",
    "LoreFile",
    "ScriptEdit",
    "ScriptEditError",
    "ScriptWorkspace",
    "WorkspaceConfigurationError",
    "WorkspaceEditError",
    "open_workspace",
]
