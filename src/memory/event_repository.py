"""Repository for managing per-character event streams (observations and reflections)."""

from datetime import datetime
from pathlib import Path
from typing import Any

from .database_config import DatabaseConfig
from .db_models import EventDB


class EventRepository:
    """SQLAlchemy-based event stream storage with decay-based scoring."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def add_event(
        self,
        event_id: str,
        session_id: str,
        character_id: str,
        event_type: str,
        tick: int,
        subject: list[str],
        content: str,
        importance: int = 2,
        decay_rate: float = 0.3,
        initial_decay: float = 10.0,
        source_refs: list[str] | None = None,
        visibility: str | None = None,
    ) -> str:
        """Add an event (observation or reflection) to a character's stream."""
        with self.db_config.create_session() as db:
            event = EventDB(
                id=event_id,
                session_id=session_id,
                character_id=character_id,
                type=event_type,
                tick=tick,
                subject=subject,
                content=content,
                importance=importance,
                decay_rate=decay_rate,
                initial_decay=initial_decay,
                source_refs=source_refs or [],
                visibility=visibility,
                created_at=datetime.now(),
            )
            db.add(event)
            db.commit()
            return event_id

    def get_events(
        self,
        session_id: str,
        character_id: str,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get events for a character in a session, optionally filtered by type."""
        with self.db_config.create_session() as db:
            query = db.query(EventDB).filter(
                EventDB.session_id == session_id,
                EventDB.character_id == character_id,
            )

            if event_type is not None:
                query = query.filter(EventDB.type == event_type)

            query = query.order_by(EventDB.tick.desc())

            if limit is not None:
                query = query.limit(limit)

            rows = query.all()
            return [self._row_to_dict(r) for r in rows]

    def get_session_events(
        self,
        session_id: str,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all events across all characters for a session."""
        with self.db_config.create_session() as db:
            query = db.query(EventDB).filter(EventDB.session_id == session_id)

            if event_type is not None:
                query = query.filter(EventDB.type == event_type)

            rows = query.order_by(EventDB.tick.desc()).all()
            return [self._row_to_dict(r) for r in rows]

    def get_scored_events(
        self,
        session_id: str,
        character_id: str,
        current_tick: int,
        subject_filter: list[str] | None = None,
        min_score: float = 0.1,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get events scored by importance * remaining_decay * recency_bonus.

        Decay formula: remaining_decay = initial_decay - (current_tick - creation_tick) * decay_rate
        Score: importance * max(remaining_decay, 0) * recency_bonus
        Recency bonus: 1.5 if created this tick, 1.0 otherwise

        Events with score < min_score are excluded.
        """
        with self.db_config.create_session() as db:
            rows = (
                db.query(EventDB)
                .filter(
                    EventDB.session_id == session_id,
                    EventDB.character_id == character_id,
                )
                .all()
            )

            scored: list[dict[str, Any]] = []
            for row in rows:
                # Apply subject filter if provided
                if subject_filter:
                    row_subjects = set(row.subject or [])
                    if not row_subjects.intersection(subject_filter):
                        continue

                # Check visibility — skip actor_only events not belonging to this character
                if row.visibility == "actor_only" and row.character_id != character_id:
                    continue

                # Calculate decay
                age = current_tick - row.tick
                remaining_decay = row.initial_decay - (age * row.decay_rate)
                if remaining_decay <= 0:
                    continue

                # Recency bonus
                recency_bonus = 1.5 if row.tick == current_tick else 1.0

                score = row.importance * remaining_decay * recency_bonus

                if score < min_score:
                    continue

                event_dict = self._row_to_dict(row)
                event_dict["score"] = score
                event_dict["remaining_decay"] = remaining_decay
                scored.append(event_dict)

            # Sort by score descending
            scored.sort(key=lambda e: e["score"], reverse=True)

            return scored[:limit]

    def assemble_memory(
        self,
        session_id: str,
        character_id: str,
        current_tick: int,
        subject_filter: list[str] | None = None,
        limit: int = 30,
    ) -> str:
        """Assemble a memory string for use in prompts.

        Returns a formatted string of scored events, most relevant first.
        """
        events = self.get_scored_events(
            session_id=session_id,
            character_id=character_id,
            current_tick=current_tick,
            subject_filter=subject_filter,
            limit=limit,
        )

        if not events:
            return "(No relevant memories)"

        lines: list[str] = []
        for event in events:
            prefix = "OBS" if event["type"] == "observation" else "REF"
            tick_label = f"t{event['tick']}"
            subjects = ", ".join(event["subject"])
            lines.append(f"[{prefix} {tick_label} | {subjects}] {event['content']}")

        return "\n".join(lines)

    def get_event_count(self, session_id: str, character_id: str) -> int:
        """Get total event count for a character in a session."""
        with self.db_config.create_session() as db:
            return (
                db.query(EventDB)
                .filter(
                    EventDB.session_id == session_id,
                    EventDB.character_id == character_id,
                )
                .count()
            )

    def prune_decayed_events(
        self,
        session_id: str,
        character_id: str,
        current_tick: int,
        max_events: int = 100,
    ) -> int:
        """Remove fully decayed events, keeping at most max_events.

        An event is fully decayed when: initial_decay - (current_tick - tick) * decay_rate <= 0

        Returns the number of events pruned.
        """
        with self.db_config.create_session() as db:
            rows = (
                db.query(EventDB)
                .filter(
                    EventDB.session_id == session_id,
                    EventDB.character_id == character_id,
                )
                .all()
            )

            ids_to_delete: list[str] = []
            surviving: list[EventDB] = []

            for row in rows:
                age = current_tick - row.tick
                remaining = row.initial_decay - (age * row.decay_rate)
                if remaining <= 0:
                    ids_to_delete.append(row.id)
                else:
                    surviving.append(row)

            # If still over max_events, remove lowest-scored survivors
            if len(surviving) > max_events:
                scored = []
                for row in surviving:
                    age = current_tick - row.tick
                    remaining = row.initial_decay - (age * row.decay_rate)
                    score = row.importance * remaining
                    scored.append((score, row.id))

                scored.sort(key=lambda x: x[0])
                excess = len(surviving) - max_events
                for _, event_id in scored[:excess]:
                    ids_to_delete.append(event_id)

            if ids_to_delete:
                db.query(EventDB).filter(EventDB.id.in_(ids_to_delete)).delete(
                    synchronize_session="fetch"
                )
                db.commit()

            return len(ids_to_delete)

    def delete_session_events(self, session_id: str) -> int:
        """Delete all events for a session. Returns count deleted."""
        with self.db_config.create_session() as db:
            count = (
                db.query(EventDB)
                .filter(EventDB.session_id == session_id)
                .delete()
            )
            db.commit()
            return count

    def get_events_since_tick(
        self,
        session_id: str,
        character_id: str,
        since_tick: int,
    ) -> list[dict[str, Any]]:
        """Get events created at or after a specific tick."""
        with self.db_config.create_session() as db:
            rows = (
                db.query(EventDB)
                .filter(
                    EventDB.session_id == session_id,
                    EventDB.character_id == character_id,
                    EventDB.tick >= since_tick,
                )
                .order_by(EventDB.tick)
                .all()
            )
            return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row: EventDB) -> dict[str, Any]:
        return {
            "id": row.id,
            "session_id": row.session_id,
            "character_id": row.character_id,
            "type": row.type,
            "tick": row.tick,
            "subject": row.subject,
            "content": row.content,
            "importance": row.importance,
            "decay_rate": row.decay_rate,
            "initial_decay": row.initial_decay,
            "source_refs": row.source_refs,
            "visibility": row.visibility,
            "created_at": row.created_at.isoformat(),
        }

    def health_check(self) -> bool:
        return self.db_config.health_check()

    def close(self) -> None:
        self.db_config.dispose()
