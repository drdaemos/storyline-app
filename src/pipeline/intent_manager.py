"""Step 6.8: Intent lifecycle — reevaluation, generation, and completion check."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import (
    Intent,
    IntentCompletionCheck,
    IntentReevaluation,
)

logger = logging.getLogger(__name__)

REEVALUATION_SYSTEM_PROMPT = """You are {character_name}. You just had a new realization. Decide whether it changes what you want to do.

## Who you are
{character_card_brief}

## Rules
- Characters are committed. They don't abandon goals on a whim.
- Change the intent only if the new realization directly contradicts it, makes it impossible, or reveals something that shifts priorities.
- If the intent is still valid, keep it."""

GENERATION_SYSTEM_PROMPT = """You are {character_name}. Decide what you want to do right now.

## Who you are
{character_card}

## Rules
- Pick ONE concrete, actionable goal that makes sense given your personality, current state, and situation.
- The goal must be specific to this moment: "ask Marta why she's upset" not "be a good friend."
- Consider your drives — if any are low, you may be motivated to address them.
- Consider your recent memories — unresolved situations or interesting opportunities.
- The success condition is how you'd know the goal is met. Use a drive threshold if the goal is drive-related (e.g., satiation > 7). Otherwise describe it briefly."""

COMPLETION_SYSTEM_PROMPT = """Has this character's goal been achieved?

## Rules
- Judge based only on the events provided. Do not speculate about offscreen events.
- The goal is complete only if the success condition has been clearly met.
- If ambiguous or partially met, it is not complete."""


class IntentManager:
    """Manages the intent lifecycle for NPCs: reevaluation, generation, and completion."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def reevaluate(
        self,
        character_name: str,
        character_card_brief: str,
        active_intent_goal: str,
        active_intent_success_condition: str,
        reflection_content: str,
        drives_summary: str,
        emotional_state_summary: str,
    ) -> IntentReevaluation:
        """Step 6.8a: Decide whether a reflection invalidates the current intent."""
        system = REEVALUATION_SYSTEM_PROMPT.format(
            character_name=character_name,
            character_card_brief=character_card_brief,
        )

        user_message = f"""## Your current intent
{active_intent_goal}
Success condition: {active_intent_success_condition}

## New realization
{reflection_content}

## Your current state
Drives: {drives_summary}
Emotional state: {emotional_state_summary}"""

        try:
            return self.processor.respond_with_model(
                prompt=system,
                user_prompt=user_message,
                output_type=IntentReevaluation,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("Intent reevaluation failed for %s: %s. Keeping intent.", character_name, e)
            return IntentReevaluation(reasoning="Fallback — keeping intent due to error.", keep=True)

    def generate(
        self,
        character_name: str,
        character_card: str,
        drives_summary: str,
        emotional_state_summary: str,
        assembled_memory: str,
        location: str,
        time: str,
        characters_present: list[str],
    ) -> Intent:
        """Step 6.8b: Generate a new intent for a character."""
        system = GENERATION_SYSTEM_PROMPT.format(
            character_name=character_name,
            character_card=character_card,
        )

        user_message = f"""## Your current state
Drives: {drives_summary}
Emotional state: {emotional_state_summary}

## Your memories
{assembled_memory}

## Current situation
Location: {location}, Time: {time}
Present: {', '.join(characters_present)}"""

        try:
            return self.processor.respond_with_model(
                prompt=system,
                user_prompt=user_message,
                output_type=Intent,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("Intent generation failed for %s: %s", character_name, e)
            from src.models.simulation import SuccessCondition

            return Intent(
                goal="Observe the situation and decide what to do.",
                success_condition=SuccessCondition(
                    type="narrative",
                    description="Has formed a clear plan of action.",
                ),
                source_refs=[],
            )

    def check_completion(
        self,
        active_intent_goal: str,
        success_condition_description: str,
        recent_events: str,
    ) -> IntentCompletionCheck:
        """Step 6.8c: Check if a narrative intent has been completed."""
        user_message = f"""## Goal
{active_intent_goal}

## Success condition
{success_condition_description}

## Recent events for this character
{recent_events}"""

        try:
            return self.processor.respond_with_model(
                prompt=COMPLETION_SYSTEM_PROMPT,
                user_prompt=user_message,
                output_type=IntentCompletionCheck,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("Intent completion check failed: %s. Assuming not complete.", e)
            return IntentCompletionCheck(reasoning="Fallback — assuming not complete.", complete=False)
