from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func

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


class SimulationSessionStore:
    """Read/admin store for simulation sessions used by API projection endpoints."""

    def __init__(self) -> None:
        self.db_config = DatabaseConfig()

    def list_user_sessions(self, user_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.db_config.create_session() as session:
            rows = (
                session.query(SimulationSession)
                .filter(SimulationSession.user_id == user_id)
                .order_by(desc(SimulationSession.updated_at))
                .limit(limit)
                .all()
            )
            return [self._build_session_overview_in_tx(session, row) for row in rows]

    def get_session_chat_details(self, session_id: str, user_id: str, limit: int = 50) -> dict[str, Any] | None:
        with self.db_config.create_session() as session:
            row = session.get(SimulationSession, session_id)
            if row is None or row.user_id != user_id:
                return None
            overview = self._build_session_overview_in_tx(session, row)
            full_messages = self._build_session_messages_in_tx(session, session_id)
            latest_suggested_actions = self._get_latest_suggested_actions_in_tx(session, session_id)
            messages = full_messages[-limit:] if limit > 0 else full_messages
            overview["message_count"] = len(full_messages)
            overview["last_message_time"] = (
                messages[-1]["created_at"].isoformat() if messages else row.updated_at.isoformat()
            )
            overview["suggested_actions"] = latest_suggested_actions
            overview["messages"] = [
                {
                    "role": msg["role"],
                    "content": msg["content"],
                    "meta_text": msg.get("meta_text"),
                    "created_at": msg["created_at"].isoformat(),
                }
                for msg in messages
            ]
            return overview

    def get_session_persona_id(self, session_id: str, user_id: str) -> str | None:
        with self.db_config.create_session() as session:
            row = session.get(SimulationSession, session_id)
            if row is None or row.user_id != user_id:
                return None
            persona = (
                session.query(SimulationSessionCharacter)
                .filter(
                    SimulationSessionCharacter.session_id == session_id,
                    SimulationSessionCharacter.role == "user_persona",
                )
                .order_by(SimulationSessionCharacter.created_at.asc())
                .first()
            )
            return persona.character_id if persona else None

    def build_session_summary_text(self, session_id: str, user_id: str) -> tuple[str, bool]:
        with self.db_config.create_session() as session:
            row = session.get(SimulationSession, session_id)
            if row is None or row.user_id != user_id:
                raise ValueError(f"Unknown session_id '{session_id}'")

            narrator_rows = (
                session.query(SimulationTurnEvent)
                .filter(
                    SimulationTurnEvent.session_id == session_id,
                    SimulationTurnEvent.event_type == "model_output",
                    SimulationTurnEvent.step_name == "narrator",
                )
                .order_by(SimulationTurnEvent.turn_index.asc(), SimulationTurnEvent.created_at.asc())
                .all()
            )
            if not narrator_rows:
                return ("No summary available yet. Summary will be generated after the conversation progresses.", False)

            ruleset = session.get(RulesetRecord, row.ruleset_id)
            world_lore = session.get(WorldLoreRecord, row.world_lore_id)
            current_scene = session.get(SimulationScene, row.current_scene_id)

            lines: list[str] = []
            lines.append(f"Session: {session_id}")
            lines.append(f"Ruleset: {ruleset.name if ruleset else row.ruleset_id}")
            lines.append(f"World lore: {world_lore.name if world_lore else row.world_lore_id}")
            lines.append(f"Turns completed: {row.current_turn_index}")
            if current_scene and isinstance(current_scene.state_json, dict):
                state = current_scene.state_json
                location = state.get("location")
                pressure = state.get("pressure_clock")
                if isinstance(location, str) and location:
                    lines.append(f"Current location: {location}")
                if isinstance(pressure, int):
                    lines.append(f"Pressure clock: {pressure}")

            lines.append("")
            lines.append("Recent narrator beats:")
            for idx, event in enumerate(narrator_rows[-8:], start=1):
                narration = event.payload_json.get("narration_text", "")
                if not isinstance(narration, str):
                    narration = ""
                compact = " ".join(narration.split())
                if len(compact) > 220:
                    compact = f"{compact[:220].rstrip()}..."
                lines.append(f"{idx}. {compact}")

            return ("\n".join(lines), True)

    def delete_session(self, session_id: str, user_id: str) -> bool:
        with self.db_config.create_session() as db:
            row = db.get(SimulationSession, session_id)
            if row is None or row.user_id != user_id:
                return False
            scenario_id = row.scenario_id

            db.query(SimulationTurnEvent).filter(SimulationTurnEvent.session_id == session_id).delete()
            db.query(SimulationAction).filter(SimulationAction.session_id == session_id).delete()
            db.query(SimulationObservation).filter(SimulationObservation.session_id == session_id).delete()
            db.query(SimulationSceneRelation).filter(SimulationSceneRelation.session_id == session_id).delete()
            db.query(SimulationSessionCharacter).filter(SimulationSessionCharacter.session_id == session_id).delete()
            db.query(SimulationScene).filter(SimulationScene.session_id == session_id).delete()
            db.query(SimulationSession).filter(SimulationSession.id == session_id).delete()

            # Best-effort cleanup for ad-hoc per-session scenarios.
            if scenario_id:
                remaining = (
                    db.query(func.count(SimulationSession.id))
                    .filter(SimulationSession.scenario_id == scenario_id)
                    .scalar()
                )
                if remaining == 0:
                    db.query(SimulationScenarioCharacter).filter(
                        SimulationScenarioCharacter.scenario_id == scenario_id
                    ).delete()
                    db.query(SimulationScenario).filter(SimulationScenario.id == scenario_id).delete()
            db.commit()
            return True

    def _build_session_overview_in_tx(self, db: Any, row: SimulationSession) -> dict[str, Any]:
        primary_character_id = self._get_primary_character_id_in_tx(db, row.id)
        messages = self._build_session_messages_in_tx(db, row.id)
        last_character_response = None
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                last_character_response = msg["content"]
                break
        last_message_time = messages[-1]["created_at"].isoformat() if messages else row.updated_at.isoformat()
        return {
            "session_id": row.id,
            "character_name": primary_character_id or "",
            "message_count": len(messages),
            "last_message_time": last_message_time,
            "last_character_response": last_character_response,
        }

    def _get_primary_character_id_in_tx(self, db: Any, session_id: str) -> str | None:
        npc_row = (
            db.query(SimulationSessionCharacter)
            .filter(
                SimulationSessionCharacter.session_id == session_id,
                SimulationSessionCharacter.role == "npc",
            )
            .order_by(
                SimulationSessionCharacter.created_at.asc(),
                SimulationSessionCharacter.character_id.asc(),
            )
            .first()
        )
        if npc_row:
            return npc_row.character_id
        any_row = (
            db.query(SimulationSessionCharacter)
            .filter(SimulationSessionCharacter.session_id == session_id)
            .order_by(
                SimulationSessionCharacter.created_at.asc(),
                SimulationSessionCharacter.character_id.asc(),
            )
            .first()
        )
        return any_row.character_id if any_row else None

    def _build_session_messages_in_tx(self, db: Any, session_id: str) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        start_event = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.event_type == "session_start",
            )
            .order_by(SimulationTurnEvent.created_at.asc())
            .first()
        )
        if start_event:
            intro_seed = start_event.payload_json.get("intro_seed")
            if isinstance(intro_seed, str) and intro_seed.strip():
                messages.append(
                    {
                        "role": "assistant",
                        "content": intro_seed,
                        "meta_text": None,
                        "created_at": start_event.created_at,
                    }
                )

        user_rows = (
            db.query(SimulationAction)
            .filter(
                SimulationAction.session_id == session_id,
                SimulationAction.actor_id == "user",
            )
            .order_by(SimulationAction.turn_index.asc(), SimulationAction.created_at.asc())
            .all()
        )
        narrator_rows = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.event_type == "model_output",
                SimulationTurnEvent.step_name == "narrator",
            )
            .order_by(SimulationTurnEvent.turn_index.asc(), SimulationTurnEvent.created_at.asc())
            .all()
        )

        narrator_by_turn: dict[int, SimulationTurnEvent] = {}
        for row in narrator_rows:
            narrator_by_turn.setdefault(row.turn_index, row)

        for action in user_rows:
            messages.append(
                {
                    "role": "user",
                    "content": action.action_text,
                    "meta_text": None,
                    "created_at": action.created_at,
                }
            )
            narrator = narrator_by_turn.get(action.turn_index)
            if narrator:
                narration = narrator.payload_json.get("narration_text")
                narration_text = str(narration) if isinstance(narration, str) else ""
                meta = narrator.payload_json.get("meta_text")
                meta_text = str(meta) if isinstance(meta, str) else None
                messages.append(
                    {
                        "role": "assistant",
                        "content": narration_text,
                        "meta_text": meta_text,
                        "created_at": narrator.created_at,
                    }
                )

        messages.sort(key=lambda msg: msg["created_at"])
        return messages

    def _get_latest_suggested_actions_in_tx(self, db: Any, session_id: str) -> list[str]:
        row = (
            db.query(SimulationTurnEvent)
            .filter(
                SimulationTurnEvent.session_id == session_id,
                SimulationTurnEvent.event_type == "model_output",
                SimulationTurnEvent.step_name == "action_suggestions",
            )
            .order_by(SimulationTurnEvent.turn_index.desc(), SimulationTurnEvent.created_at.desc())
            .first()
        )
        if row is None:
            return []
        suggestions = row.payload_json.get("suggested_actions", [])
        if not isinstance(suggestions, list):
            return []
        normalized: list[str] = []
        for item in suggestions:
            if not isinstance(item, str):
                continue
            value = " ".join(item.split()).strip()
            if not value or value in normalized:
                continue
            normalized.append(value)
            if len(normalized) == 3:
                break
        return normalized
