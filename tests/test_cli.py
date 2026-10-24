"""Tests for the process command dispatcher."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from storyline import cli
from storyline.agent import WRITER_INSTRUCTIONS, writer_prompt_version
from storyline.evals import EvalError, RunRequest
from storyline.presets import BUNDLED_PRESETS, DEFAULT_PRESET_ID
from storyline.workspace.file_workspace import FileWorkspace


class FakeEvalService:
    """Records what the CLI asks of the eval service and answers with a summary file."""

    instances: list["FakeEvalService"] = []

    def __init__(self, *, scenarios_dir: Path, seeds_dir: Path) -> None:
        self.scenarios_dir = scenarios_dir
        self.seeds_dir = seeds_dir
        self.calls: list[tuple[str, object]] = []
        FakeEvalService.instances.append(self)

    async def run(self, request: RunRequest, *, writer_model: object, judge_model: object) -> Path:
        self.calls.append(("run", request))
        self.calls.append(("judge", judge_model))
        request.out_dir.mkdir(parents=True)
        summary = request.out_dir / "summary.md"
        summary.write_text("run summary", encoding="utf-8")
        return summary

    async def compare(self, run_a: Path, run_b: Path, *, judge_model: object, out_file: Path) -> Path:
        self.calls.append(("compare", (run_a, run_b, out_file)))
        raise EvalError("no cases in common")


@pytest.fixture(autouse=True)
def configure_tracing(monkeypatch: pytest.MonkeyPatch) -> Mock:
    configure = Mock()
    monkeypatch.setattr(cli, "configure_tracing", configure)
    return configure


@pytest.fixture
def eval_service(monkeypatch: pytest.MonkeyPatch) -> type[FakeEvalService]:
    FakeEvalService.instances = []
    monkeypatch.setattr(cli, "EvalService", FakeEvalService)
    monkeypatch.setattr(cli, "resolve_model", lambda name: f"resolved:{name}")
    monkeypatch.delenv("STORYLINE_MODEL", raising=False)
    monkeypatch.delenv(cli.JUDGE_MODEL_ENV_VAR, raising=False)
    return FakeEvalService


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
    assert options["story_name"] is None


def test_story_option_names_the_story_to_open(start_session: Mock, tmp_path) -> None:
    cli.main(["--workspace", str(tmp_path), "--story", "harbor"])

    assert start_session.call_args.kwargs["story_name"] == "harbor"


def test_write_command_can_be_named_explicitly(start_session: Mock, tmp_path) -> None:
    cli.main(["write", "--workspace", str(tmp_path), "--model", "openrouter:explicit/model"])

    assert start_session.call_args.kwargs["model_name"] == "openrouter:explicit/model"
    assert start_session.call_args.kwargs["workspace"].root == tmp_path.resolve()


def test_model_option_overrides_the_environment(start_session: Mock, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("STORYLINE_MODEL", "openrouter:environment/model")

    cli.main(["--model", "openrouter:command/model", "--workspace", str(tmp_path)])

    assert start_session.call_args.kwargs["model_name"] == "openrouter:command/model"


def test_missing_workspace_exits_with_a_usage_error(start_session: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
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
    assert "--story" in output
    assert "--port" in output
    assert "--reload" in output
    assert "--data-dir" in output


def test_serve_command_starts_web_server_with_its_options(monkeypatch: pytest.MonkeyPatch) -> None:
    run_server = Mock()
    monkeypatch.setattr(cli, "run_server", run_server)

    cli.main(["serve", "--port", "8123", "--reload"])

    run_server.assert_called_once_with(port=8123, reload=True, host="127.0.0.1", workspace=None, data_dir=None)


def test_serve_command_takes_the_address_workspace_and_data_directory(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    run_server = Mock()
    monkeypatch.setattr(cli, "run_server", run_server)

    cli.main(["serve", "--host", "0.0.0.0", "--workspace", str(tmp_path / "stories"), "--data-dir", str(tmp_path / "data")])

    run_server.assert_called_once_with(port=8000, reload=False, host="0.0.0.0", workspace=str(tmp_path / "stories"), data_dir=str(tmp_path / "data"))


def test_serve_command_without_a_workspace_exits_with_a_usage_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "load_dotenv", Mock())
    monkeypatch.setenv("STORYLINE_WORKSPACE", "")
    monkeypatch.setenv("AUTH_ENABLED", "")

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["serve"])

    assert exit_info.value.code == 2
    assert "--workspace" in capsys.readouterr().err


def test_serve_command_with_authentication_but_no_clerk_key_exits_with_a_usage_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    monkeypatch.setattr(cli, "load_dotenv", Mock())
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("CLERK_SECRET_KEY", "")
    monkeypatch.setenv("CLERK_JWT_KEY", "")

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["serve", "--data-dir", str(tmp_path)])

    assert exit_info.value.code == 2
    assert "CLERK_SECRET_KEY" in capsys.readouterr().err


def test_commands_configure_tracing_but_help_does_not(start_session: Mock, configure_tracing: Mock, tmp_path) -> None:
    cli.main(["help"])
    configure_tracing.assert_not_called()

    cli.main(["--workspace", str(tmp_path)])
    configure_tracing.assert_called_once()


def test_eval_run_passes_scenarios_models_and_options_to_the_service(eval_service: type[FakeEvalService], tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    prompt_file = tmp_path / "candidate.md"
    prompt_file.write_text("Candidate prompt.", encoding="utf-8")

    cli.main(["eval", "run", "feedback", "steering", "--instructions", str(prompt_file), "--repeat", "3", "--out", str(tmp_path / "out"), "--evals-dir", str(tmp_path)])

    service = eval_service.instances[0]
    request = service.calls[0][1]
    assert isinstance(request, RunRequest)
    assert request.scenario_names == ("feedback", "steering")
    assert request.instructions == "Candidate prompt."
    assert request.repeat == 3
    assert request.judge_model_name == cli.DEFAULT_JUDGE_MODEL_NAME
    assert service.calls[1] == ("judge", f"resolved:{cli.DEFAULT_JUDGE_MODEL_NAME}")
    assert service.scenarios_dir == tmp_path / "scenarios"
    assert "run summary" in capsys.readouterr().out


def test_eval_run_defaults_to_the_built_in_prompt_and_a_versioned_output_directory(eval_service: type[FakeEvalService], monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "EVAL_RUNS_DIR", tmp_path / "eval-runs")

    cli.main(["eval", "run", "--no-judge"])

    service = eval_service.instances[0]
    request = service.calls[0][1]
    assert isinstance(request, RunRequest)
    assert request.instructions == WRITER_INSTRUCTIONS
    assert request.out_dir.parent == tmp_path / "eval-runs"
    assert request.out_dir.name.endswith(writer_prompt_version(WRITER_INSTRUCTIONS, BUNDLED_PRESETS.get(DEFAULT_PRESET_ID)))
    assert request.judge_model_name is None
    assert service.calls[1] == ("judge", None)


def test_eval_errors_exit_with_a_usage_error(eval_service: type[FakeEvalService], capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["eval", "compare", str(tmp_path / "a"), str(tmp_path / "b")])

    assert exit_info.value.code == 2
    assert "no cases in common" in capsys.readouterr().err
    out_file = eval_service.instances[0].calls[0][1][2]
    assert out_file == cli.EVAL_RUNS_DIR / "compare-a-vs-b.md"
