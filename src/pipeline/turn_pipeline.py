"""Turn pipeline orchestrator: coordinates all steps 6.1-6.9 for one turn."""

import logging
from collections.abc import Iterator
from typing import Any

from src.character_loader import CharacterLoader
from src.models.prompt_processor import PromptProcessor
from src.models.simulation import (
    ActionOutcome,
    CharacterProcessingResult,
    CharacterStateData,
    GMActionEvaluation,
    Observation,
    Ruleset,
    WorldState,
)
from src.pipeline.action_generator import ActionGenerator
from src.pipeline.character_processor import CharacterProcessor
from src.pipeline.continuation_generator import ContinuationGenerator
from src.pipeline.gm_evaluator import GMEvaluator
from src.pipeline.input_classifier import InputClassifier
from src.pipeline.intent_manager import IntentManager
from src.pipeline.narrator import Narrator
from src.pipeline.observation_extractor import ObservationExtractor
from src.services.dice_resolver import DiceResolver
from src.services.event_stream_service import EventStreamService
from src.services.ruleset_service import RulesetService
from src.services.session_state_service import SessionStateService

logger = logging.getLogger(__name__)


class TurnPipeline:
    """Orchestrates all pipeline steps for a single turn.

    Uses two processor tiers:
    - large_processor: GM evaluation, narration
    - mini_processor: all other steps (action gen, observation extraction, etc.)
    """

    def __init__(
        self,
        large_processor: PromptProcessor,
        mini_processor: PromptProcessor,
        session_state: SessionStateService,
        ruleset_service: RulesetService,
        event_stream: EventStreamService,
        character_loader: CharacterLoader,
        dice_resolver: DiceResolver | None = None,
    ) -> None:
        self.session_state = session_state
        self.ruleset_service = ruleset_service
        self.event_stream = event_stream
        self.char_loader = character_loader
        self.dice = dice_resolver or DiceResolver()

        # Pipeline steps — mini model
        self.input_classifier = InputClassifier(mini_processor)
        self.action_generator = ActionGenerator(mini_processor)
        self.observation_extractor = ObservationExtractor(mini_processor)
        self.character_processor = CharacterProcessor(mini_processor)
        self.intent_manager = IntentManager(mini_processor)
        self.continuation_generator = ContinuationGenerator(mini_processor)

        # Pipeline steps — large model
        self.gm_evaluator = GMEvaluator(large_processor)
        self.narrator = Narrator(large_processor)

    def execute_turn(
        self,
        session_id: str,
        user_input: str,
        input_type: str | None = None,
        ruleset: Ruleset | None = None,
        user_id: str = "anonymous",
    ) -> Iterator[dict[str, Any]]:
        """Execute a full turn, yielding SSE-compatible events.

        Yields dicts with 'type' and data fields:
        - {"type": "status", "step": "..."}
        - {"type": "narration_chunk", "text": "..."}
        - {"type": "narration_complete", "text": "..."}
        - {"type": "continuation_options", "options": [...]}
        - {"type": "turn_complete", "turn": int}
        - {"type": "error", "message": "..."}
        """
        try:
            yield from self._execute_turn_inner(
                session_id, user_input, input_type, ruleset, user_id
            )
        except Exception as e:
            logger.exception("Turn pipeline error")
            yield {"type": "error", "message": str(e)}

    def _execute_turn_inner(
        self,
        session_id: str,
        user_input: str,
        input_type: str | None,
        ruleset: Ruleset | None,
        user_id: str,
    ) -> Iterator[dict[str, Any]]:
        # --- Load state ---
        world_state = self.session_state.get_world_state(session_id, user_id)
        if not world_state:
            yield {"type": "error", "message": "Session not found"}
            return

        tick = self.session_state.get_turn_counter(session_id, user_id)
        present_ids = self.session_state.get_present_character_ids(session_id)
        all_states = self.session_state.get_all_character_states(session_id)
        narration_history = self.session_state.get_narration_history(session_id, user_id)

        # Save user message
        yield {"type": "status", "step": "processing_input"}

        # --- Step 6.1: Input Classification ---
        if input_type:
            classified_type = input_type
            action_text = user_input
        else:
            classification = self.input_classifier.execute(
                user_input=user_input,
                known_locations=self._get_known_locations(world_state),
                current_location=world_state.location,
                current_time=world_state.time,
            )
            classified_type = classification.type
            action_text = classification.action_text or user_input

        # TODO: handle relocation and time_skip types
        if classified_type != "action":
            yield {"type": "error", "message": f"Input type '{classified_type}' not yet supported"}
            return

        # --- Step 6.2: NPC Action Generation ---
        yield {"type": "status", "step": "generating_actions"}

        all_actions: list[dict[str, str]] = []

        # User action
        user_action = {
            "character": "You",
            "type": "action",
            "description": action_text,
        }
        all_actions.append(user_action)

        # Generate NPC actions
        for char_id in present_ids:
            char_state = all_states.get(char_id)
            if not char_state:
                continue

            char_info = self.char_loader.get_character_info(char_id, user_id)
            if not char_info:
                continue

            char_card = char_info.to_prompt_card()
            intent_goal = char_state.active_intent.goal if char_state.active_intent else ""
            assembled_memory = self.event_stream.assemble_memory(
                session_id, char_id, tick
            )

            result = self.action_generator.execute(
                character_name=char_info.name,
                character_card=char_card,
                intent_goal=intent_goal,
                drives_summary=self._format_drives(char_state),
                emotional_state_summary=self._format_emotional(char_state),
                assembled_memory=assembled_memory,
                location=world_state.location,
                time=world_state.time,
                characters_present=self._present_names(present_ids, all_states, user_id),
                user_action_description=action_text,
            )

            all_actions.append({
                "character": char_info.name,
                "type": result.action.type,
                "description": result.action.description,
                "target": result.action.target or "",
            })

        # --- Step 6.3: GM Evaluation ---
        yield {"type": "status", "step": "evaluating_actions"}

        skills_by_char = self._build_skills_map(present_ids, all_states, user_id)
        drive_schema_summary = self._format_drive_schema(ruleset) if ruleset else ""

        gm_result = self.gm_evaluator.execute(
            actions=all_actions,
            rules_text=ruleset.rules_text if ruleset else "",
            location=world_state.location,
            time=world_state.time,
            characters_present=self._present_names(present_ids, all_states, user_id),
            skills_by_character=skills_by_char,
            drive_schema_summary=drive_schema_summary,
        )

        # --- Step 6.4: Dice Resolution (programmatic) ---
        yield {"type": "status", "step": "resolving_checks"}

        outcomes = self._resolve_dice(gm_result.evaluations, all_states, present_ids, user_id)

        # Apply drive effects for successful actions
        if ruleset:
            for outcome in outcomes:
                if outcome.result == "success" and outcome.gm_evaluation:
                    eval_data = outcome.gm_evaluation
                    if eval_data.drive_effects:
                        char_id = self._name_to_id(outcome.character, present_ids, all_states, user_id)
                        if char_id and char_id in all_states:
                            effects = [{"drive": e.drive, "change": e.change} for e in eval_data.drive_effects]
                            self.ruleset_service.apply_drive_effects(
                                all_states[char_id], effects, ruleset
                            )

        # Apply drive decay for all present characters
        if ruleset:
            for char_id in present_ids:
                if char_id in all_states:
                    self.ruleset_service.apply_drive_decay(all_states[char_id], ruleset)

        # --- Step 6.5: Narration (streamed) ---
        yield {"type": "status", "step": "narrating"}

        outcome_dicts = [
            {
                "character": o.character,
                "action_summary": o.action_summary,
                "result": o.result,
                "roll_details": o.roll_details or "",
            }
            for o in outcomes
        ]

        narration_chunks: list[str] = []
        for chunk in self.narrator.execute_stream(
            outcomes=outcome_dicts,
            rules_text=ruleset.rules_text if ruleset else "",
            world_lore_brief=self._get_world_lore_brief(ruleset),
            location=world_state.location,
            time=world_state.time,
            characters_present=self._present_names(present_ids, all_states, user_id),
            narration_history=narration_history,
        ):
            narration_chunks.append(chunk)
            yield {"type": "narration_chunk", "text": chunk}

        full_narration = "".join(narration_chunks)
        yield {"type": "narration_complete", "text": full_narration}

        # --- Step 6.6: Observation Extraction ---
        yield {"type": "status", "step": "extracting_observations"}

        obs_result = self.observation_extractor.execute(
            narration=full_narration,
            outcomes=outcome_dicts,
            characters_present=self._present_names(present_ids, all_states, user_id),
        )

        # Distribute observations
        config = ruleset.config if ruleset else None
        if config and obs_result.observations:
            self.event_stream.distribute_observations(
                session_id=session_id,
                observations=obs_result.observations,
                present_character_ids=present_ids,
                tick=tick,
                config=config,
            )

        # --- Step 6.7: Character Processing ---
        yield {"type": "status", "step": "processing_characters"}

        for char_id in present_ids:
            char_state = all_states.get(char_id)
            if not char_state:
                continue

            char_info = self.char_loader.get_character_info(char_id, user_id)
            if not char_info:
                continue

            # Build observation context for this character
            this_turn_obs = self._format_observations_for_prompt(obs_result.observations)
            prior_unreflected = []  # TODO: query unreflected from event stream

            processing_result = self.character_processor.execute(
                character_name=char_info.name,
                character_card_brief=char_info.to_prompt_card(),
                reactive_stats_schema=self._format_reactive_schema(ruleset) if ruleset else "",
                character_reactive_stats=self._format_reactive_stats(char_state),
                this_turn_observations=this_turn_obs,
                prior_unreflected_observations=prior_unreflected,
                active_intent_goal=char_state.active_intent.goal if char_state.active_intent else "",
            )

            # Apply state diffs
            if ruleset and processing_result.state_diffs:
                diffs = [d.model_dump() for d in processing_result.state_diffs]
                self.ruleset_service.apply_state_diffs(char_state, diffs, ruleset)

            # Store reflection
            if processing_result.reflection and config:
                self.event_stream.add_reflection(
                    session_id=session_id,
                    character_id=char_id,
                    tick=tick,
                    reflection=processing_result.reflection,
                    config=config,
                )

            # --- Step 6.8: Intent Lifecycle ---
            self._process_intent(
                char_id=char_id,
                char_info_name=char_info.name,
                char_card=char_info.to_prompt_card(),
                char_state=char_state,
                processing_result=processing_result,
                session_id=session_id,
                world_state=world_state,
                present_ids=present_ids,
                all_states=all_states,
                tick=tick,
                user_id=user_id,
            )

            # Handle departures
            for outcome in outcomes:
                if outcome.character == char_info.name and outcome.result == "success":
                    if outcome.gm_evaluation and outcome.gm_evaluation.departure:
                        char_state.is_present = False
                        self.session_state.mark_departure(
                            session_id, char_id,
                            destination=outcome.gm_evaluation.action_summary,
                            tick=tick,
                        )

            # Clamp and save state
            if ruleset:
                self.ruleset_service.clamp_all(char_state, ruleset)
            self.session_state.save_character_state(session_id, char_id, char_state)

        # --- Step 6.9: Continuation Options ---
        yield {"type": "status", "step": "generating_options"}

        # Get user persona info for continuation
        persona_brief = ""
        persona_drives = ""
        persona_emotional = ""
        # Find persona from scenario (not an NPC)
        for cid in list(all_states.keys()):
            state = all_states.get(cid)
            if state and cid not in present_ids:
                persona_info = self.char_loader.get_character_info(cid, user_id)
                if persona_info:
                    persona_brief = persona_info.to_prompt_card()
                    persona_drives = self._format_drives(state)
                    persona_emotional = self._format_emotional(state)
                    break

        cont_result = self.continuation_generator.execute(
            location=world_state.location,
            time=world_state.time,
            characters_present=self._present_names(present_ids, all_states, user_id),
            narration_summary=full_narration[-500:] if len(full_narration) > 500 else full_narration,
            user_character_brief=persona_brief,
            user_drives_summary=persona_drives,
            user_emotional_state_summary=persona_emotional,
            known_locations=self._get_known_locations(world_state),
        )

        yield {
            "type": "continuation_options",
            "options": [o.model_dump() for o in cont_result.options],
        }

        # --- Finalize turn ---
        new_tick = self.session_state.increment_turn(session_id)
        self.session_state.append_narration(
            session_id, full_narration,
            max_history=ruleset.config.narration_history_size if ruleset else 5,
        )
        self.session_state.save_snapshot(session_id, user_id)

        # Prune event streams
        if config:
            for char_id in present_ids:
                self.event_stream.prune(
                    session_id, char_id, new_tick,
                    max_events=config.max_event_stream_length,
                )

        yield {"type": "turn_complete", "turn": new_tick}

    # --- Intent lifecycle helper ---

    def _process_intent(
        self,
        char_id: str,
        char_info_name: str,
        char_card: str,
        char_state: CharacterStateData,
        processing_result: CharacterProcessingResult,
        session_id: str,
        world_state: WorldState,
        present_ids: list[str],
        all_states: dict[str, CharacterStateData],
        tick: int,
        user_id: str,
    ) -> None:
        """Step 6.8: Handle intent reevaluation, completion, and generation."""
        intent = char_state.active_intent

        # 6.8a: Reevaluate if we have a reflection that overlaps with intent
        if intent and processing_result.reflection:
            reeval = self.intent_manager.reevaluate(
                character_name=char_info_name,
                character_card_brief=char_card,
                active_intent_goal=intent.goal,
                active_intent_success_condition=str(intent.success_condition.model_dump()),
                reflection_content=processing_result.reflection.content,
                drives_summary=self._format_drives(char_state),
                emotional_state_summary=self._format_emotional(char_state),
            )
            if not reeval.keep:
                char_state.active_intent = None
                intent = None

        # 6.8c: Check completion for narrative intents
        if intent and intent.success_condition.type == "narrative":
            recent_events = self.event_stream.assemble_memory(
                session_id, char_id, tick, limit=10
            )
            completion = self.intent_manager.check_completion(
                active_intent_goal=intent.goal,
                success_condition_description=intent.success_condition.description or "",
                recent_events=recent_events,
            )
            if completion.complete:
                char_state.active_intent = None
                intent = None

        # 6.8c: Check drive threshold intents programmatically
        if intent and intent.success_condition.type == "drive_threshold":
            sc = intent.success_condition
            if sc.drive and sc.operator and sc.threshold is not None:
                current_val = char_state.drives.get(sc.drive, 0)
                met = False
                if sc.operator == ">" and current_val > sc.threshold:
                    met = True
                elif sc.operator == ">=" and current_val >= sc.threshold:
                    met = True
                elif sc.operator == "<" and current_val < sc.threshold:
                    met = True
                elif sc.operator == "<=" and current_val <= sc.threshold:
                    met = True
                if met:
                    char_state.active_intent = None
                    intent = None

        # 6.8b: Generate new intent if needed
        if not intent:
            assembled_memory = self.event_stream.assemble_memory(
                session_id, char_id, tick
            )
            new_intent = self.intent_manager.generate(
                character_name=char_info_name,
                character_card=char_card,
                drives_summary=self._format_drives(char_state),
                emotional_state_summary=self._format_emotional(char_state),
                assembled_memory=assembled_memory,
                location=world_state.location,
                time=world_state.time,
                characters_present=self._present_names(present_ids, all_states, user_id),
            )
            char_state.active_intent = new_intent

    # --- Dice resolution ---

    def _resolve_dice(
        self,
        evaluations: list[GMActionEvaluation],
        all_states: dict[str, CharacterStateData],
        present_ids: list[str],
        user_id: str,
    ) -> list[ActionOutcome]:
        """Step 6.4: Resolve dice for all evaluated actions."""
        outcomes: list[ActionOutcome] = []
        contested_pairs: set[str] = set()

        for evaluation in evaluations:
            if not evaluation.check_required:
                outcomes.append(ActionOutcome(
                    character=evaluation.character,
                    action_summary=evaluation.action_summary,
                    result="success",
                    gm_evaluation=evaluation,
                ))
                continue

            # Contested check
            if evaluation.contested_with and evaluation.contested_with not in contested_pairs:
                contested_pairs.add(evaluation.character)
                contested_pairs.add(evaluation.contested_with)

                char_id = self._name_to_id(evaluation.character, present_ids, all_states, user_id)
                opp_id = self._name_to_id(evaluation.contested_with, present_ids, all_states, user_id)

                skill_val = 0.0
                opp_skill_val = 0.0
                opp_skill = ""

                if char_id and char_id in all_states and evaluation.skill:
                    skill_val = all_states[char_id].skills.get(evaluation.skill, 0)

                # Find opponent evaluation
                opp_eval = next(
                    (e for e in evaluations if e.character == evaluation.contested_with),
                    None,
                )
                if opp_eval and opp_eval.skill and opp_id and opp_id in all_states:
                    opp_skill = opp_eval.skill
                    opp_skill_val = all_states[opp_id].skills.get(opp_skill, 0)

                dice_result = self.dice.resolve_contested(
                    character=evaluation.character,
                    skill=evaluation.skill or "",
                    skill_value=skill_val,
                    opponent=evaluation.contested_with,
                    opponent_skill=opp_skill,
                    opponent_skill_value=opp_skill_val,
                )

                outcomes.append(ActionOutcome(
                    character=evaluation.character,
                    action_summary=evaluation.action_summary,
                    result="success" if dice_result.success else "failure",
                    roll_details=dice_result.detail,
                    gm_evaluation=evaluation,
                ))

                # Opponent gets the inverse result
                if opp_eval:
                    outcomes.append(ActionOutcome(
                        character=opp_eval.character,
                        action_summary=opp_eval.action_summary,
                        result="failure" if dice_result.success else "success",
                        roll_details=dice_result.detail,
                        gm_evaluation=opp_eval,
                    ))
                continue

            # Already handled as part of contested pair
            if evaluation.character in contested_pairs:
                continue

            # Standard check
            char_id = self._name_to_id(evaluation.character, present_ids, all_states, user_id)
            skill_val = 0.0
            if char_id and char_id in all_states and evaluation.skill:
                skill_val = all_states[char_id].skills.get(evaluation.skill, 0)

            dice_result = self.dice.resolve_check(
                character=evaluation.character,
                skill=evaluation.skill or "",
                skill_value=skill_val,
                dc=evaluation.dc or 10,
            )

            outcomes.append(ActionOutcome(
                character=evaluation.character,
                action_summary=evaluation.action_summary,
                result="success" if dice_result.success else "failure",
                roll_details=dice_result.detail,
                gm_evaluation=evaluation,
            ))

        return outcomes

    # --- Formatting helpers ---

    def _format_drives(self, state: CharacterStateData) -> str:
        if not state.drives:
            return "No drives"
        return ", ".join(f"{k}: {v:.0f}" for k, v in state.drives.items())

    def _format_emotional(self, state: CharacterStateData) -> str:
        parts = []
        if state.emotional_state.global_state:
            parts.append(
                ", ".join(f"{k}: {v:.0f}" for k, v in state.emotional_state.global_state.items())
            )
        if state.emotional_state.per_relationship:
            for target, dims in state.emotional_state.per_relationship.items():
                dim_str = ", ".join(f"{k}: {v:.0f}" for k, v in dims.items())
                parts.append(f"toward {target}: {dim_str}")
        return "; ".join(parts) if parts else "Neutral"

    def _format_reactive_stats(self, state: CharacterStateData) -> str:
        lines = []
        if state.emotional_state.global_state:
            for k, v in state.emotional_state.global_state.items():
                lines.append(f"{k}: {v:.0f}")
        if state.emotional_state.per_relationship:
            for target, dims in state.emotional_state.per_relationship.items():
                for k, v in dims.items():
                    lines.append(f"{k} (toward {target}): {v:.0f}")
        return "\n".join(lines) if lines else "No reactive stats"

    def _format_reactive_schema(self, ruleset: Ruleset) -> str:
        lines = []
        for dim in ruleset.state_schemas.emotional_state.global_dims:
            lines.append(f"- {dim.name} (global): range {dim.range_min}-{dim.range_max}")
        for dim in ruleset.state_schemas.emotional_state.per_relationship:
            lines.append(f"- {dim.name} (per-relationship): range {dim.range_min}-{dim.range_max}")
        return "\n".join(lines) if lines else "No reactive stats defined"

    def _format_drive_schema(self, ruleset: Ruleset) -> str:
        lines = []
        for d in ruleset.state_schemas.drives:
            lines.append(f"{d.name}: range {d.range_min}-{d.range_max}")
        return "\n".join(lines) if lines else "No drives defined"

    def _format_observations_for_prompt(
        self, observations: list[Observation]
    ) -> list[dict[str, str]]:
        return [
            {"id": f"obs-this-turn-{i}", "content": o.content}
            for i, o in enumerate(observations)
        ]

    def _present_names(
        self,
        present_ids: list[str],
        all_states: dict[str, CharacterStateData],
        user_id: str,
    ) -> list[str]:
        names = []
        for cid in present_ids:
            char_info = self.char_loader.get_character_info(cid, user_id)
            if char_info:
                names.append(char_info.name)
            else:
                names.append(cid)
        return names

    def _name_to_id(
        self,
        name: str,
        present_ids: list[str],
        all_states: dict[str, CharacterStateData],
        user_id: str,
    ) -> str | None:
        for cid in list(all_states.keys()):
            char_info = self.char_loader.get_character_info(cid, user_id)
            if char_info and char_info.name == name:
                return cid
        return None

    def _build_skills_map(
        self,
        present_ids: list[str],
        all_states: dict[str, CharacterStateData],
        user_id: str,
    ) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for cid in present_ids:
            state = all_states.get(cid)
            char_info = self.char_loader.get_character_info(cid, user_id)
            if state and char_info:
                result[char_info.name] = dict(state.skills)
        return result

    def _get_known_locations(self, world_state: WorldState) -> list[str]:
        # TODO: populate from world lore / location history
        return [world_state.location] if world_state.location else []

    def _get_world_lore_brief(self, ruleset: Ruleset | None) -> str:
        # TODO: load relevant lore from WorldLoreRegistry
        return ruleset.rules_text if ruleset else ""
