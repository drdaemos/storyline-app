"""Repository for managing per-character per-session runtime state."""

from pathlib import Path
from typing import Any

from .database_config import DatabaseConfig
from .db_models import CharacterStateDB


class CharacterStateRepository:
    """SQLAlchemy-based per-character state storage for simulation sessions."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def create_state(
        self,
        session_id: str,
        character_id: str,
        drives: dict[str, float],
        skills: dict[str, float],
        emotional_state: dict[str, Any],
        active_intent: dict[str, Any] | None = None,
    ) -> int:
        """Create a character state entry for a session. Returns the row ID."""
        with self.db_config.create_session() as db:
            state = CharacterStateDB(
                session_id=session_id,
                character_id=character_id,
                drives=drives,
                skills=skills,
                emotional_state=emotional_state,
                active_intent=active_intent,
                is_present=True,
                intended_destination=None,
                last_departure_tick=None,
            )
            db.add(state)
            db.commit()
            return state.id

    def get_state(self, session_id: str, character_id: str) -> dict[str, Any] | None:
        """Get a character's state for a session."""
        with self.db_config.create_session() as db:
            row = (
                db.query(CharacterStateDB)
                .filter(
                    CharacterStateDB.session_id == session_id,
                    CharacterStateDB.character_id == character_id,
                )
                .first()
            )

            if row:
                return self._row_to_dict(row)
            return None

    def get_session_states(self, session_id: str) -> list[dict[str, Any]]:
        """Get all character states for a session."""
        with self.db_config.create_session() as db:
            rows = (
                db.query(CharacterStateDB)
                .filter(CharacterStateDB.session_id == session_id)
                .all()
            )
            return [self._row_to_dict(r) for r in rows]

    def get_present_characters(self, session_id: str) -> list[dict[str, Any]]:
        """Get states only for characters currently present at the user's location."""
        with self.db_config.create_session() as db:
            rows = (
                db.query(CharacterStateDB)
                .filter(
                    CharacterStateDB.session_id == session_id,
                    CharacterStateDB.is_present.is_(True),
                )
                .all()
            )
            return [self._row_to_dict(r) for r in rows]

    def update_drives(self, session_id: str, character_id: str, drives: dict[str, float]) -> bool:
        """Update a character's drive values."""
        with self.db_config.create_session() as db:
            count = (
                db.query(CharacterStateDB)
                .filter(
                    CharacterStateDB.session_id == session_id,
                    CharacterStateDB.character_id == character_id,
                )
                .update({CharacterStateDB.drives: drives})
            )
            db.commit()
            return count > 0

    def update_skills(self, session_id: str, character_id: str, skills: dict[str, float]) -> bool:
        """Update a character's skill values."""
        with self.db_config.create_session() as db:
            count = (
                db.query(CharacterStateDB)
                .filter(
                    CharacterStateDB.session_id == session_id,
                    CharacterStateDB.character_id == character_id,
                )
                .update({CharacterStateDB.skills: skills})
            )
            db.commit()
            return count > 0

    def update_emotional_state(
        self, session_id: str, character_id: str, emotional_state: dict[str, Any]
    ) -> bool:
        """Update a character's emotional state."""
        with self.db_config.create_session() as db:
            count = (
                db.query(CharacterStateDB)
                .filter(
                    CharacterStateDB.session_id == session_id,
                    CharacterStateDB.character_id == character_id,
                )
                .update({CharacterStateDB.emotional_state: emotional_state})
            )
            db.commit()
            return count > 0

    def update_intent(
        self, session_id: str, character_id: str, intent: dict[str, Any] | None
    ) -> bool:
        """Update a character's active intent (None to clear)."""
        with self.db_config.create_session() as db:
            count = (
                db.query(CharacterStateDB)
                .filter(
                    CharacterStateDB.session_id == session_id,
                    CharacterStateDB.character_id == character_id,
                )
                .update({CharacterStateDB.active_intent: intent})
            )
            db.commit()
            return count > 0

    def update_presence(
        self,
        session_id: str,
        character_id: str,
        is_present: bool,
        intended_destination: str | None = None,
        last_departure_tick: int | None = None,
    ) -> bool:
        """Update a character's presence status and departure info."""
        with self.db_config.create_session() as db:
            updates: dict[str, Any] = {CharacterStateDB.is_present: is_present}
            if intended_destination is not None or not is_present:
                updates[CharacterStateDB.intended_destination] = intended_destination
            if last_departure_tick is not None or not is_present:
                updates[CharacterStateDB.last_departure_tick] = last_departure_tick

            count = (
                db.query(CharacterStateDB)
                .filter(
                    CharacterStateDB.session_id == session_id,
                    CharacterStateDB.character_id == character_id,
                )
                .update(updates)
            )
            db.commit()
            return count > 0

    def update_full_state(
        self,
        session_id: str,
        character_id: str,
        drives: dict[str, float],
        skills: dict[str, float],
        emotional_state: dict[str, Any],
        active_intent: dict[str, Any] | None,
        is_present: bool,
        intended_destination: str | None,
        last_departure_tick: int | None,
    ) -> bool:
        """Update all fields of a character state at once (e.g. snapshot restore)."""
        with self.db_config.create_session() as db:
            count = (
                db.query(CharacterStateDB)
                .filter(
                    CharacterStateDB.session_id == session_id,
                    CharacterStateDB.character_id == character_id,
                )
                .update({
                    CharacterStateDB.drives: drives,
                    CharacterStateDB.skills: skills,
                    CharacterStateDB.emotional_state: emotional_state,
                    CharacterStateDB.active_intent: active_intent,
                    CharacterStateDB.is_present: is_present,
                    CharacterStateDB.intended_destination: intended_destination,
                    CharacterStateDB.last_departure_tick: last_departure_tick,
                })
            )
            db.commit()
            return count > 0

    def delete_session_states(self, session_id: str) -> int:
        """Delete all character states for a session. Returns count deleted."""
        with self.db_config.create_session() as db:
            count = (
                db.query(CharacterStateDB)
                .filter(CharacterStateDB.session_id == session_id)
                .delete()
            )
            db.commit()
            return count

    def _row_to_dict(self, row: CharacterStateDB) -> dict[str, Any]:
        return {
            "id": row.id,
            "session_id": row.session_id,
            "character_id": row.character_id,
            "drives": row.drives,
            "skills": row.skills,
            "emotional_state": row.emotional_state,
            "active_intent": row.active_intent,
            "is_present": row.is_present,
            "intended_destination": row.intended_destination,
            "last_departure_tick": row.last_departure_tick,
        }

    def health_check(self) -> bool:
        return self.db_config.health_check()

    def close(self) -> None:
        self.db_config.dispose()
