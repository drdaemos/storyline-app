"""Storyline process entrypoint."""

import argparse
import os
import sys
from collections.abc import Sequence

from dotenv import load_dotenv

from storyline.agent import DEFAULT_MODEL_NAME
from storyline.tui.session import run_interactive_session
from storyline.web.app import run_server
from storyline.workspace import WORKSPACE_ENV_VAR, WorkspaceConfigurationError, open_workspace

DEFAULT_COMMAND = "write"
COMMAND_NAMES = ("write", "serve", "help")


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line interface parser."""
    parser = argparse.ArgumentParser(
        prog="storyline",
        description=f"Run Storyline. Without a command, runs `{DEFAULT_COMMAND}`.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", title="commands", metavar="COMMAND")

    write_parser = commands.add_parser("write", help="Start the interactive writing session (default).")
    write_parser.add_argument(
        "--model",
        default=os.getenv("STORYLINE_MODEL", DEFAULT_MODEL_NAME),
        help="Model name in provider:model format (default: %(default)s).",
    )
    write_parser.add_argument(
        "--workspace",
        metavar="PATH",
        help=f"Workspace directory (default: ${WORKSPACE_ENV_VAR}).",
    )

    serve_parser = commands.add_parser("serve", help="Start the web server.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    serve_parser.add_argument("--reload", action="store_true", help="Reload when source files change.")

    commands.add_parser("help", help="Show this help.")

    parser.epilog = "\n".join(subparser.format_help() for subparser in (write_parser, serve_parser))
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Load configuration and dispatch the requested command."""
    load_dotenv()
    parser = build_parser()
    options = parser.parse_args(_with_default_command(sys.argv[1:] if argv is None else argv))

    if options.command == "help":
        parser.print_help()
    elif options.command == "serve":
        run_server(port=options.port, reload=options.reload)
    else:
        try:
            workspace = open_workspace(options.workspace)
        except WorkspaceConfigurationError as error:
            parser.error(str(error))
        run_interactive_session(workspace=workspace, model_name=options.model)


def _with_default_command(argv: Sequence[str]) -> list[str]:
    """Insert the default command unless one (or top-level help) was requested."""
    arguments = list(argv)
    if arguments and (arguments[0] in COMMAND_NAMES or arguments[0] in ("-h", "--help")):
        return arguments
    return [DEFAULT_COMMAND, *arguments]


if __name__ == "__main__":
    main()
