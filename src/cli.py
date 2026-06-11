import json
import os
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from .character_loader import CharacterLoader
from .character_manager import CharacterManager
from .interactive_chat import InteractiveChatCLI
from .models.prompt_processor_factory import PromptProcessorFactory
from .models.vn import Script, VNInput
from .models.vn.pipeline import PipelineProgress
from .text_analyzer import TextAnalyzer
from .vn.judge import VNScriptJudge, compare_evaluations
from .vn.judge.storage import load_evaluation, slugify, write_evaluation_files
from .vn.pipeline.generator import VNScriptGenerator
from .vn.registry import VNGenerationJobRegistry, VNScriptRegistry, VNSessionRegistry
from .vn.service import VNNotFoundError, VNService


def build_vn_service() -> VNService:
    """Same persistence stack the web flow uses; tests substitute it."""
    return VNService(VNScriptRegistry(), VNSessionRegistry(), VNGenerationJobRegistry())


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
                    click.echo(f"  - {char_info.name} - {char_info.tagline}")
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

        uvicorn.run("src.fastapi_server:app", host=host, port=port, reload=reload, log_level="info")
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


@cli.command("vn-generate")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False), required=False)
@click.option("--resume", "resume_job_id", default=None, help="Resume a failed generation job by its id (instead of INPUT_FILE)")
@click.option("--processor", "-p", "processor_type", default=None, help="Processor type (default: claude-sonnet, or the job's processor on resume)")
@click.option("--guidance", "guidance_file", type=click.Path(exists=True, dir_okay=False), default=None, help="Reviewer guidance file (from vn-review) appended to the input rules")
@click.option("--user-id", default="cli", show_default=True, help="User scope for persisted scripts and jobs")
@click.option("--output", "-o", "output_file", type=click.Path(dir_okay=False), default=None, help="Also write the generated script JSON to this path")
def vn_generate(
    input_file: str | None,
    resume_job_id: str | None,
    processor_type: str | None,
    guidance_file: str | None,
    user_id: str,
    output_file: str | None,
) -> None:
    """Generate a VN script from a VNInput JSON file, persisting it like the web flow.

    The run is a checkpointed job: on failure it stays resumable via --resume.
    """
    console = Console()
    if (input_file is None) == (resume_job_id is None):
        raise click.UsageError("provide exactly one of INPUT_FILE or --resume JOB_ID")

    service = build_vn_service()
    if resume_job_id is not None:
        try:
            job = service.get_generation_job(resume_job_id, user_id)
        except VNNotFoundError as e:
            raise click.ClickException(str(e)) from e
        processor_type = processor_type or job.processor_type
        job_id = resume_job_id
    else:
        assert input_file is not None
        vn_input = VNInput.model_validate(json.loads(Path(input_file).read_text(encoding="utf-8")))
        if guidance_file is not None:
            guidance = Path(guidance_file).read_text(encoding="utf-8").strip()
            rules = f"{vn_input.rules}\n\nDirector's notes from the previous review (address these):\n{guidance}".strip()
            vn_input = vn_input.model_copy(update={"rules": rules})
        processor_type = processor_type or "claude-sonnet"
        job_id = service.start_generation_job(vn_input, processor_type, user_id)

    generator = VNScriptGenerator(PromptProcessorFactory.create_processor(processor_type))
    console.print(f"[blue]Generation job {job_id} (processor: {processor_type})[/blue]")

    def on_progress(progress: PipelineProgress) -> None:
        scene = f" {progress.scene_id}" if progress.scene_id else ""
        detail = f" — {progress.detail}" if progress.detail else ""
        console.print(f"[cyan]{progress.stage}{scene}[/cyan] {progress.status}{detail}")

    try:
        script_id, status, report = service.run_generation_job(job_id, generator, user_id, on_progress)
    except VNNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except Exception as e:
        console.print(f"[red]Generation failed: {e}[/red]")
        console.print(f"[yellow]The job is checkpointed; continue it with: vn-generate --resume {job_id}[/yellow]")
        raise SystemExit(1) from e

    console.print(f"[green]Script saved with id {script_id} (validation: {status})[/green]")
    for issue in report.issues:
        console.print(f"[yellow]{issue.severity}: [{issue.code}] {issue.message}[/yellow]")
    if output_file is not None:
        script = service.get_script(script_id, user_id).script
        Path(output_file).write_text(json.dumps(script.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[green]Script JSON written to {output_file}[/green]")


@cli.command("vn-review")
@click.argument("target")
@click.option("--processor", "-p", "processor_type", default="claude-sonnet", show_default=True, help="Processor type used for the judge")
@click.option("--input", "input_file", type=click.Path(exists=True, dir_okay=False), default=None, help="VNInput JSON for premise context when TARGET is a script file")
@click.option("--user-id", default="cli", show_default=True, help="User scope when TARGET is a persisted script id")
@click.option("--output-dir", default="evaluations", show_default=True, type=click.Path(file_okay=False), help="Directory for the evaluation JSON/markdown/guidance files")
@click.option("--baseline", "baseline_file", type=click.Path(exists=True, dir_okay=False), default=None, help="Previous evaluation JSON; computes numeric progress and a stop/continue recommendation")
@click.option("--target-score", default=4.0, show_default=True, type=float, help="Overall score at which the improvement loop should stop")
def vn_review(
    target: str,
    processor_type: str,
    input_file: str | None,
    user_id: str,
    output_dir: str,
    baseline_file: str | None,
    target_score: float,
) -> None:
    """Review a VN script (persisted id or JSON file) as a playwright and an interactivity director.

    Writes a machine-readable evaluation (the numeric trail for iteration), a markdown
    report, and a guidance file feedable back into vn-generate --guidance.
    """
    console = Console()
    target_path = Path(target)
    if target_path.is_file():
        script = Script.model_validate(json.loads(target_path.read_text(encoding="utf-8")))
        vn_input = VNInput.model_validate(json.loads(Path(input_file).read_text(encoding="utf-8"))) if input_file else None
        stem_base = slugify(target_path.stem)
    else:
        service = build_vn_service()
        try:
            script = service.get_script(target, user_id).script
            vn_input = service.get_script_input(target, user_id)
        except VNNotFoundError as e:
            raise click.ClickException(str(e)) from e
        stem_base = target

    judge = VNScriptJudge(PromptProcessorFactory.create_processor(processor_type))
    console.print(f"[blue]Reviewing '{script.meta.title}' (processor: {processor_type})[/blue]")
    try:
        evaluation = judge.evaluate(script, vn_input)
    except Exception as e:
        console.print(f"[red]Review failed: {e}[/red]")
        raise SystemExit(1) from e

    delta = None
    if baseline_file is not None:
        delta = compare_evaluations(evaluation, load_evaluation(Path(baseline_file)), target_score=target_score)

    stem = f"{stem_base}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    json_path, md_path, guidance_path = write_evaluation_files(Path(output_dir), stem, evaluation, delta)

    console.print(f"[bold]{evaluation.script_title}[/bold] — verdict: [green]{evaluation.verdict}[/green], overall {evaluation.overall_score}/5")
    for name, score in evaluation.dimension_scores.items():
        console.print(f"  {name}: {score}/5")
    if evaluation.priorities:
        console.print("[bold]Top findings:[/bold]")
        for finding in evaluation.priorities[:3]:
            location = "/".join(part for part in [finding.scene_id, finding.beat_id] if part) or "global"
            console.print(f"  [{finding.severity}] {location}: {finding.issue}")
    if delta is not None:
        console.print(f"[bold]Progress:[/bold] {delta.status} ({delta.baseline_score} → {delta.current_score}, Δ {delta.overall_delta:+.2f}) — recommendation: {delta.recommendation}")
    console.print(f"[green]Saved: {json_path}, {md_path}, {guidance_path}[/green]")


def main() -> None:
    """Entry point for the CLI."""
    # Loaded here, not at import time: importing this module (e.g. from tests)
    # must never mutate process env such as DATABASE_URL.
    load_dotenv()
    cli()
