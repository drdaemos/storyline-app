"""Workspace construction for the application composition root."""

import os
from pathlib import Path

from storyline.workspace.contracts import ScriptWorkspace, WorkspaceConfigurationError
from storyline.workspace.file import FileWorkspace

WORKSPACE_ENV_VAR = "STORYLINE_WORKSPACE"


def open_workspace(path: str | None = None) -> ScriptWorkspace:
    """Create the workspace adapter for ``path``, falling back to the environment."""
    raw_path = path or os.getenv(WORKSPACE_ENV_VAR)
    if not raw_path:
        raise WorkspaceConfigurationError(f"Pass --workspace or set {WORKSPACE_ENV_VAR} to a local workspace directory.")
    return FileWorkspace(root=Path(raw_path).expanduser().resolve())
