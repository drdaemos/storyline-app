"""Service for managing event streams (observations and reflections)."""

import uuid
from typing import Any

from src.memory.event_repository import EventRepository
from src.models.simulation import (
    EventData,
    Observation,
    ReflectionResult,
    RulesetConfig,
)


class EventStreamService:
    """Manages observation/reflection lifecycle and memory assembly for prompts."""

    def __init__(self, event_repository: EventRepository) -> None:
        self.repository = event_repository

    def add_observation(
        self,
        session_id: str,
        character_id: str,
        tick: int,
        observation: Observation,
        config: RulesetConfig,
    ) -> str:
        """Add an observation to a character's event stream.

        Returns the generated event ID.
        """
        event_id = f"obs-{uuid.uuid4().hex[:8]}"

        # Determine visibility
        visibility = observation.visibility if observation.visibility else None

        return self.repository.add_event(
            event_id=event_id,
            session_id=session_id,
            character_id=character_id,
            event_type="observation",
            tick=tick,
            subject=[observation.subject],
            content=observation.content,
            importance=observation.importance,
            decay_rate=config.observation_decay_rate,
            initial_decay=config.observation_initial_decay,
            visibility=visibility,
        )

    def add_observations_batch(
        self,
        session_id: str,
        character_id: str,
        tick: int,
        observations: list[Observation],
        config: RulesetConfig,
    ) -> list[str]:
        """Add multiple observations and return their IDs."""
        ids: list[str] = []
        for obs in observations:
            event_id = self.add_observation(session_id, character_id, tick, obs, config)
            ids.append(event_id)
        return ids

    def distribute_observations(
        self,
        session_id: str,
        observations: list[Observation],
        present_character_ids: list[str],
        tick: int,
        config: RulesetConfig,
    ) -> dict[str, list[str]]:
        """Distribute observations to all present characters based on visibility.

        Public observations go to all present characters.
        Actor-only observations go only to the specified actor.

        Returns a mapping of character_id -> list of created event IDs.
        """
        result: dict[str, list[str]] = {cid: [] for cid in present_character_ids}

        for obs in observations:
            if obs.visibility == "actor_only" and obs.actor:
                # Only the actor sees this
                if obs.actor in result:
                    event_id = self.add_observation(
                        session_id, obs.actor, tick, obs, config
                    )
                    result[obs.actor].append(event_id)
            else:
                # Public — all present characters
                for cid in present_character_ids:
                    event_id = self.add_observation(
                        session_id, cid, tick, obs, config
                    )
                    result[cid].append(event_id)

        return result

    def add_reflection(
        self,
        session_id: str,
        character_id: str,
        tick: int,
        reflection: ReflectionResult,
        config: RulesetConfig,
        source_observation_ids: list[str] | None = None,
    ) -> str:
        """Add a reflection to a character's event stream.

        Returns the generated event ID.
        """
        event_id = f"ref-{uuid.uuid4().hex[:8]}"

        return self.repository.add_event(
            event_id=event_id,
            session_id=session_id,
            character_id=character_id,
            event_type="reflection",
            tick=tick,
            subject=reflection.subject,
            content=reflection.content,
            importance=reflection.importance,
            decay_rate=config.reflection_decay_rate,
            initial_decay=config.reflection_initial_decay,
            source_refs=source_observation_ids or reflection.source_observation_ids,
        )

    def assemble_memory(
        self,
        session_id: str,
        character_id: str,
        current_tick: int,
        subject_filter: list[str] | None = None,
        limit: int = 10,
    ) -> str:
        """Assemble memory context for prompts. Delegates to repository."""
        return self.repository.assemble_memory(
            session_id=session_id,
            character_id=character_id,
            current_tick=current_tick,
            subject_filter=subject_filter,
            limit=limit,
        )

    def get_recent_events(
        self,
        session_id: str,
        character_id: str,
        limit: int = 10,
    ) -> list[EventData]:
        """Get recent events as domain models."""
        raw = self.repository.get_events(session_id, character_id, limit=limit)
        return [self._to_event_data(e) for e in raw]

    def prune(
        self,
        session_id: str,
        character_id: str,
        current_tick: int,
        max_events: int = 100,
    ) -> int:
        """Prune decayed events. Returns count pruned."""
        return self.repository.prune_decayed_events(
            session_id, character_id, current_tick, max_events
        )

    def _to_event_data(self, raw: dict[str, Any]) -> EventData:
        return EventData(
            id=raw["id"],
            session_id=raw["session_id"],
            character_id=raw["character_id"],
            type=raw["type"],
            tick=raw["tick"],
            subject=raw.get("subject", []),
            content=raw.get("content", ""),
            importance=raw.get("importance", 2),
            decay_rate=raw.get("decay_rate", 0.3),
            initial_decay=raw.get("initial_decay", 10.0),
            source_refs=raw.get("source_refs", []),
            visibility=raw.get("visibility"),
        )
