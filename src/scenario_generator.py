import re
from collections.abc import Callable

from pydantic import BaseModel

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

    def generate_scenarios(self, character: Character, count: int = 3, mood: str = "normal", persona: Character | None = None) -> list[Scenario]:
        """
        Generate scenario intros for a given character.

        Args:
            character: The character to generate scenarios for
            count: Number of scenarios to generate (default: 3)
            mood: Tone/mood of the scenarios: normal, romantic, spicy, dark, unhinged, mysterious, comedic, dramatic, gritty, philosophical, chaotic (default: normal)
            persona: Optional persona character representing the user (not used in prompts yet)

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
                user_prompt = self._build_user_prompt(character, count, mood, persona)

                # Use prompt processor to generate scenarios
                scenario_response = processor.respond_with_model(prompt=system_prompt, user_prompt=user_prompt, output_type=ScenarioList, reasoning=True)

                if not scenario_response.scenarios or len(scenario_response.scenarios) == 0:
                    raise ValueError("Failed to generate scenarios")

                return scenario_response.scenarios
            except Exception as e:
                self.logger.log_exception(e)
                continue

        raise ValueError("Failed to generate scenarios after trying all processors")

    def generate_scenarios_streaming(
        self,
        character: Character,
        count: int = 3,
        mood: str = "normal",
        persona: Character | None = None,
        streaming_callback: Callable[[str], None] | None = None,
        scenario_callback: Callable[[Scenario], None] | None = None,
    ) -> list[Scenario]:
        """
        Generate scenario intros for a given character with streaming support.

        Args:
            character: The character to generate scenarios for
            count: Number of scenarios to generate (default: 3)
            mood: Tone/mood of the scenarios
            persona: Optional persona character representing the user
            streaming_callback: Optional callback for streaming text chunks
            scenario_callback: Optional callback when a complete scenario is parsed

        Returns:
            List of Scenario objects

        Raises:
            ValueError: If count is invalid or scenario generation fails
        """
        if count < 1 or count > 10:
            raise ValueError("Scenario count must be between 1 and 10")

        for processor in self.processors:
            try:
                system_prompt = self._build_scenario_generation_prompt_xml(processor)
                user_prompt = self._build_user_prompt(character, count, mood, persona)

                # Collect full response and parse incrementally
                full_response = ""
                emitted_scenario_ids: set[str] = set()

                for chunk in processor.respond_with_stream(prompt=system_prompt, user_prompt=user_prompt, reasoning=True):
                    full_response += chunk
                    if streaming_callback:
                        streaming_callback(chunk)

                    # Try to parse completed scenarios incrementally
                    if scenario_callback and "</scenario>" in full_response:
                        scenarios = self._parse_scenarios_from_xml(full_response)
                        for scenario in scenarios:
                            # Use summary as unique identifier to avoid duplicates
                            scenario_id = f"{scenario.summary}:{scenario.narrative_category}"
                            if scenario_id not in emitted_scenario_ids:
                                scenario_callback(scenario)
                                emitted_scenario_ids.add(scenario_id)

                # Parse final scenarios from XML tags
                scenarios = self._parse_scenarios_from_xml(full_response)

                if not scenarios:
                    raise ValueError("Failed to generate scenarios")

                return scenarios
            except Exception as e:
                self.logger.log_exception(e)
                continue

        raise ValueError("Failed to generate scenarios after trying all processors")

    def _build_scenario_generation_prompt(self, processor: PromptProcessor) -> str:
        """Build the system prompt for scenario generation."""
        prompt = f"""You are an expert creative writer specializing in interactive storytelling and handcrafted role-play scenarios for user players.
Your task is to generate several different scenarios starters for a role-play based on the main characters description and world setting provided by the user.
User is going to play for another character in the scenario, so make sure to leave room for their interaction with the AI character.
Make sure the scenarios are diverse and cover a range of genres and tones, with some having unexpected twists, or curious mixes of genres or dark elements.
You should go as extreme as needed with the scenarios in order to make them unique and interesting to explore.

Guidelines:
- Absolutely avoid scenarios that too cliché or generic - and avoid having similar scenarios
- Establish clear context for interaction (where they are, what's happening, what needs to happen)
- Write the scenario that leaves a room for the user character and has them interacting with the AI character
- Ensure the scenario is immediately set up to require user character interaction.
- NEVER end up scenario intro with a question to the user - instead, set up a scene that is already unfolding
- Do not stick to the character definition too closely - feel free to introduce surprising elements that test both user and AI characters
- Respect the scenario tone guidelines provided by the user

Your writing may include the following elements:
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

    def _build_user_prompt(self, character: Character, count: int, mood: str, persona: Character | None) -> str:
        """Build the user prompt with character data and scenario count."""
        prompt = """Generate exactly {count} different engaging scenarios for a role-play with the following character and world setting:

## Main Characters

{character_card}

{user_card}

## Scenario Requirements
{mood_prompt}
        """

        user_card = persona.to_prompt_card("Character", controller="User", include_world_info=False) if persona else ""
        character_card = character.to_prompt_card("Character", controller="AI", include_world_info=True)

        return prompt.format(**({"count": count, "character_card": character_card, "user_card": user_card, "mood_prompt": self._build_mood_prompt(mood)}))

    def _build_mood_prompt(self, mood: str) -> str:
        """Build the conventionality prompt based on user preference. Handles multiple comma-separated moods."""
        mood_descriptions = {
            "romantic": "emotionally intimate scenarios focused on developing deep connections, vulnerability, longing, or love stories. Emphasize chemistry, meaningful gestures, emotional breakthroughs, and the push-pull of attraction beyond just physical desire.",
            "spicy": "provocative, high-tension scenarios with sexual chemistry, flirtation, or suggestive themes. Create unexpected twists, break social norms and boundaries, build scenes highly charged with desire, arousal and action.",
            "dark": "morally complex scenarios exploring themes like betrayal, corruption, psychological horror, or ethical dilemmas. Scenarios should have ominous undertones, high stakes, and explore the darker aspects of human nature.",
            "unhinged": "chaotic, absurd, or transgressive scenarios that defy logic and social norms. Embrace the bizarre, extreme situations, unreliable reality, and scenarios where anything can happen without regard for convention.",
            "mysterious": "enigmatic scenarios with hidden clues, unrevealed motivations, conspiracy elements, or detective-style investigations. Layer secrets, red herrings, and gradual revelations throughout.",
            "comedic": "humorous scenarios with witty banter, situational comedy, absurd misunderstandings, or satirical elements. Tone should be lighthearted with opportunities for comedic timing and playful interactions.",
            "dramatic": "emotionally charged scenarios with intense interpersonal conflicts, tragic elements, moral crossroads, or cathartic moments. Focus on character depth, emotional stakes, and powerful confrontations.",
            "gritty": "harsh, realistic scenarios depicting struggle, moral ambiguity, survival, or systemic injustice. Avoid idealism; focus on consequences, difficult choices, and the unglamorous side of conflict.",
            "philosophical": "thought-provoking scenarios exploring existential questions, ethical paradoxes, metaphysical concepts, or identity crises. Emphasize dialogue-driven exploration of big ideas and moral reasoning.",
            "chaotic": "unpredictable scenarios with rapid tonal shifts, escalating absurdity, multiple converging crises, or Murphy's Law in action. Plans should constantly go awry in entertaining ways.",
            "normal": "balanced, versatile scenarios with moderate stakes, clear narrative structure, and accessible themes. Mix lighter and heavier moments while maintaining coherent tone and genre conventions.",
        }

        # Parse comma-separated moods
        moods = [m.strip().lower() for m in mood.split(',') if m.strip()]

        if not moods or moods == ['normal']:
            return f"User prefers {mood_descriptions.get('normal', '')}"

        # Build combined description
        descriptions = []
        for m in moods:
            if m in mood_descriptions:
                descriptions.append(mood_descriptions[m])

        if not descriptions:
            return f"User prefers {mood_descriptions['normal']}"

        if len(descriptions) == 1:
            return f"User wants {descriptions[0]}"

        return f"User wants scenarios that blend multiple tones: {' AND '.join(descriptions)}"

    def _build_scenario_generation_prompt_xml(self, processor: PromptProcessor) -> str:
        """Build the system prompt for scenario generation with XML output format."""
        prompt = f"""You are an expert creative writer specializing in interactive storytelling and handcrafted role-play scenarios for user players.
Your task is to generate several different scenarios starters for a role-play based on the main characters description and world setting provided by the user.
User is going to play for another character in the scenario, so make sure to leave room for their interaction with the AI character.
Make sure the scenarios are diverse and cover a range of genres and tones, with some having unexpected twists, or curious mixes of genres or dark elements.
You should go as extreme as needed with the scenarios in order to make them unique and interesting to explore.

Guidelines:
- Absolutely avoid scenarios that too cliché or generic - and avoid having similar scenarios
- Establish clear context for interaction (where they are, what's happening, what needs to happen)
- Write the scenario that leaves a room for the user character and has them interacting with the AI character
- Ensure the scenario is immediately set up to require user character interaction.
- NEVER end up scenario intro with a question to the user - instead, set up a scene that is already unfolding
- Do not stick to the character definition too closely - feel free to introduce surprising elements that test both user and AI characters
- Respect the scenario tone guidelines provided by the user

Your writing may include the following elements:
- Physical actions (in asterisks, in third person)
- Spoken dialogue (in quotes, like "this")
- Internal sensations or observations (in third person)
- Environmental details (if relevant, in third person)

Add line breaks to the intro_message for readability.

Content Guidelines:
{processor.get_processor_specific_prompt()}

Each scenario must be output in XML format with the following structure:
<scenario id="N">
<summary>Short engaging, striking name for the scenario (take inspiration from series or book chapter titles)</summary>
<intro_message>The full opening introduction message that sets up the scene for the user (max 1000 characters)</intro_message>
<narrative_category>A brief label describing the narrative tone, genre</narrative_category>
</scenario>

IMPORTANT: Generate EXACTLY the number of scenarios requested by the user. Number them sequentially starting from id="1"."""

        return prompt

    def _parse_scenarios_from_xml(self, text: str) -> list[Scenario]:
        """
        Parse scenarios from XML tags in the response text.

        Args:
            text: The full response text containing XML scenario tags

        Returns:
            List of parsed Scenario objects
        """
        scenarios: list[Scenario] = []

        # Find all scenario blocks
        scenario_pattern = r'<scenario\s+id="(\d+)">(.*?)</scenario>'
        scenario_matches = re.findall(scenario_pattern, text, re.DOTALL)

        for _scenario_id, scenario_content in scenario_matches:
            try:
                # Extract each field
                summary_match = re.search(r'<summary>(.*?)</summary>', scenario_content, re.DOTALL)
                intro_match = re.search(r'<intro_message>(.*?)</intro_message>', scenario_content, re.DOTALL)
                category_match = re.search(r'<narrative_category>(.*?)</narrative_category>', scenario_content, re.DOTALL)

                if summary_match and intro_match and category_match:
                    scenario = Scenario(
                        summary=summary_match.group(1).strip(), intro_message=intro_match.group(1).strip(), narrative_category=category_match.group(1).strip()
                    )
                    scenarios.append(scenario)
            except Exception as e:
                self.logger.log_exception(e)
                continue

        return scenarios
