import os

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from .character_loader import CharacterLoader
from .character_manager import CharacterManager
from .interactive_chat import InteractiveChatCLI
from .text_analyzer import TextAnalyzer

load_dotenv()


@click.group()
def cli() -> None:
    """Storyline app - Interactive chat and text analysis."""
    pass


@cli.command()
@click.option("--character", "-c", help="Load character from YAML file (e.g., eldric)")
@click.option("--list-characters", is_flag=True, help="List available character files")
def chat(
    character: str | None,
    list_characters: bool,
) -> None:
    """Start interactive chat with a character."""
    loader = CharacterLoader()

    if list_characters:
        characters = loader.list_characters()
        if characters:
            click.echo("Available characters:")
            for char_name in characters:
                char_info = loader.get_character_info(char_name)
                if char_info:
                    click.echo(f"  - {char_info.name} - {char_info.role}")
                else:
                    click.echo(f"  - {char_name}")
        else:
            click.echo("No characters found.")
        return

    if character:
        try:
            char_obj = loader.load_character(character)
            cli_instance = InteractiveChatCLI()
            cli_instance.current_character = char_obj
            cli_instance.run()
        except FileNotFoundError:
            click.echo(f"Character '{character}' not found.")
    else:
        # Start interactive character selection
        cli_instance = InteractiveChatCLI()
        cli_instance.run()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output file for analysis results (optional)")
def analyze(file_path: str, output: str | None) -> None:
    """Analyze a text file to extract plot beats and story elements."""
    console = Console()

    try:
        console.print(f"[blue]Analyzing file: {file_path}[/blue]")

        analyzer = TextAnalyzer()
        result = analyzer.analyze_file(file_path)

        # Display results
        console.print(
            Panel(
                f"**File:** {result['file_path']}\n"
                f"**Word Count:** {result['file_stats']['word_count']}\n"
                f"**Character Count:** {result['file_stats']['character_count']}\n\n"
                f"**Analysis:**\n{result['analysis']}",
                title="Text Analysis Results",
                border_style="green",
            )
        )

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(f"Analysis of: {result['file_path']}\n")
                f.write(f"Word Count: {result['file_stats']['word_count']}\n")
                f.write(f"Character Count: {result['file_stats']['character_count']}\n\n")
                f.write(f"Analysis:\n{result['analysis']}")
            console.print(f"[green]Results saved to: {output}[/green]")

    except Exception as e:
        console.print(f"[red]Error analyzing file: {e}[/red]")


@cli.command()
@click.option("--host", help="Host to bind the server to")
@click.option("--port", help="Port to bind the server to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the FastAPI server for web-based character interactions."""
    try:
        import uvicorn

        host = host or os.getenv("HOST", "0.0.0.0")
        port = int(port or os.getenv("PORT", 8000))

        console = Console()
        console.print("[green]Starting Storyline API server...[/green]")
        console.print(f"[blue]Server will be available at: http://{host}:{port}[/blue]")
        console.print(f"[blue]Web interface: http://{host}:{port}/[/blue]")
        console.print(f"[blue]API docs: http://{host}:{port}/docs[/blue]")

        uvicorn.run(
            "src.fastapi_server:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except ImportError:
        console = Console()
        console.print("[red]FastAPI server dependencies not installed. Please install with: pip install fastapi uvicorn[/red]")
    except Exception as e:
        console = Console()
        console.print(f"[red]Error starting server: {e}[/red]")


@cli.command()
@click.option("--check", is_flag=True, help="Check sync status without making changes")
@click.option("--characters-dir", default="characters", help="Directory containing character YAML files")
def sync_characters(check: bool, characters_dir: str) -> None:
    """Sync character files to database."""
    console = Console()

    try:
        manager = CharacterManager(characters_dir)

        if check:
            # Check sync status only
            console.print("[blue]Checking character sync status...[/blue]")
            status = manager.check_sync_status()

            if status["file_only"]:
                console.print(f"[yellow]Characters only in files ({len(status['file_only'])}): {', '.join(status['file_only'])}[/yellow]")

            if status["db_only"]:
                console.print(f"[cyan]Characters only in database ({len(status['db_only'])}): {', '.join(status['db_only'])}[/cyan]")

            if status["both_same"]:
                console.print(f"[green]Characters in sync ({len(status['both_same'])}): {', '.join(status['both_same'])}[/green]")

            if status["both_different"]:
                console.print(f"[red]Characters with differences ({len(status['both_different'])}): {', '.join(status['both_different'])}[/red]")

            if status["file_errors"]:
                console.print(f"[red]File errors ({len(status['file_errors'])}):[/red]")
                for error in status["file_errors"]:
                    console.print(f"  - {error['character_id']}: {error['error']}")

        else:
            # Perform sync
            console.print("[blue]Syncing characters from files to database...[/blue]")
            results = manager.sync_files_to_database()

            if results["added"]:
                console.print(f"[green]Added to database ({len(results['added'])}): {', '.join(results['added'])}[/green]")

            if results["updated"]:
                console.print(f"[yellow]Updated in database ({len(results['updated'])}): {', '.join(results['updated'])}[/yellow]")

            if results["skipped"]:
                console.print(f"[cyan]Skipped (no changes) ({len(results['skipped'])}): {', '.join(results['skipped'])}[/cyan]")

            if results["errors"]:
                console.print(f"[red]Errors ({len(results['errors'])}):[/red]")
                for error in results["errors"]:
                    console.print(f"  - {error['character_id']}: {error['error']}")

            total_processed = len(results["added"]) + len(results["updated"]) + len(results["skipped"])
            console.print(f"[green]Sync completed. {total_processed} characters processed.[/green]")

    except Exception as e:
        console.print(f"[red]Error during sync: {e}[/red]")


def main() -> None:
    """Entry point for the CLI."""
    cli()
