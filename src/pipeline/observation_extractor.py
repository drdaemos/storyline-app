"""Step 6.6: Extract observations from narration."""

import logging

from src.models.prompt_processor import PromptProcessor
from src.models.simulation import ObservationExtractionResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Extract notable events from the narration as shared observations.

## Rules
- List only events worth remembering: actions that affect someone, reveal information, shift dynamics, or are surprising.
- OMIT routine, mundane actions: walking, sitting down, generic greetings, eating without significance, idle movement. If it wouldn't change how anyone thinks or feels, leave it out.
- Write in third person, factual. Describe what happened, not what anyone thinks about it.
- One sentence per observation. Be specific.
- Assign importance: 2 (minor but notable) to 5 (directly confrontational, revealing, or surprising). Do not output importance 1 — those events should be omitted entirely.
- Assign visibility: "public" for actions anyone present could see/hear. "actor_only" for successful stealth actions.
- Failed stealth actions are "public" — the attempt was noticed.

Return an empty observations array if nothing notable happened this turn."""


class ObservationExtractor:
    """Extracts observations from narration using a mini model."""

    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def execute(
        self,
        narration: str,
        outcomes: list[dict[str, str]],
        characters_present: list[str],
    ) -> ObservationExtractionResult:
        """Extract observations from this turn's narration."""
        outcome_lines = []
        for o in outcomes:
            line = f"- {o['character']}: {o['action_summary']} → {o['result']}"
            if o.get("stealth_result"):
                line += f" [stealth: {o['stealth_result']}]"
            outcome_lines.append(line)

        user_message = f"""Create observations from the narration.

## Narration this turn
{narration}

## Action outcomes
{chr(10).join(outcome_lines)}

## Characters present
{', '.join(characters_present)}"""

        try:
            return self.processor.respond_with_model(
                prompt=SYSTEM_PROMPT,
                user_prompt=user_message,
                output_type=ObservationExtractionResult,
                reasoning=False,
            )
        except Exception as e:
            logger.warning("Observation extraction failed: %s. Returning empty.", e)
            return ObservationExtractionResult(observations=[])
