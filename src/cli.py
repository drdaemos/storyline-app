import os

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from .text_analyzer import TextAnalyzer

load_dotenv()


@click.group()
def cli() -> None:
    """Storyline app - API server and text analysis."""
    pass


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

        uvicorn.run("src.fastapi_server:app", host=host, port=port, reload=reload, log_level="info")
    except ImportError:
        console = Console()
        console.print("[red]FastAPI server dependencies not installed. Please install with: pip install fastapi uvicorn[/red]")
    except Exception as e:
        console = Console()
        console.print(f"[red]Error starting server: {e}[/red]")


def main() -> None:
    """Entry point for the CLI."""
    cli()
