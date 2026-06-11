"""VNNarrator: prose from skeleton + state + history at play time.

The narration boundary is fixed by the system design: narration MUST NOT change
any outcome, state value, or check result. That is enforced structurally — the
narrator receives read-only snapshots (events, view, history) and returns text;
it has no reference to the engine or session.
"""

from collections.abc import Iterator

from src.models.prompt_processor import PromptProcessor
from src.models.vn.runtime import (
    BeatEntered,
    CheckResolved,
    ChoiceMade,
    EndingReached,
    EngineEvent,
    EngineView,
    SceneEntered,
    WentDeeper,
)

NARRATOR_SYSTEM_PROMPT = """You are the narrator of an interactive visual novel.
You receive a sequence of structural story events (terse intents — what happened) and you turn ONLY those events into vivid second-person prose.

Hard rules:
- Narrate exactly the given events, in order. Do not invent new events, choices, items, injuries, or revelations.
- Never change or foreshadow an outcome: a failed check stays failed, a success stays a success.
- When a check result is given, dramatize the attempt and its given result; do not soften it.
- If the events end at a pending choice, end your narration at the moment of decision without resolving it. Do not list the options; the interface shows them.
- If asked to "go deeper" on a moment, elaborate strictly within the given domain: sensory detail, atmosphere, interiority. Nothing that changes what can happen next.
- Match the story's established tone. Be concise: a few paragraphs at most."""


class VNNarrator:
    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def narrate(self, title: str, protagonist: str, events: list[EngineEvent], view: EngineView, history: list[str]) -> Iterator[str]:
        """Stream prose for the given engine events. Inputs are snapshots; nothing here can write back."""
        return self.processor.respond_with_stream(
            prompt=NARRATOR_SYSTEM_PROMPT,
            user_prompt=self._user_prompt(title, protagonist, events, view, history),
        )

    def _user_prompt(self, title: str, protagonist: str, events: list[EngineEvent], view: EngineView, history: list[str]) -> str:
        lines = [f"Story: {title}. Protagonist: {protagonist}."]
        if history:
            lines.append("## Narration so far (most recent last)")
            lines.extend(history)
        lines.append("## Current state (context only; do not recite)")
        lines.append(", ".join(f"{name}={value}" for name, value in view.vars.items()) or "(no state)")
        lines.append("## Events to narrate now")
        lines.extend(self._describe(event) for event in events)
        if view.pending is not None and view.pending.kind == "choice":
            lines.append(f"(Narration must end at this open decision: {view.pending.prompt})")
        return "\n".join(lines)

    def _describe(self, event: EngineEvent) -> str:
        if isinstance(event, SceneEntered):
            return f"- New scene: {event.intent}"
        if isinstance(event, BeatEntered):
            return f"- {event.intent}"
        if isinstance(event, CheckResolved):
            outcome = "SUCCESS" if event.success else "FAILURE"
            return f"- A risky attempt is resolved: {outcome} (this outcome is final)"
        if isinstance(event, ChoiceMade):
            return f"- The protagonist chose: {event.intent}"
        if isinstance(event, WentDeeper):
            return f"- Go deeper on the current moment. Allowed domain ONLY: {event.deeper_domain}"
        if isinstance(event, EndingReached):
            return f"- The story ends here: {event.intent} (give it a closing paragraph)"
        return f"- {event.type}"
