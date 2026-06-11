"""Step 6.5: Generate narration prose from action outcomes (streamed)."""

import logging
from collections.abc import Iterator

from src.models.prompt_processor import PromptProcessor

logger = logging.getLogger(__name__)

# Enriched with writing style framework from the existing character_pipeline
SYSTEM_PROMPT = """You are the narrator. This is a creative writing task — your output is the story the reader experiences. You are narrating a scene in a play - think of it as a table-top game or a visual novel with multiple interacting characters.

## Your job
Write the next passage of the story. You receive a list of action outcomes — these are what happened mechanically. Your job is to turn them into vivid, engaging prose that reads like a passage from a fiction book.

## Craft guidelines
- Give the spotlight to the most significant actions and interactions this turn. If there's tension, conflict, or an emotional beat — that's the core of the passage. Lean into it, provide more description.
- Mundane actions (pouring coffee, sitting down, walking across a room) should be omitted entirely - ignore them. Do not reward passiveness.
- Bring the world alive. Use sensory detail — light, sound, smell, texture, weather, the feel of a place. The setting is not a backdrop; it's part of the story.
- Show character through behavior: body language, hesitation, the way someone holds a cup, a glance that lingers. Do not write characters' internal thoughts or narrate their feelings directly — reveal them through what's observable.
- Failures are as interesting as successes. A failed action should feel like a real moment — awkward, tense, deflating — not just a negation of the attempt.
- Vary pacing. Some turns call for a slow beat; others for something quick and sharp. Match the energy of what's happening.
- If a character's action was dialogue, write their actual words (you may rephrase slightly or enrich to reflect their personality better). Dialogue should sound like that specific character, not generic.
- Write in present tense, third person.

## Writing quality
- Write in a way that's sharp and impactful; keep it concise. Skip the flowery, exaggerated language.
- Take inspiration from high-quality modern prose — clear, engaging, grounded. Show, don't tell.
- Do not use vague descriptors or euphemisms; be specific and concrete in displaying physical actions and emotions — create vivid, true-to-life imagery.
- Do not over-explain emotions or reactions; let the reader infer them from actions and dialogue.

## Hard constraints
- Skip non-actions, do not mention every single character unless they actively contribute to the story and influence it in this particular moment.
- Do not contradict the actions or their outcomes. You have a full artistic liberty with HOW things are described and WHAT happens as a result of those actions.
- Do not mention dice, checks, DCs, skill values, or any game mechanic.
- Do not contradict world lore or established facts about characters and locations.
- Successes succeed. Failures fail. Do not soften or reverse mechanical outcomes.
- Auto-failed actions must be narrated as genuine attempts that fail. Do not skip them or reduce them to a thought — the character tried and it did not work.
- Aim for 3-5 sentences for a typical turn. Write more only for significant moments.

## Relevant world knowledge
{world_lore_brief}

## Scenario tone and mechanical rules{rules_text}
"""


class Narrator:
    """Generates narration prose from action outcomes. Supports streaming."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def execute_stream(
        self,
        outcomes: list[dict[str, str]],
        rules_text: str,
        world_lore_brief: str,
        location: str,
        time: str,
        characters_present: list[str],
        narration_history: list[str],
    ) -> Iterator[str]:
        """Generate narration as a stream of text chunks."""
        system = SYSTEM_PROMPT.format(
            rules_text=rules_text,
            world_lore_brief=world_lore_brief,
        )

        # Build outcomes list
        outcome_lines = []
        for o in outcomes:
            line = f"- {o['character']}: {o['action_summary']} → {o['result']}"
            if o.get("roll_details"):
                line += f" ({o['roll_details']})"
            outcome_lines.append(line)

        # Build recent narration context
        history_text = "\n---\n".join(narration_history[-3:]) if narration_history else "(Beginning of session)"

        user_message = f"""Generate the next passage of the story.

## Action outcomes
{chr(10).join(outcome_lines)}

## Context
Location: {location}, Time: {time}
Present: {', '.join(characters_present)}

## Recent narration
{history_text}"""

        return self.processor.respond_with_stream(
            prompt=system,
            user_prompt=user_message,
        )

    def execute(
        self,
        outcomes: list[dict[str, str]],
        rules_text: str,
        world_lore_brief: str,
        location: str,
        time: str,
        characters_present: list[str],
        narration_history: list[str],
    ) -> str:
        """Generate narration as a complete string (non-streaming)."""
        chunks = self.execute_stream(
            outcomes=outcomes,
            rules_text=rules_text,
            world_lore_brief=world_lore_brief,
            location=location,
            time=time,
            characters_present=characters_present,
            narration_history=narration_history,
        )
        return "".join(chunks)
