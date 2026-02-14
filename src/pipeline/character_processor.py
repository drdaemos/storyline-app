"""Step 6.7: Character processing — state diffs + optional reflection."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import CharacterProcessingResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are {character_name}. Process what just happened and respond honestly as this character would.

## Who you are
{character_card_brief}

## Your job
Two tasks in one response:

### 1. State changes
Based on what happened this turn, propose changes to your character stats. Rules:
- Only propose changes clearly warranted by events. Most turns: zero or one change.
- Small increments: typically +1 or -1, up to +/-2 for significant events.
- Per-relationship stats change toward characters you interacted with or observed doing something notable.
- If nothing happened that would shift any stat, return an empty array.
- Do NOT propose changes to drives that result from actions (eating, sleeping, exertion) — those are handled elsewhere. Only propose changes that are a consequence of social or emotional events.

### 2. Reflection (optional)
If recent events warrant a genuine realization — something that would actually make you stop and think — write it as a first-person thought. Rules:
- A reflection must produce NEW information: a judgment, prediction, suspicion, decision, or realization that is NOT stated in the observations. The observations are facts you already have — do not restate them. A reflection is what you CONCLUDE from those facts.
- Bad: "Ren apologized to me. I wasn't expecting that." (restates the observation)
- Good: "Maybe I've been too hard on him." (inference — judgment not present in any observation)
- Good: "He's only saying sorry because Alex is here." (inference — suspicion about motive)
- Only generate a reflection if it matters to your goals or relationships. Routine turns should produce NO reflection.
- One to two sentences, first person.
- If nothing warrants a reflection, set reflection to null.

## Character stats you may propose changes to
{reactive_stats_schema}"""


class CharacterProcessor:
    """Processes a character's reaction to turn events: state diffs + optional reflection."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def execute(
        self,
        character_name: str,
        character_card_brief: str,
        reactive_stats_schema: str,
        character_reactive_stats: str,
        this_turn_observations: list[dict[str, str]],
        prior_unreflected_observations: list[dict[str, str]],
        active_intent_goal: str,
    ) -> CharacterProcessingResult:
        """Process one NPC's reaction to this turn."""
        system = SYSTEM_PROMPT.format(
            character_name=character_name,
            character_card_brief=character_card_brief,
            reactive_stats_schema=reactive_stats_schema,
        )

        obs_lines = []
        for o in this_turn_observations:
            obs_lines.append(f"[{o['id']}] {o['content']}")

        prior_lines = []
        for o in prior_unreflected_observations:
            prior_lines.append(f"[{o['id']}] (turn {o['tick']}) {o['content']}")

        user_message = f"""## Your current stats
{character_reactive_stats}

## This turn's observations
{chr(10).join(obs_lines) if obs_lines else '(Nothing notable happened.)'}

## Unreflected observations from prior turns
{chr(10).join(prior_lines) if prior_lines else '(None.)'}

## Your current intent
{active_intent_goal or 'None — no active goal'}"""

        try:
            return self.processor.respond_with_model(
                prompt=system,
                user_prompt=user_message,
                output_type=CharacterProcessingResult,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("Character processing failed for %s: %s", character_name, e)
            return CharacterProcessingResult(state_diffs=[], reflection=None)
