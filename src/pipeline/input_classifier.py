"""Step 6.1: Classify freeform user input into action, relocation, or time_skip."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import InputClassification

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Classify the user's input into one of three types.

## Types
- "action": an in-location action, dialogue, or interaction. The user is doing something where they are.
- "relocation": the user wants to move to a different location.
- "time_skip": the user wants to skip forward in time."""


class InputClassifier:
    """Classifies freeform user input using a mini model."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def execute(
        self,
        user_input: str,
        known_locations: list[str],
        current_location: str,
        current_time: str,
    ) -> InputClassification:
        """Classify user input into action, relocation, or time_skip."""
        user_message = f"""## User input
{user_input}

## Available locations
{', '.join(known_locations) if known_locations else 'No specific locations established'}

## Current context
Location: {current_location}, Time: {current_time}"""

        try:
            return self.processor.respond_with_model(
                prompt=SYSTEM_PROMPT,
                user_prompt=user_message,
                output_type=InputClassification,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("Input classification failed: %s. Defaulting to action.", e)
            return InputClassification(
                type="action",
                action_text=user_input,
            )
