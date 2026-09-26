"""Storyline process entrypoint."""

import argparse
import os
from collections.abc import Sequence

from dotenv import load_dotenv

from storyline.agent import DEFAULT_MODEL_NAME
from storyline.tui.session import run_interactive_session
from storyline.web.app import run_server
from storyline.workspace import WORKSPACE_ENV_VAR, WorkspaceConfigurationError, open_workspace


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line interface parser."""
    parser = argparse.ArgumentParser(
        prog="storyline",
        description="Run Storyline. Without a command, starts the interactive writing session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default=os.getenv("STORYLINE_MODEL", DEFAULT_MODEL_NAME),
        help="Model name in provider:model format (default: %(default)s).",
    )
    parser.add_argument(
        "--workspace",
        metavar="PATH",
        help=f"Workspace directory (default: ${WORKSPACE_ENV_VAR}).",
    )
    commands = parser.add_subparsers(dest="command", title="commands")
    commands.add_parser("help", help="Show this help.")

    serve_parser = commands.add_parser("serve", help="Start the web server.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    serve_parser.add_argument("--reload", action="store_true", help="Reload when source files change.")

    parser.epilog = serve_parser.format_help()
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Load configuration and dispatch the requested command."""
    load_dotenv()
    parser = build_parser()
    options = parser.parse_args(argv)

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


if __name__ == "__main__":
    main()
