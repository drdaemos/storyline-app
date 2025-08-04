from collections.abc import Callable

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from .actor import Actor
from .character_loader import CharacterLoader
from .models.character import Character

load_dotenv()

class InteractiveChatCLI:
    def __init__(self) -> None:
        self.console = Console()
        self.loader = CharacterLoader()
        self.current_character: Character | None = None
        self.actor: Actor | None = None

    def display_welcome(self) -> None:
        welcome_text = """
# Welcome to Interactive Storyline Chat

Select a character to start chatting with them!
        """
        self.console.print(Panel(Markdown(welcome_text), title="Storyline Chat", border_style="cyan"))

    def select_character(self) -> Character | None:
        characters = self.loader.list_characters()

        if not characters:
            self.console.print("[red]No characters found in the characters directory![/red]")
            return None

        self.console.print("\n[bold cyan]Available Characters:[/bold cyan]")
        for i, char_name in enumerate(characters, 1):
            char_info = self.loader.get_character_info(char_name)
            if char_info:
                self.console.print(f"{i}. [bold]{char_info.name}[/bold] - {char_info.role}")
            else:
                self.console.print(f"{i}. {char_name}")

        while True:
            try:
                choice = Prompt.ask("\nSelect a character (enter number or name)",
                                  choices=[str(i) for i in range(1, len(characters) + 1)] + characters)

                if choice.isdigit():
                    char_name = characters[int(choice) - 1]
                else:
                    char_name = choice

                character = self.loader.load_character(char_name)
                self.console.print(f"\n[green]Selected character: {character.name}[/green]")
                return character

            except (ValueError, IndexError, FileNotFoundError) as e:
                self.console.print(f"[red]Error: {e}[/red]")
                continue

    def display_character_info(self, character: Character) -> None:
        info_text = f"""
**Name:** {character.name}
**Role:** {character.role}
**Backstory:** {character.backstory}
        """
        self.console.print(Panel(Markdown(info_text), title=f"Character: {character.name}", border_style="green"))

    def get_ai_response(self, user_message: str, streaming_callback: Callable[[str], None] | None = None) -> str:
        if not self.actor:
            return f"[No actor available for {self.current_character.name}]"

        try:
            character_response = self.actor.respond(user_message, streaming_callback)

            return character_response
        except Exception as e:
            return f"[Error generating response: {str(e)}]"

    def chat_loop(self) -> None:
        if not self.current_character:
            return

        self.console.print(f"\n[bold green]Starting chat with {self.current_character.name}[/bold green]")
        self.console.print("[dim]Type 'quit' to exit the chat[/dim]\n")

        while True:
            try:
                user_input = Prompt.ask("[bold blue]You[/bold blue]")

                if user_input == "quit":
                    self.console.print("[yellow]Goodbye![/yellow]")
                    break

                # Display streaming response
                with Live(Text("🤔 Thinking...", style="dim"), console=self.console, refresh_per_second=10) as live:
                    current_response = ""

                    def streaming_callback(chunk: str) -> None:
                        nonlocal current_response
                        current_response = current_response + chunk
                        live.update(Panel(current_response, title=f"{self.current_character.name}", border_style="magenta"))

                    # Get AI response with streaming
                    final_response = self.get_ai_response(user_input, streaming_callback)

                    # Ensure final response is displayed
                    live.update(Panel(final_response, title=f"{self.current_character.name}", border_style="magenta"))

                self.console.print()  # Add spacing

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Chat interrupted. Goodbye![/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

    def run(self) -> None:
        self.display_welcome()
        self.current_character = self.select_character()

        if self.current_character:
            self.actor = Actor(self.current_character)
            self.display_character_info(self.current_character)
            self.chat_loop()


@click.command()
@click.option("--character", "-c", help="Load character from YAML file (e.g., eldric)")
@click.option("--list-characters", is_flag=True, help="List available character files")
def main(
    character: str | None,
    list_characters: bool,
) -> None:
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
            cli = InteractiveChatCLI()
            cli.current_character = char_obj
            cli.run()
        except FileNotFoundError:
            click.echo(f"Character '{character}' not found.")
    else:
        # Start interactive character selection
        cli = InteractiveChatCLI()
        cli.run()

