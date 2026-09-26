"""Tests for the process command dispatcher."""

from unittest.mock import Mock

import pytest

from storyline import cli
from storyline.workspace.file import FileWorkspace


@pytest.fixture
def start_session(monkeypatch: pytest.MonkeyPatch) -> Mock:
    start_session = Mock()
    monkeypatch.setattr(cli, "run_interactive_session", start_session)
    monkeypatch.delenv("STORYLINE_MODEL", raising=False)
    return start_session


def test_default_command_starts_interactive_session_in_the_workspace(start_session: Mock, tmp_path) -> None:
    cli.main(["--workspace", str(tmp_path)])

    start_session.assert_called_once()
    options = start_session.call_args.kwargs
    assert options["model_name"] == "openrouter:meta/muse-spark-1.3"
    assert isinstance(options["workspace"], FileWorkspace)
    assert options["workspace"].root == tmp_path.resolve()


def test_write_command_can_be_named_explicitly(start_session: Mock, tmp_path) -> None:
    cli.main(["write", "--workspace", str(tmp_path), "--model", "openrouter:explicit/model"])

    assert start_session.call_args.kwargs["model_name"] == "openrouter:explicit/model"
    assert start_session.call_args.kwargs["workspace"].root == tmp_path.resolve()


def test_model_option_overrides_the_environment(
    start_session: Mock, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("STORYLINE_MODEL", "openrouter:environment/model")

    cli.main(["--model", "openrouter:command/model", "--workspace", str(tmp_path)])

    assert start_session.call_args.kwargs["model_name"] == "openrouter:command/model"


def test_missing_workspace_exits_with_a_usage_error(
    start_session: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "load_dotenv", Mock())
    monkeypatch.delenv("STORYLINE_WORKSPACE", raising=False)

    with pytest.raises(SystemExit) as exit_info:
        cli.main([])

    assert exit_info.value.code == 2
    assert "--workspace" in capsys.readouterr().err
    start_session.assert_not_called()


def test_help_command_prints_available_commands(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["help"])

    output = capsys.readouterr().out
    assert "serve" in output
    assert "--workspace" in output
    assert "--port" in output
    assert "--reload" in output


def test_serve_command_starts_web_server_with_its_options(monkeypatch: pytest.MonkeyPatch) -> None:
    run_server = Mock()
    monkeypatch.setattr(cli, "run_server", run_server)

    cli.main(["serve", "--port", "8123", "--reload"])

    run_server.assert_called_once_with(port=8123, reload=True)
