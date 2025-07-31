import click
from colorama import init, Fore, Style
from .agent import NPCAgent

init()


@click.command()
@click.option('--name', default='Eldric', help='Name of the NPC')
@click.option('--role', default='Village Blacksmith', help='Role/profession of the NPC')
@click.option('--backstory', default='A gruff but kind blacksmith who has lived in this village for 30 years. Known for his excellent craftsmanship and willingness to help travelers.', help='Background story of the NPC')
def main(name, role, backstory):
    print(f"{Fore.CYAN}🎭 Interactive NPC Chat{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Creating {name}, the {role}...{Style.RESET_ALL}\n")
    
    npc = NPCAgent(role=role, backstory=backstory, name=name)
    
    print(f"{Fore.GREEN}{name} has entered the conversation!{Style.RESET_ALL}")
    print(f"{Fore.BLUE}Background: {backstory}{Style.RESET_ALL}\n")
    print(f"{Fore.MAGENTA}Type 'quit' to exit the conversation{Style.RESET_ALL}\n")
    
    while True:
        try:
            user_input = input(f"{Fore.WHITE}You: {Style.RESET_ALL}").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
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