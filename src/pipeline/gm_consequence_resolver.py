"""Step 6.3b: GM consequence resolution — determine drive/reactive effects after dice."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import GMConsequenceAction, GMConsequenceResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the game master. You determine mechanical consequences of actions now that their outcomes are resolved.

## Rules
{rules_text}

## Your job
For each action, given its resolved outcome (success, failure, auto_succeed, or auto_fail), determine:

1. **drive_effects**: mechanical drive changes on the ACTING character caused by this action's outcome.
   - Can differ based on success vs failure. Examples:
     - Eating succeeds → satiation +3
     - Running and failing → energy -1 (still exerted yourself)
     - Auto-fail at something embarrassing in public → reputation -2
   - Most actions have NO drive effects. Do not invent consequences for mundane actions.

2. **reactive_effects**: mechanical effects on OTHER characters caused by this action's outcome.
   - These are direct, mechanical cross-character consequences, NOT emotional reactions (those are handled separately).
   - Examples:
     - Successful intimidation → target's composure -1
     - Cringeworthy failed flirtation → witness's attraction toward actor drops
     - Successful cooking for someone → target's satiation +2
   - Most actions have NO reactive effects. Only include when the consequence is direct and mechanical.

## Guidelines
- Consider ALL outcomes holistically. If character A deflected character B's action, account for that in B's consequences.
- drive_effects changes: abs ≤ 5 per effect.
- reactive_effects changes: abs ≤ 3 per effect.
- Empty arrays are the correct output for most mundane actions. Do not manufacture consequences.
- One consequence entry per action."""


class GMConsequenceResolver:
    """Determines mechanical consequences after dice resolution (step 6.3b)."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def execute(
        self,
        outcomes: list[dict[str, str]],
        rules_text: str,
        location: str,
        time: str,
        characters_present: list[str],
        drive_schema_summary: str,
    ) -> GMConsequenceResult:
        """Resolve consequences for all actions given their outcomes."""
        system = SYSTEM_PROMPT.format(rules_text=rules_text)

        # Build outcomes list
        outcome_lines = []
        for o in outcomes:
            line = f"- {o['character']}: {o['action_summary']} → {o['result']}"
            if o.get("roll_details"):
                line += f" ({o['roll_details']})"
            outcome_lines.append(line)

        user_message = f"""Determine consequences for the following outcomes.

## Action outcomes this turn
{chr(10).join(outcome_lines)}

## World state
Location: {location}, Time: {time}
Present: {', '.join(characters_present)}

## Drive schema
{drive_schema_summary}"""

        try:
            return self.processor.respond_with_model(
                prompt=system,
                user_prompt=user_message,
                output_type=GMConsequenceResult,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("GM consequence resolution failed: %s. No effects this turn.", e)
            return GMConsequenceResult(consequences=[
                GMConsequenceAction(
                    character=o.get("character", ""),
                    action_ref=o.get("action_summary", ""),
                    reasoning="Consequence resolution unavailable",
                )
                for o in outcomes
            ])
