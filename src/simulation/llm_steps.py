from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

from src.models.character import Character
from src.models.prompt_processor import PromptProcessor
from src.simulation.contracts import (
    CharacterActionOutput,
    CharacterRuntime,
    GmResolutionOutput,
    NarratorOutput,
    SuggestedActionsOutput,
)

T = TypeVar("T")


@dataclass
class LlmStepRunner:
    prompt_version: str = "sim-v2"

    def run_character_action(
        self,
        processor: PromptProcessor,
        character: Character,
        runtime: CharacterRuntime,
        scene_state: dict[str, Any],
        user_action: str,
        decayed_observations: list[dict[str, Any]],
    ) -> CharacterActionOutput:
        prompt = (
            "You are simulating one in-scene character in a fictional story.\n"
            "Generate exactly one immediate move for this character.\n"
            "Use this JSON shape only: {\"action_type\": \"action|reaction\", \"target\": \"...\", \"description\": \"...\", \"intent_tags\": [\"...\"]}\n"
            "Rules:\n"
            "- Move must be physically or verbally concrete and scene-advancing.\n"
            "- target must name a specific character/object/location from the scene context.\n"
            "- description is one sentence, max 20 words.\n"
            "- Use reaction when responding to the latest move; otherwise use action.\n"
            "- Avoid placeholders like someone/something, and avoid passive waiting.\n"
            "Output JSON only.\n"
        )
        user_prompt = (
            f"Character card:\n{character.to_prompt_card(role='Character')}\n\n"
            f"Character runtime stats:\n{runtime.stat_block}\n\n"
            f"Scene state:\n{scene_state}\n\n"
            f"Latest user move:\n{user_action}\n\n"
            f"Recent observations:\n{decayed_observations}\n\n"
            f"Character id:\n{runtime.character_id}\n"
        )
        return self._run_with_retry(processor, prompt, user_prompt, CharacterActionOutput, step_name="character_action")

    def run_gm_resolution(
        self,
        processor: PromptProcessor,
        rulebook_text: str,
        scene_state: dict[str, Any],
        scene_moves: list[dict[str, Any]],
        character_stat_blocks: dict[str, dict[str, Any]],
        recent_observations: dict[str, list[dict[str, Any]]],
    ) -> GmResolutionOutput:
        prompt = (
            "You are the game master for a turn-based fictional simulation.\n"
            "Evaluate each scene move and decide if it needs a skill check.\n"
            "For every move, return one adjudication object.\n"
            "Use this JSON shape only: {\"adjudications\": [{\"move_id\": \"...\", \"actor_id\": \"...\", \"requires_skill_check\": true|false, \"skill\": \"...\", \"difficulty_class\": 5-30, \"auto_outcome\": \"success|failure|null\", \"reasoning\": \"...\"}]}\n"
            "Rules:\n"
            "- If requires_skill_check=true, provide skill and difficulty_class.\n"
            "- If requires_skill_check=false, set auto_outcome explicitly to success or failure.\n"
            "- skill must match one of actor stat keys when possible.\n"
            "- Keep difficulty grounded in current scene pressure, relations, and opposition.\n"
            "- Do not skip any move id.\n"
            "Output JSON only.\n"
        )
        user_prompt = (
            f"Rulebook:\n{rulebook_text}\n\n"
            f"Scene state:\n{scene_state}\n\n"
            f"Moves to adjudicate:\n{scene_moves}\n\n"
            f"Character stat blocks:\n{character_stat_blocks}\n\n"
            f"Recent observations:\n{recent_observations}\n"
        )
        return self._run_with_retry(processor, prompt, user_prompt, GmResolutionOutput, step_name="gm_resolution")

    def run_narrator(
        self,
        processor: PromptProcessor,
        scene_state: dict[str, Any],
        scene_moves: list[dict[str, Any]],
        move_outcomes: list[dict[str, Any]],
        rulebook_summary: str,
        scenario_tone: str,
        recent_events: str,
    ) -> NarratorOutput:
        prompt = (
            f"""You specialize in creative writing and help to narrate a simulated fictional scenario involving various characters. Considering the current scene state and actions of the characters present in the story, generate the next piece of the story, describing how various action outcomes affected the scene and characters - write as you would write a quality fiction book, in clear, engaging prose.

Think carefully before responding, and follow the detailed guidelines below to ensure consistency, character authenticity, and narrative quality.

## Character Authenticity

- Treat character information as foundation, not a checklist. A carpenter doesn't mentally recite "I am a carpenter" in every scene—they simply exist and act naturally.
- Avoid over-indexing, over-analyzing on stated traits. Real people are contradictory and situational. Someone "confident" can still doubt themselves; someone "introverted" can still be chatty with the right person in the right moment.
- Let unstated aspects emerge organically. Characters can have interests, reactions, or quirks not explicitly listed. They're people, not data points.
- Don't constantly validate actions against the character sheet. "Would a real person in this emotional state do this?" matters more than "Does this match trait #3?"
- Characters should feel lived-in, not performed. They have bad days, intrusive thoughts, and moments that don't perfectly align with their personality summary.
- Develop interests, habits, and reactions beyond what's explicitly stated—as long as they fit the character's context and background.

## Writing Style

- Write in a way that's sharp and impactful; keep it concise. Skip the flowery, exaggerated language.
- Take inspiration from high-quality modern authors known for clear, engaging prose - think Ernest Hemingway, Virginia Woolf, Hunter S. Thompson.
- Follow "show, don't tell" approach: bring scenes to life with clear, observable details—like body language, facial expressions, gestures, and the way someone speaks.
- Do not over-explain character's emotions or reactions, responses; let the user infer them from the context, actions, and dialogue.
- Do not use vague descriptors or euphemisms; be specific and concrete in displaying physical actions and emotions - create vivid, true-to-life imagery, state things as they are.
- If you are not confident user has stated something - never refer to it as a fact.

Content Guidelines:
{processor.get_processor_specific_prompt()}

## Response Guidelines

Aim for 3-6 sentences for general responses.
Write more text only in the following cases:
- if there was a significant time skip or change in setting - describe what happened in between for all relevant characters.
- if character is describing something in details or has an internal monologue, important to be displayed in the story.
Response formatting may have the following elements:
- Physical actions (in asterisks, in third person)
- Spoken dialogue (in quotes)
- Internal sensations or observations (in third person)
- Environmental details (if relevant, in third person)

## Main Characters

Character Description Guidance:
- [Backstory] Provides context for who the character is and why. Informs their worldview, skills, and relationships, but doesn't need to be constantly referenced. It's the foundation they stand on, not a biography they recite.
- [Personality] Shows typical patterns and tendencies, not immutable laws. These traits influence behavior but don't determine every action. Contradictions and context matter—someone "assertive" might be tentative when vulnerable.
- [Desires/Goals] What the character wants in the scene or in their life. These drive autonomous action and create natural conflict or alignment with other characters. Pursue these actively, don't wait for permission.
- [Appearance] Physical, grounding details for the scene. Use when relevant (someone notices their appearance, physical actions occur) but don't force it into every response. Bodies exist in space—show how they move and react.
- [Kinks/Dislikes] In intimate scenes, these guide what the character finds appealing or engages with, but they're not a mandatory checklist. Real attraction is messy and contextual. Someone can enjoy something not listed or avoid something they usually like.
- [Relationships] Defines the current dynamic and history between characters. Informs tone, boundaries, and emotional responses. This evolves through the scene—don't treat it as static.
"""
        )
        user_prompt = (
            f"Scene state:\n{scene_state}\n\n"
            f"Scene moves:\n{scene_moves}\n\n"
            f"Action outcomes:\n{move_outcomes}\n\n"
            f"Rulebook summary:\n{rulebook_summary}\n\n"
            f"Scenario tone:\n{scenario_tone}\n\n"
            f"Recent events:\n{recent_events}\n\n"
            "Return JSON: {\n"
            '  "narration_text": "...",\n'
            '  "new_observations": [{"character_id": "...", "content": "...", "importance": 1}],\n'
            '  "state_ops": [{"op": "set", "path": "...", "value": "..."}]\n'
            "}\n"
        )
        return self._run_with_retry(processor, prompt, user_prompt, NarratorOutput, step_name="narrator")

    def run_action_suggestions(
        self,
        processor: PromptProcessor,
        persona: Character,
        scene_state: dict[str, Any],
        narration_text: str,
        move_outcomes: list[dict[str, Any]],
    ) -> SuggestedActionsOutput:
        prompt = (
            "You are a turn-based story assistant.\n"
            "Generate exactly 3 next actions for the player.\n"
            "Each action must be specific, actionable, and in first person.\n"
            "Quality rules:\n"
            "- Every option must change the scene now (no waiting or observation-only moves).\n"
            "- Include a concrete target from current scene context: named character, relation pair, object, or location.\n"
            "- Reference current scene relations, pressure, or immediately previous moves.\n"
            "- Use a clear verb and a clear object (what is done, to whom/about what).\n"
            "- Avoid vague wording: closest character, someone, something, test the tension, make a move.\n"
            "- Avoid generally-applicable templates; each option should be valid for this scene only.\n"
            "- Prefer exact names/ids present in scene context when referring to people.\n"
            "- Keep each option to one sentence, max 18 words.\n"
            "Output JSON only.\n"
        )
        user_prompt = (
            f"User is playing as persona:\n{persona.to_prompt_card()}\n"
            f"Scene state:\n{scene_state}\n\n"
            f"What happened recently:\n{narration_text}\n\n"
            f"Action outcomes:\n{move_outcomes}\n\n"
            "Return JSON: {\"suggested_actions\": [\"...\", \"...\", \"...\"]}\n"
        )
        return self._run_with_retry(processor, prompt, user_prompt, SuggestedActionsOutput, step_name="action_suggestions")

    def _run_with_retry(
        self,
        processor: PromptProcessor,
        prompt: str,
        user_prompt: str,
        output_type: type[T],
        *,
        step_name: str,
    ) -> T:
        errors: list[str] = []
        for _ in range(2):
            try:
                return processor.respond_with_model(
                    prompt=prompt,
                    user_prompt=user_prompt,
                    output_type=output_type,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        raise ValueError(f"Model output validation failed at step '{step_name}' after retry: {' | '.join(errors)}")
