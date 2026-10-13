"""Which stories a user can reach."""

import re
from pathlib import Path
from typing import Protocol

from storyline.web.errors import InvalidUserIdError
from storyline.workspace import Workspace
from storyline.workspace.file_workspace import FileWorkspace

USERS_DIRECTORY = "users"
USER_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


class UserWorkspaces(Protocol):
    """Maps a user to the workspace that holds that user's stories, and no one else's."""

    def workspace_for(self, user_id: str) -> Workspace:
        """Return the workspace of ``user_id``."""


class LocalUserWorkspaces:
    """Authentication switched off: the one local user works in an ordinary workspace, shared with the terminal interface."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def workspace_for(self, user_id: str) -> Workspace:
        return self._workspace


class DirectoryUserWorkspaces:
    """One workspace directory per user under ``<data_dir>/users/<user id>``."""

    def __init__(self, data_dir: Path) -> None:
        self._users_root = data_dir.expanduser().resolve() / USERS_DIRECTORY
        self._workspaces: dict[str, FileWorkspace] = {}

    def workspace_for(self, user_id: str) -> FileWorkspace:
        if USER_ID_PATTERN.fullmatch(user_id) is None:
            raise InvalidUserIdError("This user id cannot be given a workspace.")
        workspace = self._workspaces.get(user_id)
        if workspace is None:
            # One object per user, so every request shares its write lock.
            workspace = self._workspaces[user_id] = FileWorkspace(root=self._users_root / user_id)
        return workspace
