"""Step 6.9: Generate continuation options for the user."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import ContinuationOptionsResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Suggest 2-4 options for what the user character could do next.

## Rules
- Options should be varied: different approaches to the situation, not minor variations of the same action.
- Include at least one option that engages with present characters (if any are present).
- If the situation naturally suggests it, include a relocation option ("Go to [specific location]") or time skip ("Wait until [specific time or event]").
- Each option is brief: a short phrase describing the action.
- Do not suggest actions that repeat what the user just did.
- Tag each option with its type.

## Available locations
{known_locations}"""


class ContinuationGenerator:
    """Generates continuation options for the user after narration."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def execute(
        self,
        location: str,
        time: str,
        characters_present: list[str],
        narration_summary: str,
        user_character_brief: str,
        user_drives_summary: str,
        user_emotional_state_summary: str,
        known_locations: list[str],
    ) -> ContinuationOptionsResult:
        """Generate 2-4 continuation options."""
        system = SYSTEM_PROMPT.format(
            known_locations=", ".join(known_locations) if known_locations else "No specific locations established",
        )

        user_message = f"""## Current situation
Location: {location}, Time: {time}
Present: {', '.join(characters_present)}

## What just happened
{narration_summary}

## User character
{user_character_brief}
Drives: {user_drives_summary}
Emotional state: {user_emotional_state_summary}"""

        try:
            return self.processor.respond_with_model(
                prompt=system,
                user_prompt=user_message,
                output_type=ContinuationOptionsResult,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("Continuation generation failed: %s. Returning empty.", e)
            return ContinuationOptionsResult(options=[])
