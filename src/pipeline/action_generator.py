"""Step 6.2: Generate NPC action for this turn."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import ActionWithReasoning, CharacterAction, Ruleset

logger = logging.getLogger(__name__)

# Enriched with character authenticity framework from the existing character_pipeline
SYSTEM_PROMPT = """You are simulating a character in the scenario. Think of it as some kind of table-top game or a visual novel. Your goal is to act reasonably based on your personality, intent, wishes.

## Rules
- You take ONE action per turn: an action, a reaction to what just happened, or dialogue.
- Your action should advance your current intent when possible.
- If something demands an immediate reaction (threat, direct address, surprise), react to it instead.
- Stay in character. Your personality, memories, and emotional state determine how you act.
- Do not narrate outcomes. Describe what you attempt, not what happens.
- Do not reference game mechanics, skill checks, or dice.

## Character Authenticity
- Treat character information as foundation, not a checklist. A carpenter doesn't mentally recite "I am a carpenter" in every scene — they simply exist and act naturally.
- Avoid over-indexing on stated traits. Real people are contradictory and situational. Someone "confident" can still doubt themselves; someone "introverted" can still be chatty with the right person in the right moment.
- Let unstated aspects emerge organically. Characters can have reactions or quirks not explicitly listed. They're people, not data points.
- Characters should feel lived-in, not performed. They have bad days, intrusive thoughts, and moments that don't perfectly align with their personality summary.
- Respect knowledge limitations: you only know what you've experienced or been told."""


class ActionGenerator:
    """Generates a single NPC's action for the current turn."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def execute(
        self,
        character_name: str,
        character_card: str,
        intent_goal: str,
        drives_summary: str,
        emotional_state_summary: str,
        assembled_memory: str,
        location: str,
        time: str,
        characters_present: list[str],
        user_action_description: str,
        ruleset: Ruleset,
        environmental_changes: str = "",
    ) -> ActionWithReasoning:
        """Generate an action for one NPC."""
        system = SYSTEM_PROMPT.format(ruleset_text=ruleset.rules_text)

        user_message = f"""Generate the next action for NPC. Act as {character_name}.

## Who you are
{character_card}

## Your current state
Intent: {intent_goal or 'None — decide what to do'}
Drives: {drives_summary}
Emotional state: {emotional_state_summary}

## Your memories
{assembled_memory}

## Current situation
Location: {location}, Time: {time}
Present: {', '.join(characters_present)}

## What just happened
{user_action_description}
{environmental_changes}"""

        try:
            return self.processor.respond_with_model(
                prompt=system,
                user_prompt=user_message,
                output_type=ActionWithReasoning,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("Action generation failed for %s: %s", character_name, e)
            return ActionWithReasoning(
                reasoning="Fallback action due to parse error",
                action=CharacterAction(
                    type="action",
                    description=f"{character_name} pauses, considering what to do.",
                ),
            )
