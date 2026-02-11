import os
from typing import Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from .character_loader import CharacterLoader
from .character_manager import CharacterManager
from .interactive_chat import InteractiveChatCLI
from .memory.scenario_registry import ScenarioRegistry
from .memory.world_lore_registry import WorldLoreRegistry
from .text_analyzer import TextAnalyzer

load_dotenv()

SEED_PERSONA_ID = "dev_user_persona"
SEED_NPC_IDS = ["dev_npc_kara", "dev_npc_miles"]
SEED_WORLD_LORE_ID = "dev_world_neon_harbor"
SEED_SCENARIO_ID = "dev_scenario_neon_harbor"
SEED_CHARACTER_IDS = [SEED_PERSONA_ID, *SEED_NPC_IDS]


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


@cli.group()
def dev() -> None:
    """Developer tooling commands."""
    pass


@dev.command("bootstrap")
@click.option("--user-id", default="anonymous", show_default=True, help="Target user ID for seeded records")
@click.option("--overwrite", is_flag=True, help="Overwrite existing seeded records if they exist")
def dev_bootstrap(user_id: str, overwrite: bool) -> None:
    """Seed local dev data (persona, NPCs, world lore, and one scenario)."""
    console = Console()
    manager = CharacterManager()
    scenario_registry = ScenarioRegistry()
    world_lore_registry = WorldLoreRegistry()

    def character_payload(name: str, tagline: str, backstory: str) -> dict[str, Any]:
        return {
            "name": name,
            "tagline": tagline,
            "backstory": backstory,
            "personality": "",
            "appearance": "",
            "relationships": {},
            "key_locations": [],
            "setting_description": "",
            "interests": [],
            "dislikes": [],
            "desires": [],
            "kinks": [],
        }

    try:
        # Persona
        manager.save_character_to_database(
            SEED_PERSONA_ID,
            character_payload(
                "Dev Persona",
                "Curious operator in a shifting social scene",
                "A composed observer who can pivot between charm and pressure.",
            ),
            user_id=user_id,
            is_persona=True,
        )

        # NPCs
        manager.save_character_to_database(
            SEED_NPC_IDS[0],
            character_payload(
                "Kara Voss",
                "Club manager with a long memory",
                "Runs the neon harbor lounge and tracks every favor owed.",
            ),
            user_id=user_id,
            is_persona=False,
        )
        manager.save_character_to_database(
            SEED_NPC_IDS[1],
            character_payload(
                "Miles Rook",
                "Broker of rumors and leverage",
                "Knows where every story breaks first and sells timing, not facts.",
            ),
            user_id=user_id,
            is_persona=False,
        )

        # World lore
        world_lore_registry.save_world_lore(
            name="Neon Harbor",
            lore_text=(
                "A rain-soaked port district where information moves faster than cargo. "
                "Favors are currency, and every public conversation has a private audience."
            ),
            lore_json={
                "era": "near-future",
                "tone": "tense social intrigue",
                "anchors": ["Lighthouse Lounge", "Dockside Exchange", "Storm Rail Terminal"],
            },
            world_lore_id=SEED_WORLD_LORE_ID,
            user_id=user_id,
        )

        # Scenario asset
        scenario_payload = {
            "summary": "Stormfront Bargain",
            "intro_message": (
                "Rain slams against the lounge skylights as Kara waves you to a back booth. "
                "Miles is already there, tapping a sealed data shard against a glass. "
                "Both insist they need your answer before midnight."
            ),
            "narrative_category": "social-thriller / negotiation",
            "character_id": SEED_NPC_IDS[0],
            "character_ids": SEED_NPC_IDS,
            "persona_id": SEED_PERSONA_ID,
            "world_lore_id": SEED_WORLD_LORE_ID,
            "location": "Lighthouse Lounge, Neon Harbor",
            "time_context": "11:24 PM, heavy storm warning",
            "atmosphere": "Electric, crowded, and claustrophobic with hidden listeners",
            "plot_hooks": [
                "Two offers, one decision",
                "Hidden surveillance in the room",
                "A deadline tied to the midnight cargo departure",
            ],
            "stakes": "Choosing wrong burns your leverage with one faction immediately",
            "character_goals": {
                "Kara Voss": "Lock in a favorable alliance tonight",
                "Miles Rook": "Force a deal that exposes Kara's blind spots",
            },
            "potential_directions": [
                "Broker a risky compromise",
                "Back one side and trigger immediate fallout",
                "Delay both and investigate the hidden surveillance first",
            ],
        }

        if overwrite:
            scenario_id = scenario_registry.save_scenario(
                scenario_data=scenario_payload,
                character_id=SEED_NPC_IDS[0],
                scenario_id=SEED_SCENARIO_ID,
                user_id=user_id,
            )
        else:
            existing = scenario_registry.get_scenario(SEED_SCENARIO_ID, user_id)
            if existing is None:
                scenario_id = scenario_registry.save_scenario(
                    scenario_data=scenario_payload,
                    character_id=SEED_NPC_IDS[0],
                    scenario_id=SEED_SCENARIO_ID,
                    user_id=user_id,
                )
            else:
                scenario_id = SEED_SCENARIO_ID

        console.print("[green]Dev bootstrap complete.[/green]")
        console.print(f"[blue]User:[/blue] {user_id}")
        console.print(f"[blue]Persona:[/blue] {SEED_PERSONA_ID}")
        console.print(f"[blue]NPCs:[/blue] {', '.join(SEED_NPC_IDS)}")
        console.print(f"[blue]World Lore:[/blue] {SEED_WORLD_LORE_ID}")
        console.print(f"[blue]Scenario:[/blue] {scenario_id}")
        console.print("[cyan]You can now start a session from Scenario Library and test suggested actions in chat.[/cyan]")
    except Exception as e:
        console.print(f"[red]Dev bootstrap failed: {e}[/red]")


@dev.command("reset-bootstrap")
@click.option("--user-id", default="anonymous", show_default=True, help="Target user ID for seeded records")
def dev_reset_bootstrap(user_id: str) -> None:
    """Remove seeded local dev data created by `dev bootstrap`."""
    console = Console()
    manager = CharacterManager()
    scenario_registry = ScenarioRegistry()
    world_lore_registry = WorldLoreRegistry()

    removed = {
        "characters": [],
        "scenarios": [],
        "world_lore": [],
    }

    try:
        # Remove seeded scenario IDs and any scenario records with dev_* IDs.
        scenarios = scenario_registry.get_all_scenarios(user_id)
        for scenario in scenarios:
            scenario_id = scenario.get("id", "")
            if scenario_id == SEED_SCENARIO_ID or str(scenario_id).startswith("dev_"):
                if scenario_registry.delete_scenario(scenario_id, user_id):
                    removed["scenarios"].append(scenario_id)

        # Remove seeded world lore IDs with dev_* prefix.
        world_lore_items = world_lore_registry.list_world_lore(user_id)
        for item in world_lore_items:
            world_lore_id = item.get("id", "")
            if str(world_lore_id).startswith("dev_"):
                if world_lore_registry.delete_world_lore(world_lore_id, user_id):
                    removed["world_lore"].append(world_lore_id)

        # Remove seeded characters with exact IDs or dev_* prefix.
        all_characters = manager.registry.get_all_characters(user_id=user_id, include_personas=True)
        for character in all_characters:
            character_id = character.get("id", "")
            if character_id in SEED_CHARACTER_IDS or str(character_id).startswith("dev_"):
                if manager.registry.delete_character(character_id, user_id):
                    removed["characters"].append(character_id)

        console.print("[green]Dev bootstrap data reset complete.[/green]")
        console.print(f"[blue]Removed characters:[/blue] {', '.join(removed['characters']) if removed['characters'] else 'none'}")
        console.print(f"[blue]Removed scenarios:[/blue] {', '.join(removed['scenarios']) if removed['scenarios'] else 'none'}")
        console.print(f"[blue]Removed world lore:[/blue] {', '.join(removed['world_lore']) if removed['world_lore'] else 'none'}")
    except Exception as e:
        console.print(f"[red]Dev bootstrap reset failed: {e}[/red]")


def main() -> None:
    """Entry point for the CLI."""
    cli()
