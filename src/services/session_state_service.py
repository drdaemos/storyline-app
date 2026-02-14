"""Service for managing session state: world state, character presence, snapshots."""

from typing import Any

from src.memory.character_state_repository import CharacterStateRepository
from src.memory.session_repository import SessionRepository
from src.models.simulation import (
    CharacterStateData,
    EmotionalStateData,
    TurnSnapshot,
    WorldState,
)


class SessionStateService:
    """Manages world state, character presence, turn counter, and snapshots."""

    def __init__(
        self,
        session_repository: SessionRepository,
        character_state_repository: CharacterStateRepository,
    ) -> None:
        self.sessions = session_repository
        self.char_states = character_state_repository

    def get_world_state(self, session_id: str, user_id: str = "anonymous") -> WorldState | None:
        """Get the current world state for a session."""
        session = self.sessions.get_session(session_id, user_id)
        if not session:
            return None
        return WorldState(**session.get("world_state", {}))

    def update_world_state(self, session_id: str, world_state: WorldState) -> bool:
        """Update the world state for a session."""
        return self.sessions.update_world_state(session_id, world_state.model_dump())

    def get_character_state(
        self, session_id: str, character_id: str
    ) -> CharacterStateData | None:
        """Get a character's state as a domain model."""
        raw = self.char_states.get_state(session_id, character_id)
        if not raw:
            return None
        return self._raw_to_character_state(raw)

    def get_all_character_states(
        self, session_id: str
    ) -> dict[str, CharacterStateData]:
        """Get all character states for a session as a dict keyed by character_id."""
        raw_list = self.char_states.get_session_states(session_id)
        return {
            r["character_id"]: self._raw_to_character_state(r)
            for r in raw_list
        }

    def get_present_character_ids(self, session_id: str) -> list[str]:
        """Get IDs of characters currently present at the user's location."""
        present = self.char_states.get_present_characters(session_id)
        return [r["character_id"] for r in present]

    def save_character_state(
        self,
        session_id: str,
        character_id: str,
        state: CharacterStateData,
    ) -> bool:
        """Persist a character state. Creates if not exists, updates if exists."""
        existing = self.char_states.get_state(session_id, character_id)

        emotional_dict = state.emotional_state.model_dump() if isinstance(
            state.emotional_state, EmotionalStateData
        ) else state.emotional_state

        intent_dict = state.active_intent.model_dump() if state.active_intent else None

        if existing:
            return self.char_states.update_full_state(
                session_id=session_id,
                character_id=character_id,
                drives=state.drives,
                skills=state.skills,
                emotional_state=emotional_dict,
                active_intent=intent_dict,
                is_present=state.is_present,
                intended_destination=state.intended_destination,
                last_departure_tick=state.last_departure_tick,
            )
        else:
            self.char_states.create_state(
                session_id=session_id,
                character_id=character_id,
                drives=state.drives,
                skills=state.skills,
                emotional_state=emotional_dict,
                active_intent=intent_dict,
            )
            if not state.is_present:
                self.char_states.update_presence(
                    session_id, character_id,
                    is_present=False,
                    intended_destination=state.intended_destination,
                    last_departure_tick=state.last_departure_tick,
                )
            return True

    def increment_turn(self, session_id: str) -> int:
        """Increment turn counter. Returns new value."""
        return self.sessions.increment_turn(session_id)

    def get_turn_counter(self, session_id: str, user_id: str = "anonymous") -> int:
        """Get current turn counter."""
        session = self.sessions.get_session(session_id, user_id)
        if not session:
            return 0
        return session.get("turn_counter", 0)

    def append_narration(self, session_id: str, narration: str, max_history: int = 5) -> bool:
        """Append narration to session history."""
        return self.sessions.append_narration(session_id, narration, max_history)

    def get_narration_history(self, session_id: str, user_id: str = "anonymous") -> list[str]:
        """Get narration history for a session."""
        session = self.sessions.get_session(session_id, user_id)
        if not session:
            return []
        return session.get("narration_history", [])

    def mark_departure(
        self,
        session_id: str,
        character_id: str,
        destination: str,
        tick: int,
    ) -> bool:
        """Mark a character as departing (no longer present)."""
        return self.char_states.update_presence(
            session_id, character_id,
            is_present=False,
            intended_destination=destination,
            last_departure_tick=tick,
        )

    def mark_arrival(self, session_id: str, character_id: str) -> bool:
        """Mark a character as arrived (now present)."""
        return self.char_states.update_presence(
            session_id, character_id,
            is_present=True,
            intended_destination=None,
            last_departure_tick=None,
        )

    def save_snapshot(self, session_id: str, user_id: str = "anonymous") -> bool:
        """Save a TurnSnapshot of the current session state for regeneration."""
        session = self.sessions.get_session(session_id, user_id)
        if not session:
            return False

        char_states = self.get_all_character_states(session_id)

        snapshot = TurnSnapshot(
            world_state=WorldState(**session.get("world_state", {})),
            character_states=dict(char_states),
            turn_counter=session.get("turn_counter", 0),
            narration_history=session.get("narration_history", []),
            location_history=session.get("location_history", []),
        )

        return self.sessions.save_snapshot(session_id, snapshot.model_dump())

    def restore_snapshot(self, session_id: str) -> TurnSnapshot | None:
        """Restore from the last saved snapshot. Returns the snapshot if found."""
        raw = self.sessions.get_snapshot(session_id)
        if not raw:
            return None

        snapshot = TurnSnapshot(**raw)

        # Restore session-level state
        self.sessions.update_world_state(session_id, snapshot.world_state.model_dump())

        # Restore character states
        for char_id, char_state in snapshot.character_states.items():
            if isinstance(char_state, dict):
                char_state = CharacterStateData(**char_state)
            self.save_character_state(session_id, char_id, char_state)

        return snapshot

    def _raw_to_character_state(self, raw: dict[str, Any]) -> CharacterStateData:
        emotional = raw.get("emotional_state", {})
        if isinstance(emotional, dict):
            emotional_data = EmotionalStateData(**emotional) if emotional else EmotionalStateData()
        else:
            emotional_data = emotional

        intent_data = None
        if raw.get("active_intent"):
            from src.models.simulation import Intent
            intent_data = Intent(**raw["active_intent"])

        return CharacterStateData(
            drives=raw.get("drives", {}),
            skills=raw.get("skills", {}),
            emotional_state=emotional_data,
            active_intent=intent_data,
            is_present=raw.get("is_present", True),
            intended_destination=raw.get("intended_destination"),
            last_departure_tick=raw.get("last_departure_tick"),
        )
