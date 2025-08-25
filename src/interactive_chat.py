from collections.abc import Callable

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from .character_loader import CharacterLoader
from .character_responder import CharacterResponder
from .models.character import Character


class InteractiveChatCLI:
    def __init__(self) -> None:
        self.console = Console()
        self.loader = CharacterLoader()
        self.current_character: Character | None = None
        self.responder: CharacterResponder | None = None

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
                choice = Prompt.ask("\nSelect a character (enter number or name)", choices=[str(i) for i in range(1, len(characters) + 1)] + characters)

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
        if not self.responder:
            return f"[No responder available for {self.current_character.name}]"

        try:
            character_response = self.responder.respond(user_message, streaming_callback)

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
            self.responder = self._setup_character_session(self.current_character)
            self.display_character_info(self.current_character)
            self.chat_loop()

    def _setup_character_session(self, character: Character) -> CharacterResponder:
        """Set up character session, checking for existing sessions and prompting user choice."""
        # Create a temporary responder to check for existing sessions
        temp_responder = CharacterResponder(character, use_persistent_memory=True)
        session_history = temp_responder.get_session_history()

        if session_history and len(session_history) > 0:
            self._display_session_history(session_history)
            choice = self._prompt_session_choice()

            if choice == "continue":
                # Load the most recent session
                most_recent_session = session_history[0]
                responder = CharacterResponder(
                    character,
                    session_id=most_recent_session["session_id"],
                    use_persistent_memory=True
                )
                self.console.print(f"[green]Continuing previous session with {len(responder.memory)} messages loaded.[/green]")
                return responder
            elif choice == "new":
                # Clear all existing sessions for this character and start fresh
                temp_responder.persistent_memory.clear_character_memory(character.name)
                responder = CharacterResponder(character, use_persistent_memory=True)
                self.console.print("[green]Started fresh conversation (previous sessions cleared).[/green]")
                return responder

        # No existing sessions, create new one
        responder = CharacterResponder(character, use_persistent_memory=True)
        self.console.print("[green]Started new conversation.[/green]")
        return responder

    def _display_session_history(self, session_history: list[dict[str, str]]) -> None:
        """Display existing sessions for the character."""
        self.console.print("\n[bold yellow]Found existing conversations:[/bold yellow]")

        for i, session in enumerate(session_history[:3], 1):  # Show up to 3 recent sessions
            message_count = session.get("message_count", 0)
            last_time = session.get("last_message_time", "Unknown")
            self.console.print(f"  {i}. Session with {message_count} messages (last: {last_time})")

        if len(session_history) > 3:
            self.console.print(f"  ... and {len(session_history) - 3} more sessions")

    def _prompt_session_choice(self) -> str:
        """Prompt user to choose between continuing existing session or starting new."""
        self.console.print("\n[bold cyan]What would you like to do?[/bold cyan]")
        self.console.print("1. [green]Continue[/green] from the most recent conversation")
        self.console.print("2. [red]Start new[/red] conversation (clears all previous sessions)")

        choice = Prompt.ask(
            "Choose an option",
            choices=["1", "2", "continue", "new", "c", "n"],
            default="1"
        )

        if choice in ["1", "continue", "c"]:
            return "continue"
        else:
            return "new"
