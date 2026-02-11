from __future__ import annotations

import uuid
from collections.abc import Iterator
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from src.memory.database_config import DatabaseConfig
from src.memory.db_models import (
    RulesetRecord,
    SimulationAction,
    SimulationObservation,
    SimulationScenario,
    SimulationScenarioCharacter,
    SimulationScene,
    SimulationSceneRelation,
    SimulationSession,
    SimulationSessionCharacter,
    SimulationTurnEvent,
    WorldLoreRecord,
)
from src.simulation.contracts import (
    RuntimeObservation,
    RuntimeRuleset,
    RuntimeScene,
    RuntimeSession,
    RuntimeWorldLore,
    StartSimulationSessionInput,
)


class SimulationRepository:
    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)
        self._seed_defaults()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with self.db_config.create_session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def _seed_defaults(self) -> None:
        default_rulebook_text = (
            "Roll only on social risk, ambiguity, or tension shifts. "
            "Use 1d20 + relevant_stat. 16+ clean success, 10-15 mixed, 9- failure. "
            "Mixed or failure increments pressure_clock."
        )
        default_character_stat_schema = {
            "type": "object",
            "required": ["warmth", "self_awareness", "boundaries", "logic"],
            "properties": {
                "warmth": {"type": "integer", "min": 0, "max": 10},
                "self_awareness": {"type": "integer", "min": 0, "max": 10},
                "boundaries": {"type": "integer", "min": 0, "max": 10},
                "logic": {"type": "integer", "min": 0, "max": 10},
            },
            "additionalProperties": True,
        }
        default_scene_state_schema = {
            "type": "object",
            "required": ["location", "pressure_clock", "present"],
            "properties": {
                "location": {"type": "string", "minLength": 1},
                "pressure_clock": {"type": "integer", "min": 0},
                "present": {"type": "array", "items": {"type": "string"}},
                "relations": {"type": "array"},
                "time_minutes": {"type": "integer", "min": 0},
            },
            "additionalProperties": True,
        }

        with self.db_config.create_session() as session:
            everyday_tension = session.get(RulesetRecord, "everyday-tension")
            if everyday_tension is None:
                session.add(
                    RulesetRecord(
                        id="everyday-tension",
                        name="Everyday Tension",
                        rulebook_text=default_rulebook_text,
                        character_stat_schema=default_character_stat_schema,
                        scene_state_schema=default_scene_state_schema,
                        mechanics_guidance={"uses_dice": True, "dice_formats": ["NdM+K"]},
                    )
                )
            if session.get(WorldLoreRecord, "default-world") is None:
                session.add(
                    WorldLoreRecord(
                        id="default-world",
                        name="Default World",
                        lore_text="Grounded contemporary setting with plausible social dynamics.",
                        lore_json={"genre": "slice_of_life"},
                    )
                )
            session.commit()

    def get_ruleset(self, ruleset_id: str) -> RuntimeRuleset:
        with self.db_config.create_session() as session:
            row = session.get(RulesetRecord, ruleset_id)
            if row is None:
                raise ValueError(f"Unknown ruleset_id '{ruleset_id}'")
            return self._runtime_ruleset_from_row(row)

    def list_rulesets(self) -> list[RuntimeRuleset]:
        with self.db_config.create_session() as session:
            rows = session.query(RulesetRecord).order_by(RulesetRecord.updated_at.desc(), RulesetRecord.id.asc()).all()
            return [self._runtime_ruleset_from_row(row) for row in rows]

    def get_world_lore(self, world_lore_id: str) -> RuntimeWorldLore:
        with self.db_config.create_session() as session:
            row = session.get(WorldLoreRecord, world_lore_id)
            if row is None:
                raise ValueError(f"Unknown world_lore_id '{world_lore_id}'")
            return RuntimeWorldLore(id=row.id, name=row.name, lore_text=row.lore_text, lore_json=row.lore_json)

    def _runtime_ruleset_from_row(self, row: RulesetRecord) -> RuntimeRuleset:
        rulebook_text = row.rulebook_text
        scene_state_schema = row.scene_state_schema
        if row.id == "everyday-tension":
            rulebook_text = rulebook_text.replace(" (0..6)", "")
            scene_state_schema = self._strip_pressure_clock_upper_bound(scene_state_schema)
        return RuntimeRuleset(
            id=row.id,
            name=row.name,
            rulebook_text=rulebook_text,
            character_stat_schema=row.character_stat_schema,
            scene_state_schema=scene_state_schema,
            mechanics_guidance=row.mechanics_guidance,
        )

    @staticmethod
    def _strip_pressure_clock_upper_bound(schema: Any) -> Any:
        if not isinstance(schema, dict):
            return schema
        schema_copy = deepcopy(schema)
        properties = schema_copy.get("properties")
        if not isinstance(properties, dict):
            return schema_copy
        pressure_clock = properties.get("pressure_clock")
        if not isinstance(pressure_clock, dict):
            return schema_copy
        pressure_clock.pop("max", None)
        pressure_clock.pop("maximum", None)
        return schema_copy

    def create_session(self, data: StartSimulationSessionInput) -> RuntimeSession:
        with self.transaction() as session:
            scenario_id = data.scenario_id
            if scenario_id:
                scenario = session.get(SimulationScenario, scenario_id)
                if scenario is None:
                    raise ValueError(f"Unknown scenario_id '{scenario_id}'")
            else:
                scenario_id = str(uuid.uuid4())
                session.add(
                    SimulationScenario(
                        id=scenario_id,
                        character_id=data.npc_ids[0] if data.npc_ids else data.character_ids[0],
                        title="Ad-hoc session",
                        summary=data.intro_seed[:200],
                        scenario_data={},
                        ruleset_id=data.ruleset_id,
                        world_lore_id=data.world_lore_id,
                        scene_seed=data.scene_seed,
                        intro_seed=data.intro_seed,
                        tone="",
                        stakes="",
                        goals={},
                        user_id=data.user_id,
                    )
                )
                for character_id in data.character_ids:
                    session.add(SimulationScenarioCharacter(scenario_id=scenario_id, character_id=character_id))

            first_scene_id = str(uuid.uuid4())
            session.add(
                SimulationScene(
                    id=first_scene_id,
                    session_id=data.session_id,
                    scene_index=1,
                    state_json=data.scene_seed,
                )
            )
            sim_session = SimulationSession(
                id=data.session_id,
                scenario_id=scenario_id,
                ruleset_id=data.ruleset_id,
                world_lore_id=data.world_lore_id,
                current_scene_id=first_scene_id,
                current_turn_index=0,
                small_model_key=data.small_model_key,
                large_model_key=data.large_model_key,
                user_id=data.user_id,
            )
            session.add(sim_session)

            for character_id in data.character_ids:
                role = "npc" if character_id in data.npc_ids else "user_persona"
                session.add(
                    SimulationSessionCharacter(
                        session_id=data.session_id,
                        character_id=character_id,
                        role=role,
                        stat_block=data.stat_blocks[character_id],
                    )
                )

            session.add(
                SimulationTurnEvent(
                    id=str(uuid.uuid4()),
                    session_id=data.session_id,
                    scene_id=first_scene_id,
                    turn_index=0,
                    event_type="session_start",
                    step_name="engine_apply",
                    payload_json={"intro_seed": data.intro_seed, "scene_seed": data.scene_seed},
                    model_key=None,
                    prompt_version="sim-v2",
                    user_action_id=None,
                )
            )
            session.flush()

            return RuntimeSession(
                id=sim_session.id,
                ruleset_id=sim_session.ruleset_id,
                world_lore_id=sim_session.world_lore_id,
                current_scene_id=sim_session.current_scene_id,
                current_turn_index=sim_session.current_turn_index,
                small_model_key=sim_session.small_model_key,
                large_model_key=sim_session.large_model_key,
                user_id=sim_session.user_id,
                created_at=sim_session.created_at,
                updated_at=sim_session.updated_at,
            )

    def get_session(self, session_id: str, user_id: str) -> RuntimeSession:
        with self.db_config.create_session() as session:
            return self.get_session_in_tx(session, session_id, user_id)

    def get_session_in_tx(self, db: Session, session_id: str, user_id: str) -> RuntimeSession:
        row = db.get(SimulationSession, session_id)
        if row is None or row.user_id != user_id:
            raise ValueError(f"Unknown session_id '{session_id}'")
        return RuntimeSession(
            id=row.id,
            ruleset_id=row.ruleset_id,
            world_lore_id=row.world_lore_id,
            current_scene_id=row.current_scene_id,
            current_turn_index=row.current_turn_index,
            small_model_key=row.small_model_key,
            large_model_key=row.large_model_key,
            user_id=row.user_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def get_scene(self, scene_id: str) -> RuntimeScene:
        with self.db_config.create_session() as session:
            return self.get_scene_in_tx(session, scene_id)

    def get_scene_in_tx(self, db: Session, scene_id: str) -> RuntimeScene:
        row = db.get(SimulationScene, scene_id)
        if row is None:
            raise ValueError(f"Unknown scene_id '{scene_id}'")
        return RuntimeScene(id=row.id, session_id=row.session_id, scene_index=row.scene_index, state_json=row.state_json, created_at=row.created_at)

    def list_session_characters(self, session_id: str) -> list[dict[str, Any]]:
        with self.db_config.create_session() as session:
            return self.list_session_characters_in_tx(session, session_id)

    def list_session_characters_in_tx(self, db: Session, session_id: str) -> list[dict[str, Any]]:
        rows = db.query(SimulationSessionCharacter).filter(SimulationSessionCharacter.session_id == session_id).all()
        return [{"character_id": row.character_id, "role": row.role, "stat_block": row.stat_block} for row in rows]

    def list_recent_observations(self, session_id: str, character_id: str, limit: int = 5) -> list[RuntimeObservation]:
        with self.db_config.create_session() as session:
            return self.list_recent_observations_in_tx(session, session_id, character_id, limit)

    def list_recent_observations_in_tx(self, db: Session, session_id: str, character_id: str, limit: int = 5) -> list[RuntimeObservation]:
        rows = (
            db.query(SimulationObservation)
            .filter(
                and_(
                    SimulationObservation.session_id == session_id,
                    SimulationObservation.character_id == character_id,
                )
            )
            .order_by(desc(SimulationObservation.created_at))
            .limit(limit)
            .all()
        )
        return [
            RuntimeObservation(
                id=row.id,
                session_id=row.session_id,
                scene_id=row.scene_id,
                character_id=row.character_id,
                content=row.content,
                importance=row.importance,
                reinforcement_count=row.reinforcement_count,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def session_has_user_action_id(self, db: Session, session_id: str, user_action_id: str) -> bool:
        return db.query(SimulationTurnEvent).filter(SimulationTurnEvent.session_id == session_id, SimulationTurnEvent.user_action_id == user_action_id).first() is not None

    def get_narration_for_action_id(self, db: Session, session_id: str, user_action_id: str) -> str | None:
        marker = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.user_action_id == user_action_id,
                SimulationTurnEvent.event_type == "user_action",
            )
            .first()
        )
        if marker is None:
            return None
        narrator = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.turn_index == marker.turn_index,
                SimulationTurnEvent.event_type == "model_output",
                SimulationTurnEvent.step_name == "narrator",
            )
            .first()
        )
        if narrator is None:
            return None
        return str(narrator.payload_json.get("narration_text", ""))

    def get_suggestions_for_action_id(self, db: Session, session_id: str, user_action_id: str) -> list[str]:
        marker = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.user_action_id == user_action_id,
                SimulationTurnEvent.event_type == "user_action",
            )
            .first()
        )
        if marker is None:
            return []
        suggestion_event = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.turn_index == marker.turn_index,
                SimulationTurnEvent.event_type == "model_output",
                SimulationTurnEvent.step_name == "action_suggestions",
            )
            .first()
        )
        if suggestion_event is None:
            return []
        suggestions = suggestion_event.payload_json.get("suggested_actions", [])
        if not isinstance(suggestions, list):
            return []
        return [str(item) for item in suggestions if isinstance(item, str)]

    def get_meta_text_for_action_id(self, db: Session, session_id: str, user_action_id: str) -> str | None:
        marker = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.user_action_id == user_action_id,
                SimulationTurnEvent.event_type == "user_action",
            )
            .first()
        )
        if marker is None:
            return None
        narrator = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.turn_index == marker.turn_index,
                SimulationTurnEvent.event_type == "model_output",
                SimulationTurnEvent.step_name == "narrator",
            )
            .first()
        )
        if narrator is None:
            return None
        meta_text = narrator.payload_json.get("meta_text")
        return str(meta_text) if isinstance(meta_text, str) else None

    def write_turn_outputs(
        self,
        db: Session,
        session_id: str,
        expected_current_scene_id: str,
        expected_turn_index: int,
        narration_text: str,
        narration_meta_text: str | None,
        state_json: dict[str, Any],
        user_action_id: str,
        model_events: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        observations: list[dict[str, Any]],
        relations: list[dict[str, Any]],
    ) -> tuple[str, int]:
        session_row = db.get(SimulationSession, session_id)
        if session_row is None:
            raise ValueError(f"Unknown session '{session_id}'")
        if session_row.current_scene_id != expected_current_scene_id or session_row.current_turn_index != expected_turn_index:
            raise ValueError("Optimistic concurrency conflict")

        next_turn = expected_turn_index + 1
        new_scene_id = str(uuid.uuid4())
        scene_row = SimulationScene(id=new_scene_id, session_id=session_id, scene_index=next_turn + 1, state_json=state_json)
        db.add(scene_row)

        session_row.current_scene_id = new_scene_id
        session_row.current_turn_index = next_turn
        session_row.updated_at = datetime.now()

        for action in actions:
            db.add(
                SimulationAction(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    scene_id=new_scene_id,
                    turn_index=next_turn,
                    actor_id=action["actor_id"],
                    action_text=action["action_text"],
                    resolved_outcome=action.get("status", "") + ": " + str(action.get("outcome", "")),
                )
            )

        for obs in observations:
            db.add(
                SimulationObservation(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    scene_id=new_scene_id,
                    character_id=obs["character_id"],
                    content=obs["content"],
                    importance=obs["importance"],
                    reinforcement_count=obs.get("reinforcement_count", 0),
                )
            )

        for rel in relations:
            char_a = rel["a"]
            char_b = rel["b"]
            low, high = sorted([char_a, char_b])
            db.add(
                SimulationSceneRelation(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    scene_id=new_scene_id,
                    character_a_id=low,
                    character_b_id=high,
                    trust=int(rel.get("trust", 0)),
                    tension=int(rel.get("tension", 0)),
                    closeness=int(rel.get("closeness", 0)),
                )
            )

        # mandatory narrator message event
        db.add(
            SimulationTurnEvent(
                id=str(uuid.uuid4()),
                session_id=session_id,
                scene_id=new_scene_id,
                turn_index=next_turn,
                event_type="user_action",
                step_name="turn_start",
                user_action_id=user_action_id,
                payload_json={},
                model_key=None,
                prompt_version="sim-v2",
            )
        )

        # mandatory narrator message event
        db.add(
            SimulationTurnEvent(
                id=str(uuid.uuid4()),
                session_id=session_id,
                scene_id=new_scene_id,
                turn_index=next_turn,
                event_type="model_output",
                step_name="narrator",
                user_action_id=None,
                payload_json={"narration_text": narration_text, "meta_text": narration_meta_text},
                model_key=None,
                prompt_version="sim-v2",
            )
        )
        for event in model_events:
            db.add(
                SimulationTurnEvent(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    scene_id=new_scene_id,
                    turn_index=next_turn,
                    event_type=event["event_type"],
                    step_name=event["step_name"],
                    user_action_id=None,
                    payload_json=event["payload_json"],
                    model_key=event.get("model_key"),
                    prompt_version=event.get("prompt_version", "sim-v2"),
                )
            )

        return new_scene_id, next_turn
