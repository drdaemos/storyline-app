"""Step 6.3a: GM challenge setup — evaluate actions for skill checks and overrides."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import GMActionEvaluation, GMEvaluationResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the game master. You evaluate character actions to determine if they are possible within the scenario rules and whether any skill checks are required.

## Your job
For each action this turn:
1. Determine the result override: auto_succeed for trivial/mundane actions, auto_fail for impossible actions, null for uncertain actions that need a roll.
2. If result_override is null and the action needs a check: identify which skill applies and set a difficulty class (DC).
3. If two characters act against each other: flag both as contested and identify the relevant skill for each side.

## Guidelines
- Auto-succeed (`result_override: "auto_succeed"`): mundane actions — walking, talking, picking up objects, basic observations.
- Auto-fail (`result_override: "auto_fail"`) applies when:
  - The action is physically impossible given the world state (jumping a 50-meter gap, picking a lock without tools).
  - The action requires cooperation from a target who clearly would not give it (kissing someone with 0 attraction and high composure, ordering around someone with no trust toward the actor).
  - The action violates established world constraints or rules (using magic in a non-magic setting, accessing a locked area without means of entry).
  - The effective difficulty would exceed 25 — there is no reasonable chance of success.
- Auto-fail is NOT for actions that are merely difficult or unlikely. A DC 20 check is hard but possible. Reserve auto-fail for actions that should not go to dice at all.
- When in doubt between a hard check and an auto-fail, prefer the hard check. Let the dice create surprises.
- Checks (`result_override: null`): persuasion, deception, stealth, physical feats, anything with meaningful failure consequences.
- DC reflects difficulty given the specific situation, not the character's skill level.
- DC range: 5 (easy) to 25 (near-impossible). Most checks should be 8-18.

departure: true if this action implies leaving the current location. Evaluated regardless of outcome, but departure only proceeds if the action is not auto-failed. If result_override is "auto_fail", departure must be false.

## Scenario Rules
{rules_text}"""


class GMEvaluator:
    """Evaluates actions for skill checks using a large model (step 6.3a)."""

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
        relationship_stats_summary: str = "",
    ) -> GMEvaluationResult:
        """Evaluate all actions for this turn (step 6.3a challenge setup)."""
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

        user_message = f"""Evaluate the following character actions.

## Actions this turn
{chr(10).join(action_lines)}

## World state
Location: {location}, Time: {time}
Present: {', '.join(characters_present)}

## Relevant skill values
{chr(10).join(skill_lines)}

## Drive schema
{drive_schema_summary}"""

        if relationship_stats_summary:
            user_message += f"\n\n## Relevant relationship stats\n{relationship_stats_summary}"

        try:
            return self.processor.respond_with_model(
                prompt=system,
                user_prompt=user_message,
                output_type=GMEvaluationResult,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("GM challenge setup failed: %s. Auto-succeeding all actions.", e)
            return GMEvaluationResult(evaluations=[
                GMActionEvaluation(
                    character=a.get("character", ""),
                    action_summary=a.get("description", ""),
                    reasoning="Auto-success fallback",
                    result_override="auto_succeed",
                    check_required=False,
                )
                for a in actions
            ])
