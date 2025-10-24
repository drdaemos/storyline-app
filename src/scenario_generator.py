from pydantic import BaseModel
from langfuse import observe

from .character_utils import format_character_description
from .chat_logger import ChatLogger
from .models.api_models import Scenario
from .models.character import Character
from .models.prompt_processor import PromptProcessor


class ScenarioList(BaseModel):
    """Model for scenario list response from AI."""

    scenarios: list[Scenario]


class ScenarioGenerator:
    """Service for generating scenario intros for characters."""

    def __init__(self, processors: list[PromptProcessor], logger: ChatLogger) -> None:
        """
        Initialize the ScenarioGenerator.

        Args:
            processors: The ordered list of prompt processors to use for generation (primary first)
        """
        self.processors = processors
        self.logger = logger

    @observe
    def generate_scenarios(self, character: Character, count: int = 3, mood: str = "normal") -> list[Scenario]:
        """
        Generate scenario intros for a given character.

        Args:
            character: The character to generate scenarios for
            count: Number of scenarios to generate (default: 3)
            mood: Tone/mood of the scenarios: normal, romantic, spicy, dark, unhinged, mysterious, comedic, dramatic, gritty, philosophical, chaotic (default: normal)

        Returns:
            List of Scenario objects

        Raises:
            ValueError: If count is invalid or scenario generation fails
        """
        if count < 1 or count > 10:
            raise ValueError("Scenario count must be between 1 and 10")

        for processor in self.processors:
            try:
                system_prompt = self._build_scenario_generation_prompt(processor)
                user_prompt = self._build_user_prompt(character, count, mood)

                # Use prompt processor to generate scenarios
                scenario_response = processor.respond_with_model(prompt=system_prompt, user_prompt=user_prompt, output_type=ScenarioList)

                if not scenario_response.scenarios or len(scenario_response.scenarios) == 0:
                    raise ValueError("Failed to generate scenarios")

                return scenario_response.scenarios
            except Exception as e:
                self.logger.log_exception(e)
                continue

        raise ValueError("Failed to generate scenarios after trying all processors")

    def _build_scenario_generation_prompt(self, processor: PromptProcessor) -> str:
        """Build the system prompt for scenario generation."""
        prompt = f"""You are an expert creative writer specializing in interactive storytelling and handcrafted role-play scenarios for your players.
Your task is to generate several different scenarios starters for a role-play based on the AI character description and world setting provided by the user.
User is going to play for another character in the scenario, so make sure to leave room for their interaction with the AI character.
Make sure the scenarios are diverse and cover a range of genres and tones, with some having unexpected twists, or curious mixes of genres or dark elements.
You should go as extreme as needed with the scenarios in order to make them unique and interesting to explore.

Guidelines:
- Absolutely avoid scenarios that too cliché or generic - and avoid having similar scenarios
- Establish clear context for interaction (where they are, what's happening, what needs to happen)
- Write the scenario that leaves a room for the user character and has them interacting with the AI character
- Ensure the scenario is requiring the immediate user response and interaction with the AI character
- Never mention user as a "user" / "player" / "you" in the scenario description - refer to them indirectly
- Do not stick to the character definition too closely - feel free to introduce surprising elements that test both user and AI characters
- Do not write as an overview, instead set it up as a scene that is already unfolding in front of the user
- Respect the scenario tone guidelines provided by the user

Your scenario intro may include the following:
- Physical actions (in asterisks, in third person)
- Spoken dialogue (in quotes, like "this")
- Internal sensations or observations (in third person)
- Environmental details (if relevant, in third person)

Add line breaks to the intro_message for readability.

Content Guidelines:
{processor.get_processor_specific_prompt()}

Each scenario must consist of:
1. **summary**: Short engaging, striking name for the scenario (take inspiration from series or book chapter titles)
2. **intro_message**: The full opening introduction message that sets up the scene for the user (max 1000 characters)
3. **narrative_category**: A brief label describing the narrative tone, genre

Output your scenarios as a JSON object with a 'scenarios' array containing objects with 'summary', 'intro_message', and 'narrative_category' fields."""

        return prompt

    def _build_user_prompt(self, character: Character, count: int, mood: str) -> str:
        """Build the user prompt with character data and scenario count."""
        prompt = """Generate exactly {count} different engaging scenarios for a role-play with the following character and world setting:

## AI Character Information

Character Name: {character_name}
Character Background: {character_background}
Character Appearance: {character_appearance}
Character Personality: {character_personality}
Established Relationships:
{relationships}

## World Description

Setting: {setting_description}
Key Locations:
{key_locations}

## Scenario Requirements
{mood_prompt}
        """

        return prompt.format(**(format_character_description(character) | {"count": count} | {"mood_prompt": self._build_mood_prompt(mood)}))

    def _build_mood_prompt(self, mood: str) -> str:
        """Build the conventionality prompt based on user preference."""
        match mood:
            case "romantic":
                return "User wants emotionally intimate scenarios focused on developing deep connections, vulnerability, longing, or love stories. Emphasize chemistry, meaningful gestures, emotional breakthroughs, and the push-pull of attraction beyond just physical desire."

            case "spicy":
                return "User wants provocative, high-tension scenarios with sexual chemistry, flirtation, or suggestive themes. Create unexpected twists, break social norms and boundaries, build scenes highly charged with desire, arousal and action."

            case "dark":
                return "User prefers morally complex scenarios exploring themes like betrayal, corruption, psychological horror, or ethical dilemmas. Scenarios should have ominous undertones, high stakes, and explore the darker aspects of human nature."

            case "unhinged":
                return "User seeks chaotic, absurd, or transgressive scenarios that defy logic and social norms. Embrace the bizarre, extreme situations, unreliable reality, and scenarios where anything can happen without regard for convention."

            case "mysterious":
                return "User enjoys enigmatic scenarios with hidden clues, unrevealed motivations, conspiracy elements, or detective-style investigations. Layer secrets, red herrings, and gradual revelations throughout."

            case "comedic":
                return "User seeks humorous scenarios with witty banter, situational comedy, absurd misunderstandings, or satirical elements. Tone should be lighthearted with opportunities for comedic timing and playful interactions."

            case "dramatic":
                return "User wants emotionally charged scenarios with intense interpersonal conflicts, tragic elements, moral crossroads, or cathartic moments. Focus on character depth, emotional stakes, and powerful confrontations."

            case "gritty":
                return "User wants harsh, realistic scenarios depicting struggle, moral ambiguity, survival, or systemic injustice. Avoid idealism; focus on consequences, difficult choices, and the unglamorous side of conflict."

            case "philosophical":
                return "User wants thought-provoking scenarios exploring existential questions, ethical paradoxes, metaphysical concepts, or identity crises. Emphasize dialogue-driven exploration of big ideas and moral reasoning."

            case "chaotic":
                return "User seeks unpredictable scenarios with rapid tonal shifts, escalating absurdity, multiple converging crises, or Murphy's Law in action. Plans should constantly go awry in entertaining ways."

            case _:
                return "User prefers balanced, versatile scenarios with moderate stakes, clear narrative structure, and accessible themes. Mix lighter and heavier moments while maintaining coherent tone and genre conventions."
