"""Storyline process entrypoint."""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from storyline.agent import DEFAULT_MODEL_NAME, WRITER_INSTRUCTIONS, resolve_model, writer_prompt_version
from storyline.evals import DEFAULT_JUDGE_MODEL_NAME, EvalError, EvalService, RunRequest, ScenarioError
from storyline.observability import configure_tracing
from storyline.presets import BUNDLED_PRESETS, DEFAULT_PRESET_ID
from storyline.tui.session import run_interactive_session
from storyline.web.app import run_server
from storyline.web.settings import DATA_DIR_ENV_VAR, WebConfigurationError
from storyline.workspace import WORKSPACE_ENV_VAR, WorkspaceConfigurationError, open_workspace

DEFAULT_COMMAND = "write"
COMMAND_NAMES = ("write", "serve", "eval", "help")
EVALS_DIR = Path("evals")
EVAL_RUNS_DIR = Path("eval-runs")
JUDGE_MODEL_ENV_VAR = "STORYLINE_JUDGE_MODEL"


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line interface parser."""
    parser = argparse.ArgumentParser(
        prog="storyline",
        description=f"Run Storyline. Without a command, runs `{DEFAULT_COMMAND}`.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", title="commands", metavar="COMMAND")

    write_parser = commands.add_parser("write", help="Start the interactive writing session (default).")
    _add_model_option(write_parser)
    write_parser.add_argument(
        "--workspace",
        metavar="PATH",
        help=f"Workspace directory holding one subdirectory per story (default: ${WORKSPACE_ENV_VAR}).",
    )
    write_parser.add_argument(
        "--story",
        metavar="NAME",
        help="Story to open (default: the last active story, or the only one).",
    )

    serve_parser = commands.add_parser("serve", help="Start the web server.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Address to listen on (default: %(default)s).")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    serve_parser.add_argument("--reload", action="store_true", help="Reload when source files change.")
    serve_parser.add_argument(
        "--workspace",
        metavar="PATH",
        help=f"Workspace directory the single local user's stories live in; used when AUTH_ENABLED is not true (default: ${WORKSPACE_ENV_VAR}).",
    )
    serve_parser.add_argument(
        "--data-dir",
        metavar="PATH",
        help=f"Directory holding one workspace per user under users/; used when AUTH_ENABLED=true (default: ${DATA_DIR_ENV_VAR}).",
    )

    eval_parser = commands.add_parser("eval", help="Evaluate the writer prompt on scenarios, or compare two runs.")
    eval_commands = eval_parser.add_subparsers(dest="eval_command", metavar="EVAL_COMMAND", required=True)

    run_parser = eval_commands.add_parser("run", help="Play scenarios against the writer agent, then check and judge the results.")
    run_parser.add_argument("scenarios", nargs="*", metavar="SCENARIO", help="Scenarios to run (default: all).")
    _add_model_option(run_parser)
    run_parser.add_argument("--instructions", metavar="PATH", type=Path, help="Writer prompt file to try (default: the built-in prompt).")
    run_parser.add_argument("--repeat", type=int, default=1, help="Times to play each scenario (default: %(default)s).")
    _add_judge_options(run_parser)
    run_parser.add_argument("--out", metavar="DIR", type=Path, help=f"Output directory (default: a new directory in {EVAL_RUNS_DIR}).")
    run_parser.add_argument("--evals-dir", metavar="DIR", type=Path, default=EVALS_DIR, help="Directory with scenarios/ and seeds/ (default: %(default)s).")

    compare_parser = eval_commands.add_parser("compare", help="Judge the stories of two runs side by side, dimension by dimension.")
    compare_parser.add_argument("run_a", metavar="RUN_A", type=Path, help="Baseline run directory.")
    compare_parser.add_argument("run_b", metavar="RUN_B", type=Path, help="Candidate run directory.")
    _add_judge_options(compare_parser, allow_skip=False)
    compare_parser.add_argument("--out", metavar="FILE", type=Path, help=f"Comparison file (default: in {EVAL_RUNS_DIR}).")

    commands.add_parser("help", help="Show this help.")

    parser.epilog = "\n".join(subparser.format_help() for subparser in (write_parser, serve_parser, run_parser, compare_parser))
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Load configuration and dispatch the requested command."""
    load_dotenv()
    parser = build_parser()
    options = parser.parse_args(_with_default_command(sys.argv[1:] if argv is None else argv))

    if options.command == "help":
        parser.print_help()
        return
    configure_tracing()
    if options.command == "serve":
        try:
            run_server(port=options.port, reload=options.reload, host=options.host, workspace=options.workspace, data_dir=options.data_dir)
        except (WebConfigurationError, WorkspaceConfigurationError) as error:
            parser.error(str(error))
    elif options.command == "eval":
        try:
            print(asyncio.run(_run_eval_command(options)))
        except (EvalError, ScenarioError) as error:
            parser.error(str(error))
    else:
        try:
            workspace = open_workspace(options.workspace)
        except WorkspaceConfigurationError as error:
            parser.error(str(error))
        run_interactive_session(workspace=workspace, story_name=options.story, model_name=options.model)


async def _run_eval_command(options: argparse.Namespace) -> str:
    """Run the requested eval subcommand and return its summary text."""
    if options.eval_command == "compare":
        out_file = options.out or EVAL_RUNS_DIR / f"compare-{options.run_a.name}-vs-{options.run_b.name}.md"
        service = EvalService(scenarios_dir=EVALS_DIR / "scenarios", seeds_dir=EVALS_DIR / "seeds")
        summary = await service.compare(options.run_a, options.run_b, judge_model=resolve_model(options.judge_model), out_file=out_file)
        return summary.read_text(encoding="utf-8")

    instructions = options.instructions.read_text(encoding="utf-8") if options.instructions else WRITER_INSTRUCTIONS
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    request = RunRequest(
        scenario_names=tuple(options.scenarios),
        model_name=options.model,
        instructions=instructions,
        out_dir=options.out or EVAL_RUNS_DIR / f"{timestamp}-{writer_prompt_version(instructions, BUNDLED_PRESETS.get(DEFAULT_PRESET_ID))}",
        judge_model_name=None if options.no_judge else options.judge_model,
        repeat=options.repeat,
    )
    service = EvalService(scenarios_dir=options.evals_dir / "scenarios", seeds_dir=options.evals_dir / "seeds")
    judge_model = None if options.no_judge else resolve_model(options.judge_model)
    summary = await service.run(request, writer_model=resolve_model(options.model), judge_model=judge_model)
    return summary.read_text(encoding="utf-8")


def _add_model_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model",
        default=os.getenv("STORYLINE_MODEL", DEFAULT_MODEL_NAME),
        help="Model name in provider:model format (default: %(default)s).",
    )


def _add_judge_options(parser: argparse.ArgumentParser, *, allow_skip: bool = True) -> None:
    parser.add_argument(
        "--judge-model",
        default=os.getenv(JUDGE_MODEL_ENV_VAR, DEFAULT_JUDGE_MODEL_NAME),
        help=f"Judge model; use a different model family from the writer (default: ${JUDGE_MODEL_ENV_VAR} or %(default)s).",
    )
    if allow_skip:
        parser.add_argument("--no-judge", action="store_true", help="Only run the mechanical checks.")


def _with_default_command(argv: Sequence[str]) -> list[str]:
    """Insert the default command unless one (or top-level help) was requested."""
    arguments = list(argv)
    if arguments and (arguments[0] in COMMAND_NAMES or arguments[0] in ("-h", "--help")):
        return arguments
    return [DEFAULT_COMMAND, *arguments]


if __name__ == "__main__":
    main()
