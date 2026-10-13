"""Web server configuration, read from the environment so it reaches a reloaded server process unchanged."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from storyline.agent import DEFAULT_MODEL_NAME
from storyline.web.auth import Authenticator, ClerkAuthenticator, SingleUserAuthenticator
from storyline.web.static_files import default_static_dir
from storyline.web.user_workspaces import DirectoryUserWorkspaces, LocalUserWorkspaces, UserWorkspaces
from storyline.workspace import WORKSPACE_ENV_VAR, open_workspace

AUTH_ENABLED_ENV_VAR = "AUTH_ENABLED"
CLERK_SECRET_KEY_ENV_VAR = "CLERK_SECRET_KEY"
CLERK_JWT_KEY_ENV_VAR = "CLERK_JWT_KEY"
CLERK_AUTHORIZED_PARTIES_ENV_VAR = "CLERK_AUTHORIZED_PARTIES"
DATA_DIR_ENV_VAR = "STORYLINE_DATA_DIR"
STATIC_DIR_ENV_VAR = "STORYLINE_STATIC_DIR"
MODEL_ENV_VAR = "STORYLINE_MODEL"
TRUE_VALUES = frozenset({"true", "1", "yes", "on"})


class WebConfigurationError(ValueError):
    """Raised when the web server is not configured well enough to start."""


@dataclass(frozen=True)
class WebSettings:
    """Everything the environment decides about a web server."""

    auth_enabled: bool = False
    clerk_secret_key: str | None = None
    clerk_jwt_key: str | None = None
    clerk_authorized_parties: tuple[str, ...] = ()
    workspace: str | None = None
    data_dir: Path | None = None
    default_model_name: str = DEFAULT_MODEL_NAME
    static_dir: Path | None = None

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> Self:
        env = os.environ if environ is None else environ
        parties = tuple(party.strip() for party in env.get(CLERK_AUTHORIZED_PARTIES_ENV_VAR, "").split(",") if party.strip())
        data_dir = env.get(DATA_DIR_ENV_VAR, "").strip()
        static_dir = env.get(STATIC_DIR_ENV_VAR, "").strip()
        return cls(
            auth_enabled=env.get(AUTH_ENABLED_ENV_VAR, "").strip().lower() in TRUE_VALUES,
            clerk_secret_key=env.get(CLERK_SECRET_KEY_ENV_VAR, "").strip() or None,
            clerk_jwt_key=env.get(CLERK_JWT_KEY_ENV_VAR, "").strip() or None,
            clerk_authorized_parties=parties,
            workspace=env.get(WORKSPACE_ENV_VAR, "").strip() or None,
            data_dir=Path(data_dir) if data_dir else None,
            default_model_name=env.get(MODEL_ENV_VAR, "").strip() or DEFAULT_MODEL_NAME,
            static_dir=Path(static_dir) if static_dir else None,
        )

    def authenticator(self) -> Authenticator:
        """Return the authenticator these settings call for; raise ``WebConfigurationError`` if it cannot work."""
        if not self.auth_enabled:
            return SingleUserAuthenticator()
        if not self.clerk_secret_key and not self.clerk_jwt_key:
            raise WebConfigurationError(f"{AUTH_ENABLED_ENV_VAR}=true needs {CLERK_SECRET_KEY_ENV_VAR} (or {CLERK_JWT_KEY_ENV_VAR}).")
        return ClerkAuthenticator(secret_key=self.clerk_secret_key, jwt_key=self.clerk_jwt_key, authorized_parties=self.clerk_authorized_parties)

    def user_workspaces(self) -> UserWorkspaces:
        """Return where each user's stories live; raise ``WebConfigurationError`` or ``WorkspaceConfigurationError`` if unset."""
        if not self.auth_enabled:
            return LocalUserWorkspaces(open_workspace(self.workspace))
        if self.data_dir is None:
            raise WebConfigurationError(f"{AUTH_ENABLED_ENV_VAR}=true needs {DATA_DIR_ENV_VAR}, the directory that holds every user's stories.")
        return DirectoryUserWorkspaces(self.data_dir)

    def frontend_dir(self) -> Path:
        """Return where the built frontend is looked for."""
        return self.static_dir or default_static_dir()
