import click
from colorama import Fore, Style, init

from .agent import NPCAgent
from .character_loader import CharacterLoader

init()


@click.command()
@click.option("--character", "-c", help="Load character from YAML file (e.g., eldric)")
@click.option("--name", help="Name of the NPC (overrides YAML)")
@click.option("--role", help="Role/profession of the NPC (overrides YAML)")
@click.option("--backstory", help="Background story of the NPC (overrides YAML)")
@click.option("--list-characters", is_flag=True, help="List available character files")
def main(
    character: str | None,
    name: str | None,
    role: str | None,
    backstory: str | None,
    list_characters: bool,
) -> None:
    loader = CharacterLoader()

    if list_characters:
        characters = loader.list_characters()
        if characters:
            print(f"{Fore.CYAN}Available characters:{Style.RESET_ALL}")
            for char in characters:
                char_info = loader.get_character_info(char)
                if char_info:
                    print(f"  {Fore.GREEN}{char}{Style.RESET_ALL} - {char_info['role']}")
        else:
            print(f"{Fore.YELLOW}No character files found in characters/ directory{Style.RESET_ALL}")
        return

    if character:
        try:
            char_data = loader.load_character(character)
            name = name or char_data["name"]
            role = role or char_data["role"]
            backstory = backstory or char_data["backstory"]
            print(f"{Fore.GREEN}Loaded character from {character}.yaml{Style.RESET_ALL}")
        except FileNotFoundError:
            print(f"{Fore.RED}Character file '{character}.yaml' not found{Style.RESET_ALL}")
            return
        except ValueError as e:
            print(f"{Fore.RED}Error loading character: {e}{Style.RESET_ALL}")
            return
    else:
        if not all([name, role, backstory]):
            print(f"{Fore.RED}Error: Either provide --character or all of --name, --role, and --backstory{Style.RESET_ALL}")
            return

    # At this point, name, role, and backstory should be guaranteed to be strings
    assert name is not None, "Name should not be None at this point"
    assert role is not None, "Role should not be None at this point"
    assert backstory is not None, "Backstory should not be None at this point"

    print(f"{Fore.CYAN}🎭 Interactive NPC Chat{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Creating {name}, the {role}...{Style.RESET_ALL}\n")

    npc = NPCAgent(role=role, backstory=backstory, name=name)

    print(f"{Fore.GREEN}{name} has entered the conversation!{Style.RESET_ALL}")
    print(f"{Fore.BLUE}Background: {backstory}{Style.RESET_ALL}\n")
    print(f"{Fore.MAGENTA}Type 'quit' to exit the conversation{Style.RESET_ALL}\n")

    while True:
        try:
            user_input = input(f"{Fore.WHITE}You: {Style.RESET_ALL}").strip()

            if user_input.lower() in ["quit", "exit", "bye"]:
                print(f"{Fore.YELLOW}{name}: Farewell, traveler! Safe journeys!{Style.RESET_ALL}")
                break

            if not user_input:
                continue

            print(f"{Fore.CYAN}Thinking...{Style.RESET_ALL}", end="")
            response = npc.respond(user_input)
            print(f"\r{Fore.GREEN}{name}: {response}{Style.RESET_ALL}\n")

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}{name}: Until we meet again!{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
