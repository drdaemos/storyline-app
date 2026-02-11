from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.memory.db_models import SimulationSession
from src.character_loader import CharacterLoader
from src.models.character import Character
from src.simulation.contracts import (
    CharacterRuntime,
    MoveAdjudication,
    MoveOutcome,
    RuntimeObservation,
    SceneMove,
    StartSimulationSessionInput,
    StateOp,
    TurnResult,
)
from src.simulation.dice import roll_dice
from src.simulation.llm_steps import LlmStepRunner
from src.simulation.model_router import ModelRouter
from src.simulation.repository import SimulationRepository
from src.simulation.schema_validation import validate_schema
from src.simulation.state_ops import apply_state_ops


@dataclass
class SimulationService:
    repository: SimulationRepository
    model_router: ModelRouter
    character_loader: CharacterLoader
    llm_runner: LlmStepRunner = field(default_factory=LlmStepRunner)

    @classmethod
    def create_default(cls) -> SimulationService:
        return cls(
            repository=SimulationRepository(),
            model_router=ModelRouter(),
            character_loader=CharacterLoader(),
        )

    def start_session(
        self,
        *,
        session_id: str,
        user_id: str,
        scenario_id: str | None = None,
        npc_character_id: str | None = None,
        npc_character_ids: list[str] | None = None,
        persona_character_id: str,
        intro_seed: str,
        ruleset_id: str = "everyday-tension",
        world_lore_id: str = "default-world",
        scene_seed_overrides: dict[str, Any] | None = None,
        small_model_key: str = "deepseek-v32",
        large_model_key: str = "claude-sonnet",
    ) -> str:
        ruleset = self.repository.get_ruleset(ruleset_id)
        effective_npc_ids = npc_character_ids or []
        if npc_character_id:
            effective_npc_ids.append(npc_character_id)
        effective_npc_ids = [cid for cid in dict.fromkeys(effective_npc_ids) if cid]
        if not effective_npc_ids:
            raise ValueError("At least one NPC character is required")

        all_character_ids = [*effective_npc_ids, persona_character_id]
        loaded_characters = {
            character_id: self._load_character(character_id, user_id)
            for character_id in all_character_ids
        }
        stat_blocks = {
            character_id: self._derive_stat_block(ruleset.character_stat_schema, ruleset.id, loaded_characters[character_id])
            for character_id in all_character_ids
        }

        scene_seed = {
            "location": "scene start",
            "pressure_clock": 0,
            "present": [*effective_npc_ids, persona_character_id],
            "relations": [
                {"a": npc_id, "b": persona_character_id, "trust": 0, "tension": 0, "closeness": 0}
                for npc_id in effective_npc_ids
            ],
            "time_minutes": 0,
        }
        if scene_seed_overrides and isinstance(scene_seed_overrides, dict):
            scene_seed.update(scene_seed_overrides)
        present = scene_seed.get("present")
        if isinstance(present, list):
            scene_seed["present"] = [*dict.fromkeys([*present, *all_character_ids])]
        else:
            scene_seed["present"] = [*all_character_ids]
        validate_schema(scene_seed, ruleset.scene_state_schema)

        request = StartSimulationSessionInput(
            session_id=session_id,
            scenario_id=scenario_id,
            ruleset_id=ruleset_id,
            world_lore_id=world_lore_id,
            character_ids=[*effective_npc_ids, persona_character_id],
            npc_ids=effective_npc_ids,
            stat_blocks=stat_blocks,
            scene_seed=scene_seed,
            intro_seed=intro_seed,
            user_id=user_id,
            small_model_key=small_model_key,
            large_model_key=large_model_key,
        )
        self.repository.create_session(request)
        return session_id

    def run_turn(self, *, session_id: str, user_id: str, user_action: str, user_action_id: str) -> TurnResult:
        if not user_action.strip():
            raise ValueError("user_action cannot be empty")
        if not user_action_id.strip():
            raise ValueError("user_action_id cannot be empty")

        with self.repository.transaction() as db:
            runtime_session = self.repository.get_session_in_tx(db, session_id, user_id)
            if self.repository.session_has_user_action_id(db, session_id, user_action_id):
                existing = self.repository.get_narration_for_action_id(db, session_id, user_action_id)
                if existing is None:
                    raise ValueError("Idempotent turn found without narrator event")
                existing_suggestions = self.repository.get_suggestions_for_action_id(db, session_id, user_action_id)
                existing_meta_text = self.repository.get_meta_text_for_action_id(db, session_id, user_action_id)
                return TurnResult(
                    narration_text=existing,
                    session_id=session_id,
                    turn_index=runtime_session.current_turn_index,
                    scene_id=runtime_session.current_scene_id,
                    suggested_actions=existing_suggestions,
                    meta_text=existing_meta_text,
                )

            ruleset = self.repository.get_ruleset(runtime_session.ruleset_id)
            world_lore = self.repository.get_world_lore(runtime_session.world_lore_id)
            scene = self.repository.get_scene_in_tx(db, runtime_session.current_scene_id)
            char_rows = self.repository.list_session_characters_in_tx(db, session_id)
            runtimes = [CharacterRuntime(character_id=row["character_id"], role=row["role"], stat_block=row["stat_block"]) for row in char_rows]
            npc_runtimes = [row for row in runtimes if row.role == "npc"]
            persona_runtime = next((row for row in runtimes if row.role == "user_persona"), None)
            if persona_runtime is None:
                raise ValueError("Session has no user persona runtime")
            persona = self._load_character(persona_runtime.character_id, user_id)

            recent_obs = {row.character_id: self._decayed(self.repository.list_recent_observations_in_tx(db, session_id, row.character_id)) for row in runtimes}
            stat_blocks = {row.character_id: row.stat_block for row in runtimes}

            small_processor = self.model_router.get_processor(runtime_session.small_model_key)
            large_processor = self.model_router.get_processor(runtime_session.large_model_key)

            model_events: list[dict[str, Any]] = []
            scene_moves: list[SceneMove] = [
                self._build_user_scene_move(
                    user_action=user_action,
                    actor_id=persona_runtime.character_id,
                    scene_state=scene.state_json,
                )
            ]

            for idx, runtime in enumerate(npc_runtimes, start=1):
                character = self._load_character(runtime.character_id, user_id)
                character_action = self.llm_runner.run_character_action(
                    processor=small_processor,
                    character=character,
                    runtime=runtime,
                    scene_state=scene.state_json,
                    user_action=user_action,
                    decayed_observations=recent_obs.get(runtime.character_id, []),
                )
                move = SceneMove(
                    move_id=f"move-{idx}-{runtime.character_id}",
                    actor_id=runtime.character_id,
                    action_type=self._normalize_action_type(character_action.action_type),
                    target=self._normalize_move_target(character_action.target),
                    description=self._normalize_move_description(character_action.description),
                    source="character",
                )
                scene_moves.append(move)
                model_events.append(
                    {
                        "event_type": "model_output",
                        "step_name": "character_action",
                        "payload_json": {
                            "move": move.model_dump(),
                            "intent_tags": list(character_action.intent_tags),
                        },
                        "model_key": runtime_session.small_model_key,
                    }
                )

            gm_resolution = self.llm_runner.run_gm_resolution(
                processor=large_processor,
                rulebook_text=ruleset.rulebook_text,
                scene_state=scene.state_json,
                scene_moves=[move.model_dump() for move in scene_moves],
                character_stat_blocks=stat_blocks,
                recent_observations=recent_obs,
            )
            model_events.append(
                {
                    "event_type": "model_output",
                    "step_name": "gm_resolution",
                    "payload_json": gm_resolution.model_dump(),
                    "model_key": runtime_session.large_model_key,
                }
            )

            move_outcomes, dice_results = self._resolve_move_outcomes(
                scene_moves=scene_moves,
                adjudications=gm_resolution.adjudications,
                stat_blocks=stat_blocks,
                session_id=session_id,
                turn_index=runtime_session.current_turn_index + 1,
                user_action_id=user_action_id,
            )
            model_events.append(
                {
                    "event_type": "tool_call",
                    "step_name": "roll_resolution",
                    "payload_json": {
                        "dice_results": dice_results,
                        "move_outcomes": [outcome.model_dump() for outcome in move_outcomes],
                    },
                    "model_key": None,
                }
            )

            rulebook_summary = f"{ruleset.name}: {ruleset.rulebook_text[:300]}"
            narrator = self.llm_runner.run_narrator(
                processor=large_processor,
                scene_state=scene.state_json,
                scene_moves=[move.model_dump() for move in scene_moves],
                move_outcomes=[outcome.model_dump() for outcome in move_outcomes],
                rulebook_summary=rulebook_summary,
                scenario_tone=str(scene.state_json.get("tone", "")),
                recent_events=world_lore.lore_text[:300],
            )
            model_events.append(
                {
                    "event_type": "model_output",
                    "step_name": "narrator",
                    "payload_json": narrator.model_dump(),
                    "model_key": runtime_session.large_model_key,
                }
            )

            try:
                suggestions_output = self.llm_runner.run_action_suggestions(
                    processor=small_processor,
                    persona=persona,
                    scene_state=scene.state_json,
                    narration_text=narrator.narration_text,
                    move_outcomes=[outcome.model_dump() for outcome in move_outcomes],
                )
                suggested_actions = self._normalize_suggestions(suggestions_output.suggested_actions)
            except Exception:
                suggested_actions = self._fallback_suggestions()

            model_events.append(
                {
                    "event_type": "model_output",
                    "step_name": "action_suggestions",
                    "payload_json": {"suggested_actions": suggested_actions},
                    "model_key": runtime_session.small_model_key,
                }
            )

            normalized_ops = [self._normalize_state_op(op) for op in narrator.state_ops]
            next_state = apply_state_ops(scene.state_json, normalized_ops)
            validate_schema(next_state, ruleset.scene_state_schema)
            meta_text = self._build_meta_text(dice_results=dice_results, state_ops=normalized_ops, move_outcomes=move_outcomes)
            model_events.append(
                {
                    "event_type": "state_apply",
                    "step_name": "engine_apply",
                    "payload_json": {"state_ops": [op.model_dump() for op in normalized_ops], "next_state": next_state},
                    "model_key": None,
                }
            )

            serialized_observations = [obs.model_dump() for obs in narrator.new_observations]
            relations = next_state.get("relations", []) if isinstance(next_state.get("relations", []), list) else []
            new_scene_id, turn_index = self.repository.write_turn_outputs(
                db=db,
                session_id=session_id,
                expected_current_scene_id=scene.id,
                expected_turn_index=runtime_session.current_turn_index,
                narration_text=narrator.narration_text,
                narration_meta_text=meta_text,
                state_json=next_state,
                user_action_id=user_action_id,
                model_events=model_events,
                actions=self._build_persisted_actions(scene_moves=scene_moves, move_outcomes=move_outcomes, user_action=user_action),
                observations=serialized_observations,
                relations=relations,
            )

            return TurnResult(
                narration_text=narrator.narration_text,
                session_id=session_id,
                turn_index=turn_index,
                scene_id=new_scene_id,
                suggested_actions=suggested_actions,
                meta_text=meta_text,
            )

    def configure_session_models(self, *, session_id: str, user_id: str, small_model_key: str, large_model_key: str) -> bool:
        with self.repository.transaction() as db:
            row = db.get(SimulationSession, session_id)
            if row is None or row.user_id != user_id:
                return False
            row.small_model_key = small_model_key
            row.large_model_key = large_model_key
            return True

    def _load_character(self, character_id: str, user_id: str) -> Character:
        character = self.character_loader.load_character(character_id, user_id)
        if character is None:
            raise ValueError(f"Character '{character_id}' not found")
        return character

    def _default_stat_block(self, schema: dict[str, Any]) -> dict[str, Any]:
        props = schema.get("properties", {})
        result: dict[str, Any] = {}
        for key, prop in props.items():
            prop_type = prop.get("type")
            if prop_type == "integer":
                minimum = prop.get("minimum", prop.get("min", 0))
                maximum = prop.get("maximum", prop.get("max", 10))
                result[key] = int((minimum + maximum) / 2)
            elif prop_type == "number":
                minimum = prop.get("minimum", prop.get("min", 0))
                maximum = prop.get("maximum", prop.get("max", 1))
                result[key] = float((minimum + maximum) / 2)
            elif prop_type == "string":
                result[key] = ""
            elif prop_type == "array":
                result[key] = []
        return result

    def _derive_stat_block(self, schema: dict[str, Any], ruleset_id: str, character: Character) -> dict[str, Any]:
        stat_block = self._default_stat_block(schema)
        if character.ruleset_id != ruleset_id:
            return stat_block
        if not isinstance(character.ruleset_stats, dict):
            return stat_block

        props = schema.get("properties", {})
        for key, prop in props.items():
            if key not in character.ruleset_stats:
                continue
            value = character.ruleset_stats[key]
            prop_type = prop.get("type")
            if prop_type == "integer":
                if not isinstance(value, (int, float)):
                    continue
                minimum = prop.get("minimum", prop.get("min"))
                maximum = prop.get("maximum", prop.get("max"))
                num = int(value)
                if isinstance(minimum, int):
                    num = max(minimum, num)
                if isinstance(maximum, int):
                    num = min(maximum, num)
                stat_block[key] = num
            elif prop_type == "number":
                if not isinstance(value, (int, float)):
                    continue
                minimum = prop.get("minimum", prop.get("min"))
                maximum = prop.get("maximum", prop.get("max"))
                num_f = float(value)
                if isinstance(minimum, (int, float)):
                    num_f = max(float(minimum), num_f)
                if isinstance(maximum, (int, float)):
                    num_f = min(float(maximum), num_f)
                stat_block[key] = num_f
            elif prop_type == "string":
                if isinstance(value, str):
                    stat_block[key] = value
            elif prop_type == "boolean":
                if isinstance(value, bool):
                    stat_block[key] = value
            elif prop_type == "array":
                if isinstance(value, list):
                    stat_block[key] = value
            elif prop_type == "object":
                if isinstance(value, dict):
                    stat_block[key] = value
        return stat_block

    def _decayed(self, observations: list[RuntimeObservation]) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        lambda_value = 0.015
        result = []
        for obs in observations:
            age_minutes = max(0.0, (now - obs.created_at.replace(tzinfo=UTC)).total_seconds() / 60.0)
            decay_weight = 2.718281828 ** (-lambda_value * age_minutes)
            reinforcement_multiplier = 1.0 + min(obs.reinforcement_count, 3) * 0.15
            priority = obs.importance * decay_weight * reinforcement_multiplier
            result.append(
                {
                    "character_id": obs.character_id,
                    "content": obs.content,
                    "importance": obs.importance,
                    "created_at": obs.created_at.isoformat(),
                    "priority": round(priority, 4),
                }
            )
        return result

    def _seed_for_roll(self, *, session_id: str, turn_index: int, user_action_id: str, roll_index: int) -> int:
        text = f"{session_id}:{turn_index}:{user_action_id}:{roll_index}"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return int(digest[:12], 16)

    def _build_user_scene_move(self, *, user_action: str, actor_id: str, scene_state: dict[str, Any]) -> SceneMove:
        return SceneMove(
            move_id="move-0-user",
            actor_id=actor_id,
            action_type="action",
            target=self._infer_user_target(user_action=user_action, actor_id=actor_id, scene_state=scene_state),
            description=self._normalize_move_description(user_action),
            source="user",
        )

    def _infer_user_target(self, *, user_action: str, actor_id: str, scene_state: dict[str, Any]) -> str:
        lowered = user_action.lower()
        present = scene_state.get("present", [])
        if isinstance(present, list):
            for raw in present:
                if not isinstance(raw, str):
                    continue
                candidate = raw.strip()
                if not candidate or candidate == actor_id:
                    continue
                if candidate.lower() in lowered:
                    return candidate
        return "scene"

    def _normalize_move_target(self, target: str) -> str:
        text = " ".join(target.strip().split())
        if not text:
            return "scene"
        if len(text) > 120:
            return text[:120].rstrip()
        return text

    def _normalize_move_description(self, description: str) -> str:
        text = " ".join(description.strip().split())
        if not text:
            return "acts with intent."
        if len(text) > 400:
            return text[:400].rstrip()
        return text

    def _normalize_action_type(self, action_type: str) -> str:
        value = action_type.strip().lower()
        if value == "reaction":
            return "reaction"
        return "action"

    def _resolve_move_outcomes(
        self,
        *,
        scene_moves: list[SceneMove],
        adjudications: list[MoveAdjudication],
        stat_blocks: dict[str, dict[str, Any]],
        session_id: str,
        turn_index: int,
        user_action_id: str,
    ) -> tuple[list[MoveOutcome], list[dict[str, Any]]]:
        adjudication_by_move_id: dict[str, MoveAdjudication] = {}
        for adjudication in adjudications:
            adjudication_by_move_id.setdefault(adjudication.move_id, adjudication)

        move_outcomes: list[MoveOutcome] = []
        dice_results: list[dict[str, Any]] = []
        roll_index = 0

        for move in scene_moves:
            adjudication = adjudication_by_move_id.get(move.move_id) or self._default_adjudication(move)
            if adjudication.actor_id != move.actor_id:
                adjudication = MoveAdjudication(
                    move_id=move.move_id,
                    actor_id=move.actor_id,
                    requires_skill_check=adjudication.requires_skill_check,
                    skill=adjudication.skill,
                    difficulty_class=adjudication.difficulty_class,
                    auto_outcome=adjudication.auto_outcome,
                    reasoning=adjudication.reasoning,
                )

            actor_stat_block = stat_blocks.get(move.actor_id, {})
            if adjudication.requires_skill_check:
                skill_key = self._resolve_skill_key(adjudication.skill, actor_stat_block)
                difficulty_class = adjudication.difficulty_class if isinstance(adjudication.difficulty_class, int) else 10
                modifier = self._get_stat_modifier(actor_stat_block, skill_key)
                expression = f"1d20{modifier:+d}" if modifier else "1d20"
                seed = self._seed_for_roll(
                    session_id=session_id,
                    turn_index=turn_index,
                    user_action_id=user_action_id,
                    roll_index=roll_index,
                )
                roll_result = roll_dice(expression, seed=seed)
                roll_index += 1
                success = roll_result.total >= difficulty_class
                outcome = MoveOutcome(
                    move_id=move.move_id,
                    actor_id=move.actor_id,
                    action_type=move.action_type,
                    target=move.target,
                    description=move.description,
                    requires_skill_check=True,
                    skill=skill_key,
                    difficulty_class=difficulty_class,
                    roll_expression=roll_result.expression,
                    rolls=roll_result.rolls,
                    modifier=roll_result.modifier,
                    total=roll_result.total,
                    success=success,
                    reasoning=adjudication.reasoning,
                )
                dice_results.append(
                    {
                        "move_id": move.move_id,
                        "expression": roll_result.expression,
                        "rolls": roll_result.rolls,
                        "modifier": roll_result.modifier,
                        "total": roll_result.total,
                        "seed": roll_result.seed,
                        "reason": adjudication.reasoning,
                        "character_id": move.actor_id,
                        "check_type": skill_key or "check",
                        "difficulty_class": difficulty_class,
                    }
                )
                move_outcomes.append(outcome)
                continue

            auto_outcome = adjudication.auto_outcome or "success"
            outcome = MoveOutcome(
                move_id=move.move_id,
                actor_id=move.actor_id,
                action_type=move.action_type,
                target=move.target,
                description=move.description,
                requires_skill_check=False,
                success=auto_outcome != "failure",
                reasoning=adjudication.reasoning or f"auto_{auto_outcome}",
            )
            move_outcomes.append(outcome)

        return move_outcomes, dice_results

    def _default_adjudication(self, move: SceneMove) -> MoveAdjudication:
        return MoveAdjudication(
            move_id=move.move_id,
            actor_id=move.actor_id,
            requires_skill_check=False,
            auto_outcome="success",
            reasoning="default_auto_success",
        )

    def _resolve_skill_key(self, skill: str | None, stat_block: dict[str, Any]) -> str | None:
        if not isinstance(stat_block, dict) or not stat_block:
            return None
        normalized_map = {
            self._normalize_identifier(str(key)): str(key)
            for key in stat_block.keys()
            if isinstance(key, str)
        }
        if isinstance(skill, str) and skill.strip():
            normalized_skill = self._normalize_identifier(skill)
            if normalized_skill in normalized_map:
                return normalized_map[normalized_skill]
            for normalized_key, original_key in normalized_map.items():
                if normalized_skill in normalized_key:
                    return original_key
        for key, value in stat_block.items():
            if isinstance(key, str) and isinstance(value, (int, float)) and not isinstance(value, bool):
                return key
        return None

    def _get_stat_modifier(self, stat_block: dict[str, Any], skill_key: str | None) -> int:
        if isinstance(skill_key, str):
            value = stat_block.get(skill_key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
        for value in stat_block.values():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
        return 0

    def _normalize_identifier(self, text: str) -> str:
        return re.sub(r"[^a-z0-9_]", "", text.strip().lower().replace(" ", "_"))

    def _build_persisted_actions(
        self,
        *,
        scene_moves: list[SceneMove],
        move_outcomes: list[MoveOutcome],
        user_action: str,
    ) -> list[dict[str, Any]]:
        outcome_by_move_id = {outcome.move_id: outcome for outcome in move_outcomes}
        actions: list[dict[str, Any]] = []
        for move in scene_moves:
            outcome = outcome_by_move_id.get(move.move_id)
            status = "success" if outcome is None or outcome.success else "failure"
            outcome_text = outcome.to_summary() if outcome is not None else "no_outcome"
            action_text = user_action if move.source == "user" else f"[{move.action_type}] {move.target}: {move.description}"
            actions.append(
                {
                    "actor_id": "user" if move.source == "user" else move.actor_id,
                    "action_text": action_text,
                    "status": status,
                    "outcome": outcome_text,
                }
            )
        return actions

    def _normalize_suggestions(self, suggestions: list[str]) -> list[str]:
        normalized: list[str] = []
        for suggestion in suggestions:
            text = " ".join(suggestion.strip().split())
            if not text:
                continue
            if len(text) > 120:
                text = text[:120].rstrip()
            if text not in normalized:
                normalized.append(text)
            if len(normalized) == 3:
                break
        if normalized:
            return normalized
        return self._fallback_suggestions()

    def _build_meta_text(
        self,
        *,
        dice_results: list[dict[str, Any]],
        state_ops: list[StateOp],
        move_outcomes: list[MoveOutcome],
    ) -> str | None:
        lines: list[str] = []

        if move_outcomes:
            lines.append("Action outcomes:")
            for outcome in move_outcomes:
                lines.append(f" - {outcome.to_summary()}")

        if dice_results:
            if lines:
                lines.append("")
            lines.append("Dice rolls:")
            for result in dice_results:
                expression = str(result.get("expression", ""))
                rolls = result.get("rolls", [])
                modifier = int(result.get("modifier", 0))
                total = result.get("total")
                reason = str(result.get("reason", "")).strip()
                character_id = str(result.get("character_id", "")).strip()
                check_type = str(result.get("check_type", "")).strip()
                who = character_id if character_id else "unknown"
                check = check_type if check_type else "check"
                modifier_text = f"+{modifier}" if modifier >= 0 else str(modifier)
                roll_text = f"{expression} ({rolls}) {modifier_text} = {total}"
                detail = f" - [{who}/{check}] {roll_text}"
                if reason:
                    detail += f" -- {reason}"
                lines.append(detail)

        if state_ops:
            if lines:
                lines.append("")
            lines.append("Scene state changes:")
            for op in state_ops:
                value_text = json.dumps(op.value, ensure_ascii=True) if op.value is not None else "null"
                lines.append(f" - {op.op} {op.path} {value_text}")

        if not lines:
            return None
        return "\n".join(lines)

    def _fallback_suggestions(self) -> list[str]:
        return [
            "I ask a direct question to break the stalemate.",
            "I set a clear boundary and name what I need right now.",
            "I shift the focus to one concrete next step.",
        ]

    def _normalize_state_op(self, op: StateOp) -> StateOp:
        if op.op not in {"increment", "decrement"}:
            return op
        value = op.value
        if isinstance(value, bool) or isinstance(value, (int, float)):
            return op
        if isinstance(value, str):
            trimmed = value.strip()
            try:
                parsed = float(trimmed) if "." in trimmed else int(trimmed)
                return StateOp(op=op.op, path=op.path, value=parsed)
            except ValueError:
                return op
        return op
