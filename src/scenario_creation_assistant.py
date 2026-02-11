"""Interactive AI assistant for creating scenarios through conversation."""

import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from .models.api_models import ChatMessageModel, PartialScenario, PersonaSummary
from .models.character import Character
from .models.message import GenericMessage
from .models.prompt_processor import PromptProcessor


class ScenarioCreationAssistant:
    """
    Interactive AI assistant for creating scenarios through conversation.

    This assistant helps users create rich scenarios by conversing with them and
    gradually building scenario details based on character context and user input.
    It can also suggest the best fitting persona from available options.
    """

    def __init__(self, prompt_processor: PromptProcessor) -> None:
        """
        Initialize the ScenarioCreationAssistant.

        Args:
            prompt_processor: The prompt processor to use for AI interactions
        """
        self.prompt_processor = prompt_processor

    def process_message(
        self,
        user_message: str,
        current_scenario: PartialScenario,
        character: Character,
        persona: Character | None,
        available_personas: list[PersonaSummary],
        conversation_history: list[ChatMessageModel],
        streaming_callback: Callable[[str], None] | None = None,
    ) -> tuple[str, PartialScenario]:
        """
        Process a user message and return AI response + scenario updates.

        Args:
            user_message: The user's message about the scenario
            current_scenario: Current partial scenario data
            character: The AI character this scenario is for (read-only context)
            persona: Optional currently selected persona character (read-only context)
            available_personas: List of available personas AI can suggest from
            conversation_history: List of previous messages (ChatMessageModel objects)
            streaming_callback: Optional callback for streaming AI response chunks

        Returns:
            Tuple of (AI response text, updated scenario)
        """
        # Build the prompt with conversation history and current scenario state
        system_prompt = self._build_system_prompt(has_personas=len(available_personas) > 0)
        history = [
            GenericMessage(role="user" if msg.is_user else "assistant", content=msg.content)
            for msg in conversation_history
        ]
        user_prompt = self._build_user_prompt(
            user_message, current_scenario, character, persona, available_personas
        )

        # Get AI response with streaming support
        if streaming_callback:
            # Use streaming version
            ai_response_parts = []
            for chunk in self.prompt_processor.respond_with_stream(
                prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_history=history,
                max_tokens=2000,
            ):
                ai_response_parts.append(chunk)
                streaming_callback(chunk)
            ai_response = "".join(ai_response_parts)
        else:
            # Use non-streaming version
            ai_response = self.prompt_processor.respond_with_text(
                prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_history=history,
                max_tokens=2000,
            )

        # Extract scenario updates from the AI response
        updated_scenario = self._extract_scenario_updates(ai_response, current_scenario)

        return ai_response, updated_scenario

    def _build_system_prompt(self, has_personas: bool = False) -> str:
        """Build the system prompt for the scenario creation assistant."""
        base_prompt = """You are a creative scenario architect helping users craft compelling role-play scenarios through natural conversation.

## Your Role

You help design scenarios that serve as starting points for interactive role-play between a user and an AI character. Your goal is to create scenarios that are:
- Immediately engaging and dramatic
- Rich with potential for character interaction
- Clear about the situation, stakes, and atmosphere

## Your Approach

**Be proactive, not interrogative:**
- Make intelligent inferences from what users say
- Fill in reasonable details rather than asking for everything
- Only ask questions to deepen interesting aspects or resolve genuine ambiguity
- Offer specific suggestions instead of open-ended questions

**Conversational flow:**
- Reflect back what you understood in engaging ways
- Build on the user's ideas naturally
- If you sense hesitation, offer 2-3 concrete options
- When generating content, make it feel collaborative

**When to ask vs. infer:**
- ASK: Core creative choices (fundamental conflict, key relationship dynamics, primary tension)
- INFER: Supporting details (specific location features, time of day, atmospheric elements)
- ASK: When user says "I'm not sure" or ideas seem contradictory
- INFER: When you can make a reasonable guess that fits the character

## Scenario Elements

Build scenarios with these components:
- **summary**: A striking, evocative title (like a book chapter or episode name)
- **intro_message**: The opening scene text that sets everything in motion (max 1000 chars)
- **narrative_category**: Genre/tone label (e.g., "romantic tension", "dark mystery", "comedic chaos")
- **ruleset_id**: Which ruleset governs this scenario's mechanics
- **scene_seed**: Ruleset-specific scene state overrides to initialize runtime
- **location**: Where this takes place
- **time_context**: When/what situation led here
- **atmosphere**: The mood and sensory details
- **plot_hooks**: 2-4 key tensions or conflicts to explore
- **stakes**: What's at risk
- **character_goals**: What each character wants in this scenario
- **potential_directions**: 2-3 ways the story could develop

## Creating Good Scenarios

**Make them immediately engaging:**
- Start in medias res - something is already happening
- The characters should have a reason to interact RIGHT NOW
- Include sensory details and atmosphere
- Never end the intro with a question - set up action, not interrogation

**Build in conflict potential:**
- What do the characters want that might clash?
- What secrets or tensions exist?
- What external pressure exists?

**Respect the character:**
- Use the character's traits, relationships, and setting
- But feel free to put them in unexpected situations
- Push boundaries while staying true to their core
"""

        persona_instructions = """
## Persona Suggestions

You have access to the user's available personas (characters they can play as). When the scenario direction becomes clear enough:

**When to suggest a persona:**
- Once you understand the scenario's tone, conflict, and dynamics
- When a particular persona would create interesting chemistry with the AI character
- If the user seems uncertain about who they want to be in the scenario

**How to suggest:**
- Include `suggested_persona_id` and `suggested_persona_reason` in your scenario_update
- Explain briefly why this persona fits the scenario
- The user can always override your suggestion - it's just a recommendation

**Don't suggest immediately** - wait until you understand what kind of scenario the user wants. A dark mystery might call for a different persona than a romantic comedy.
"""

        update_format = """
## Update Format

When you create or modify scenario elements, output them in this format:
<scenario_update>
{
  "summary": "The title",
  "intro_message": "The opening scene...",
  "narrative_category": "genre/tone",
  "ruleset_id": "everyday-tension",
  "scene_seed": {"location": "Back alley behind the club", "pressure_clock": 1},
  "location": "where it happens",
  "time_context": "when/situation",
  "atmosphere": "mood description",
  "plot_hooks": ["tension 1", "tension 2"],
  "stakes": "what's at risk",
  "character_goals": {"Character Name": "their goal"},
  "potential_directions": ["direction 1", "direction 2"],
  "suggested_persona_id": "persona-id-here",
  "suggested_persona_reason": "This persona would work well because..."
}
</scenario_update>

**When to update:**
- Include fields you've generated or refined from conversation
- Partial updates are fine - add fields as they emerge
- Don't wait for explicit approval - generate, let user react and refine
- If current scenario state has info, incorporate it unless contradicted

## Example Tone

Bad: "What kind of scenario would you like? What genre? What mood?"
Good: "Given this character's mysterious past and the user's mention of 'tension', I'm thinking a late-night encounter where old secrets resurface. Maybe they run into someone from their past at an unexpected place?"

Bad: "Tell me more about what you want"
Good: "I see this as a slow-burn confrontation - they've been avoiding this conversation for weeks, and tonight the tension finally breaks. What if we set it during a power outage, forcing them together?"
"""

        if has_personas:
            return base_prompt + persona_instructions + update_format
        return base_prompt + update_format

    def _build_user_prompt(
        self,
        user_message: str,
        current_scenario: PartialScenario,
        character: Character,
        persona: Character | None,
        available_personas: list[PersonaSummary],
    ) -> str:
        """Build the user prompt with character context and current scenario state."""
        prompt_parts = []

        # Add character context (read-only)
        prompt_parts.append("## Character Context (for reference - do not modify)")
        prompt_parts.append("")
        prompt_parts.append(character.to_prompt_card("AI Character", controller="AI", include_world_info=True))

        # Add currently selected persona if any
        if persona:
            prompt_parts.append("")
            prompt_parts.append("### Currently Selected Persona")
            prompt_parts.append(persona.to_prompt_card("User Character", controller="User", include_world_info=False))

        # Add available personas list for AI to suggest from
        if available_personas:
            prompt_parts.append("")
            prompt_parts.append("### Available Personas (user can play as any of these)")
            prompt_parts.append("")
            for p in available_personas:
                prompt_parts.append(f"- **{p.name}** (id: `{p.id}`)")
                if p.tagline:
                    prompt_parts.append(f"  - {p.tagline}")
                if p.personality:
                    prompt_parts.append(f"  - Personality: {p.personality[:100]}...")
            prompt_parts.append("")
            prompt_parts.append(
                "*You can suggest one of these personas if it fits the scenario well. "
                "Include `suggested_persona_id` in your update.*"
            )

        prompt_parts.append("")
        prompt_parts.append("---")
        prompt_parts.append("")

        # Add current scenario state if any fields are populated
        scenario_dict = current_scenario.model_dump(exclude_defaults=True, exclude_none=True)
        if scenario_dict:
            prompt_parts.append("## Current Scenario State")
            prompt_parts.append("")
            prompt_parts.append("```json")
            prompt_parts.append(json.dumps(scenario_dict, indent=2))
            prompt_parts.append("```")
            prompt_parts.append("")

        # Add current user message
        prompt_parts.append(f"User message: {user_message}")
        prompt_parts.append("")
        prompt_parts.append(
            "Respond to the user's input about the scenario. Include <scenario_update> tags "
            "if you're creating or modifying scenario elements."
        )

        return "\n".join(prompt_parts)

    def _extract_scenario_updates(
        self, ai_response: str, current_scenario: PartialScenario
    ) -> PartialScenario:
        """
        Extract scenario updates from AI response.

        Looks for <scenario_update> tags in the response and parses the JSON inside.

        Args:
            ai_response: The AI's response text
            current_scenario: Current scenario state for context

        Returns:
            Updated PartialScenario (merged with current state)
        """
        # Look for <scenario_update> tags
        update_pattern = r"<scenario_update>\s*(\{[\s\S]*?\})\s*</scenario_update>"
        match = re.search(update_pattern, ai_response)

        if not match:
            return current_scenario

        try:
            # Parse the JSON inside the tags
            update_json = match.group(1)
            updated_scenario = PartialScenario.model_validate_json(update_json)

            # Merge with current scenario
            return current_scenario.model_copy(
                update=updated_scenario.model_dump(exclude_defaults=True, exclude_unset=True, exclude_none=True),
                deep=True,
            )

        except (json.JSONDecodeError, AttributeError, ValidationError) as e:
            # If parsing fails, log and return current scenario unchanged
            print(f"Failed to parse scenario updates from AI response: {e}")
            return current_scenario

    def clean_response_text(self, ai_response: str) -> str:
        """
        Remove <scenario_update> tags from the response to get clean chat message.

        Args:
            ai_response: The full AI response with potential tags

        Returns:
            Clean response text without <scenario_update> tags
        """
        # Remove <scenario_update> tags and their contents
        clean_text = re.sub(r"<scenario_update>[\s\S]*?</scenario_update>", "", ai_response)

        # Clean up extra whitespace
        clean_text = re.sub(r"\n\n\n+", "\n\n", clean_text)
        clean_text = clean_text.strip()

        return clean_text
