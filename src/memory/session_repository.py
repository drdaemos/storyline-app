"""Repository for managing simulation sessions."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import or_

from .database_config import DatabaseConfig
from .db_models import SessionDB


class SessionRepository:
    """SQLAlchemy-based persistent session storage with world state management."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def create_session(
        self,
        scenario_id: str,
        world_state: dict[str, Any],
        user_id: str = "anonymous",
        session_id: str | None = None,
    ) -> str:
        """Create a new simulation session. Returns the session ID."""
        if session_id is None:
            session_id = str(uuid.uuid4())

        with self.db_config.create_session() as db:
            session_row = SessionDB(
                id=session_id,
                scenario_id=scenario_id,
                user_id=user_id,
                world_state=world_state,
                turn_counter=0,
                narration_history=[],
                location_history=[],
                status="active",
                snapshot=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(session_row)
            db.commit()
            return session_id

    def get_session(self, session_id: str, user_id: str = "anonymous") -> dict[str, Any] | None:
        """Retrieve a session by ID."""
        with self.db_config.create_session() as db:
            row = (
                db.query(SessionDB)
                .filter(
                    SessionDB.id == session_id,
                    or_(SessionDB.user_id == user_id, SessionDB.user_id == "anonymous"),
                )
                .first()
            )

            if row:
                return self._row_to_dict(row)
            return None

    def get_user_sessions(
        self,
        user_id: str = "anonymous",
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve sessions for a user, optionally filtered by status."""
        with self.db_config.create_session() as db:
            query = db.query(SessionDB).filter(
                or_(SessionDB.user_id == user_id, SessionDB.user_id == "anonymous")
            )

            if status is not None:
                query = query.filter(SessionDB.status == status)

            rows = query.order_by(SessionDB.updated_at.desc()).limit(limit).all()
            return [self._row_to_dict(r) for r in rows]

    def update_world_state(self, session_id: str, world_state: dict[str, Any]) -> bool:
        """Update the world state for a session."""
        with self.db_config.create_session() as db:
            count = (
                db.query(SessionDB)
                .filter(SessionDB.id == session_id)
                .update({
                    SessionDB.world_state: world_state,
                    SessionDB.updated_at: datetime.now(),
                })
            )
            db.commit()
            return count > 0

    def increment_turn(self, session_id: str) -> int:
        """Increment the turn counter and return the new value."""
        with self.db_config.create_session() as db:
            row = db.query(SessionDB).filter(SessionDB.id == session_id).first()
            if not row:
                return -1
            row.turn_counter += 1
            row.updated_at = datetime.now()
            db.commit()
            return row.turn_counter

    def append_narration(self, session_id: str, narration: str, max_history: int = 5) -> bool:
        """Append a narration to the history, keeping only the last max_history entries."""
        with self.db_config.create_session() as db:
            row = db.query(SessionDB).filter(SessionDB.id == session_id).first()
            if not row:
                return False

            history = list(row.narration_history or [])
            history.append(narration)
            if len(history) > max_history:
                history = history[-max_history:]

            row.narration_history = history
            row.updated_at = datetime.now()
            db.commit()
            return True

    def append_location(self, session_id: str, location_entry: dict[str, Any]) -> bool:
        """Append a location entry to the location history."""
        with self.db_config.create_session() as db:
            row = db.query(SessionDB).filter(SessionDB.id == session_id).first()
            if not row:
                return False

            history = list(row.location_history or [])
            history.append(location_entry)
            row.location_history = history
            row.updated_at = datetime.now()
            db.commit()
            return True

    def update_status(self, session_id: str, status: str) -> bool:
        """Update session status (active, paused, completed)."""
        with self.db_config.create_session() as db:
            count = (
                db.query(SessionDB)
                .filter(SessionDB.id == session_id)
                .update({
                    SessionDB.status: status,
                    SessionDB.updated_at: datetime.now(),
                })
            )
            db.commit()
            return count > 0

    def save_snapshot(self, session_id: str, snapshot: dict[str, Any]) -> bool:
        """Save a turn boundary snapshot for regeneration support."""
        with self.db_config.create_session() as db:
            count = (
                db.query(SessionDB)
                .filter(SessionDB.id == session_id)
                .update({
                    SessionDB.snapshot: snapshot,
                    SessionDB.updated_at: datetime.now(),
                })
            )
            db.commit()
            return count > 0

    def get_snapshot(self, session_id: str) -> dict[str, Any] | None:
        """Get the last saved snapshot for a session."""
        with self.db_config.create_session() as db:
            row = db.query(SessionDB).filter(SessionDB.id == session_id).first()
            if row and row.snapshot:
                return row.snapshot
            return None

    def delete_session(self, session_id: str, user_id: str = "anonymous") -> bool:
        """Delete a session by ID."""
        with self.db_config.create_session() as db:
            count = (
                db.query(SessionDB)
                .filter(SessionDB.id == session_id, SessionDB.user_id == user_id)
                .delete()
            )
            db.commit()
            return count > 0

    def _row_to_dict(self, row: SessionDB) -> dict[str, Any]:
        return {
            "id": row.id,
            "scenario_id": row.scenario_id,
            "user_id": row.user_id,
            "world_state": row.world_state,
            "turn_counter": row.turn_counter,
            "narration_history": row.narration_history,
            "location_history": row.location_history,
            "status": row.status,
            "snapshot": row.snapshot,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    def health_check(self) -> bool:
        return self.db_config.health_check()

    def close(self) -> None:
        self.db_config.dispose()
