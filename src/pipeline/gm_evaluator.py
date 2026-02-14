"""Step 6.3: GM evaluation of actions for skill checks and drive effects."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import GMActionEvaluation, GMEvaluationResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the game master. You evaluate character actions to determine if skill checks are needed.

## Rules
{rules_text}

## Your job
For each action this turn:
1. Determine if the action is trivial/mundane (auto-succeeds) or uncertain/risky (needs a skill check).
2. If a check is needed: identify which skill applies and set a difficulty class (DC).
3. If two characters act against each other: flag both as contested and identify the relevant skill for each side.

## Guidelines
- Mundane actions auto-succeed: walking, talking, picking up objects, basic observations.
- Checks are for: persuasion, deception, stealth, physical feats, anything with meaningful failure consequences.
- DC reflects difficulty given the specific situation, not the character's skill level.
- DC range: 5 (easy) to 25 (near-impossible). Most checks should be 8-18.
- Physically impossible actions always fail — do not set a DC, instead set check_required to false and explain why.

drive_effects: mechanical consequences of this action on the acting character's drives, applied only if the action succeeds. Most actions have no drive effects. Examples: eating → satiation +3, physical exertion → energy -1.

departure: true if this action, on success, results in the character leaving the current location."""


class GMEvaluator:
    """Evaluates actions for skill checks using a large model."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def execute(
        self,
        actions: list[dict[str, str]],
        rules_text: str,
        location: str,
        time: str,
        characters_present: list[str],
        skills_by_character: dict[str, dict[str, float]],
        drive_schema_summary: str,
    ) -> GMEvaluationResult:
        """Evaluate all actions for this turn."""
        system = SYSTEM_PROMPT.format(rules_text=rules_text)

        # Build actions list
        action_lines = []
        for a in actions:
            line = f"- {a['character']}: [{a['type']}] {a['description']}"
            if a.get("target"):
                line += f" (target: {a['target']})"
            action_lines.append(line)

        # Build skills summary
        skill_lines = []
        for name, skills in skills_by_character.items():
            skills_str = ", ".join(f"{k}: {v:.0f}" for k, v in skills.items())
            skill_lines.append(f"{name}: {skills_str}")

        user_message = f"""## Actions this turn
{chr(10).join(action_lines)}

## World state
Location: {location}, Time: {time}
Present: {', '.join(characters_present)}

## Relevant skill values
{chr(10).join(skill_lines)}

## Drive schema
{drive_schema_summary}"""

        try:
            return self.processor.respond_with_model(
                prompt=system,
                user_prompt=user_message,
                output_type=GMEvaluationResult,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("GM evaluation failed: %s. Auto-succeeding all actions.", e)
            return GMEvaluationResult(evaluations=[
                GMActionEvaluation(
                    character=a.get("character", ""),
                    action_summary=a.get("description", ""),
                    reasoning="Auto-success fallback",
                    check_required=False,
                )
                for a in actions
            ])
