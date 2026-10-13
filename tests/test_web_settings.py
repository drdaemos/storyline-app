"""Tests for how the web server is configured from the environment and started."""

import os
from pathlib import Path

import pytest

from storyline.web import app as web_app
from storyline.web.auth import ClerkAuthenticator, SingleUserAuthenticator
from storyline.web.settings import WebConfigurationError, WebSettings
from storyline.web.user_workspaces import DirectoryUserWorkspaces, LocalUserWorkspaces
from storyline.workspace import WorkspaceConfigurationError
from storyline.workspace.file_workspace import FileWorkspace
from tests.web_support import http_client

CONFIGURATION_VARIABLES = (
    "STORYLINE_WORKSPACE",
    "STORYLINE_DATA_DIR",
    "STORYLINE_STATIC_DIR",
    "STORYLINE_MODEL",
    "AUTH_ENABLED",
    "CLERK_SECRET_KEY",
    "CLERK_JWT_KEY",
    "CLERK_AUTHORIZED_PARTIES",
)


@pytest.fixture(autouse=True)
def clean_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test with no configuration, and restore whatever the test leaves in the environment."""
    for name in CONFIGURATION_VARIABLES:
        monkeypatch.setenv(name, "")


def test_nothing_is_configured_by_default() -> None:
    settings = WebSettings.from_environment({})

    assert settings.auth_enabled is False
    assert settings.data_dir is None
    assert settings.clerk_authorized_parties == ()
    assert isinstance(settings.authenticator(), SingleUserAuthenticator)


@pytest.mark.parametrize(("value", "enabled"), [("true", True), ("TRUE", True), (" true ", True), ("1", True), ("false", False), ("", False), ("nope", False)])
def test_authentication_is_enabled_by_the_auth_enabled_variable(value: str, enabled: bool) -> None:
    assert WebSettings.from_environment({"AUTH_ENABLED": value}).auth_enabled is enabled


def test_settings_are_read_from_their_variables() -> None:
    settings = WebSettings.from_environment(
        {
            "AUTH_ENABLED": "true",
            "CLERK_SECRET_KEY": "sk_test_1",
            "CLERK_JWT_KEY": "pem",
            "CLERK_AUTHORIZED_PARTIES": "https://a.example, https://b.example,",
            "STORYLINE_DATA_DIR": "/srv/storyline",
            "STORYLINE_MODEL": "openrouter:other/model",
            "STORYLINE_STATIC_DIR": "/srv/static",
        }
    )

    assert settings.clerk_secret_key == "sk_test_1"
    assert settings.clerk_jwt_key == "pem"
    assert settings.clerk_authorized_parties == ("https://a.example", "https://b.example")
    assert settings.data_dir == Path("/srv/storyline")
    assert settings.default_model_name == "openrouter:other/model"
    assert settings.frontend_dir() == Path("/srv/static")


def test_without_authentication_the_one_user_works_in_the_ordinary_local_workspace(tmp_path) -> None:
    workspaces = WebSettings.from_environment({"STORYLINE_WORKSPACE": str(tmp_path)}).user_workspaces()

    assert isinstance(workspaces, LocalUserWorkspaces)
    assert workspaces.workspace_for("local").root == tmp_path.resolve()


def test_without_authentication_a_workspace_is_required() -> None:
    with pytest.raises(WorkspaceConfigurationError):
        WebSettings.from_environment({}).user_workspaces()


def test_with_authentication_users_get_directories_under_the_data_dir(tmp_path) -> None:
    settings = WebSettings.from_environment({"AUTH_ENABLED": "true", "CLERK_SECRET_KEY": "sk_test_1", "STORYLINE_DATA_DIR": str(tmp_path)})

    assert isinstance(settings.authenticator(), ClerkAuthenticator)
    assert isinstance(settings.user_workspaces(), DirectoryUserWorkspaces)


def test_with_authentication_a_clerk_key_and_a_data_dir_are_required(tmp_path) -> None:
    without_key = WebSettings.from_environment({"AUTH_ENABLED": "true", "STORYLINE_DATA_DIR": str(tmp_path)})
    without_data_dir = WebSettings.from_environment({"AUTH_ENABLED": "true", "CLERK_SECRET_KEY": "sk_test_1"})

    with pytest.raises(WebConfigurationError, match="CLERK_SECRET_KEY"):
        without_key.authenticator()
    with pytest.raises(WebConfigurationError, match="STORYLINE_DATA_DIR"):
        without_data_dir.user_workspaces()


def test_a_jwt_key_alone_is_enough_for_clerk(tmp_path) -> None:
    settings = WebSettings.from_environment({"AUTH_ENABLED": "true", "CLERK_JWT_KEY": "pem"})

    assert isinstance(settings.authenticator(), ClerkAuthenticator)


@pytest.mark.asyncio
async def test_the_app_built_from_the_environment_serves_the_local_workspace_shared_with_the_terminal(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = FileWorkspace(root=tmp_path / "stories")
    await workspace.create_story(name="harbor")
    monkeypatch.setenv("STORYLINE_WORKSPACE", str(tmp_path / "stories"))
    monkeypatch.setenv("STORYLINE_STATIC_DIR", str(tmp_path / "no-frontend"))

    async with http_client(web_app.create_app_from_environment()) as client:
        listed = await client.get("/api/stories")

    assert listed.json()["stories"] == ["harbor"]


@pytest.mark.asyncio
async def test_the_app_built_from_the_environment_with_authentication_demands_a_token(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("CLERK_JWT_KEY", "not-a-real-key")
    monkeypatch.setenv("STORYLINE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STORYLINE_STATIC_DIR", str(tmp_path / "no-frontend"))

    async with http_client(web_app.create_app_from_environment()) as client:
        anonymous = await client.get("/api/stories")
        garbage = await client.get("/api/stories", headers={"Authorization": "Bearer garbage"})

    assert anonymous.status_code == 401
    assert garbage.status_code == 401


class _RecordedServer:
    """Stands in for uvicorn.run, recording how the server would have been started."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> None:
        self.calls.append((args, kwargs))


def test_run_server_starts_uvicorn_with_the_app_factory_and_passes_configuration_through_the_environment(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = _RecordedServer()
    monkeypatch.setattr(web_app.uvicorn, "run", server)

    web_app.run_server(port=8123, reload=True, host="0.0.0.0", workspace=str(tmp_path))

    ((args, options),) = server.calls
    assert args == ("storyline.web.app:create_app_from_environment",)
    assert options["factory"] is True
    assert (options["host"], options["port"], options["reload"]) == ("0.0.0.0", 8123, True)
    assert os.environ["STORYLINE_WORKSPACE"] == str(tmp_path)


def test_run_server_passes_the_data_dir_through_the_environment(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app.uvicorn, "run", _RecordedServer())
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_1")

    web_app.run_server(port=8000, reload=False, data_dir=str(tmp_path))

    assert os.environ["STORYLINE_DATA_DIR"] == str(tmp_path)


def test_run_server_refuses_to_start_when_it_cannot_work(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _RecordedServer()
    monkeypatch.setattr(web_app.uvicorn, "run", server)

    with pytest.raises(WorkspaceConfigurationError):
        web_app.run_server(port=8000, reload=False)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    with pytest.raises(WebConfigurationError):
        web_app.run_server(port=8000, reload=False)

    assert server.calls == []
