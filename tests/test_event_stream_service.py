import tempfile
from pathlib import Path

import pytest

from src.memory.event_repository import EventRepository
from src.models.simulation import Observation, ReflectionResult, RulesetConfig
from src.services.event_stream_service import EventStreamService


def _test_config() -> RulesetConfig:
    return RulesetConfig(
        observation_decay_rate=1.0,
        reflection_decay_rate=0.25,
        observation_initial_decay=3.0,
        reflection_initial_decay=8.0,
        max_event_stream_length=100,
    )


class TestEventStreamService:
    @pytest.fixture(autouse=True)
    def clear_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)

    def test_distribute_observations_public_and_actor_only(self) -> None:
        repo = EventRepository(memory_dir=Path(tempfile.mkdtemp()))
        service = EventStreamService(repo)
        config = _test_config()

        observations = [
            Observation(
                subject="Ren",
                content="Ren slams the table.",
                importance=4,
                visibility="public",
            ),
            Observation(
                subject="Ren",
                content="Ren hides a key in their sleeve.",
                importance=3,
                visibility="actor_only",
                actor="char_a",
            ),
        ]

        distributed = service.distribute_observations(
            session_id="s1",
            observations=observations,
            present_character_ids=["char_a", "char_b"],
            tick=1,
            config=config,
        )

        assert len(distributed["char_a"]) == 2
        assert len(distributed["char_b"]) == 1

        char_b_memory = service.assemble_memory("s1", "char_b", current_tick=1)
        assert "hides a key" not in char_b_memory

        repo.close()

    def test_add_reflection_and_memory_assembly_with_decay(self) -> None:
        repo = EventRepository(memory_dir=Path(tempfile.mkdtemp()))
        service = EventStreamService(repo)
        config = _test_config()

        service.add_observation(
            session_id="s1",
            character_id="char_a",
            tick=0,
            observation=Observation(
                subject="Mara",
                content="Mara says nothing and studies Ren.",
                importance=3,
                visibility="public",
            ),
            config=config,
        )
        service.add_observation(
            session_id="s1",
            character_id="char_a",
            tick=3,
            observation=Observation(
                subject="Mara",
                content="Mara steps into Ren's path.",
                importance=5,
                visibility="public",
            ),
            config=config,
        )

        service.add_reflection(
            session_id="s1",
            character_id="char_a",
            tick=3,
            reflection=ReflectionResult(
                subject=["Mara"],
                content="She's forcing a confrontation.",
                importance=4,
                source_observation_ids=[],
            ),
            config=config,
        )

        memory = service.assemble_memory(
            session_id="s1",
            character_id="char_a",
            current_tick=3,
        )

        assert "steps into Ren's path" in memory
        assert "forcing a confrontation" in memory
        assert "studies Ren" not in memory

        repo.close()

    def test_add_observations_batch(self) -> None:
        repo = EventRepository(memory_dir=Path(tempfile.mkdtemp()))
        service = EventStreamService(repo)
        config = _test_config()

        observations = [
            Observation(subject="Ren", content="Ren shouts.", importance=3, visibility="public"),
            Observation(subject="Mara", content="Mara flinches.", importance=2, visibility="public"),
        ]

        ids = service.add_observations_batch("s1", "char_a", tick=1, observations=observations, config=config)

        assert len(ids) == 2
        events = service.get_recent_events("s1", "char_a", limit=10)
        assert len(events) == 2

        repo.close()

    def test_get_recent_events_returns_event_data(self) -> None:
        repo = EventRepository(memory_dir=Path(tempfile.mkdtemp()))
        service = EventStreamService(repo)
        config = _test_config()

        service.add_observation(
            session_id="s1",
            character_id="char_a",
            tick=0,
            observation=Observation(subject="Ren", content="Ren speaks.", importance=4, visibility="public"),
            config=config,
        )

        events = service.get_recent_events("s1", "char_a", limit=5)
        assert len(events) == 1
        event = events[0]
        assert event.content == "Ren speaks."
        assert event.type == "observation"

        repo.close()

    def test_prune_removes_decayed_and_excess_events(self) -> None:
        repo = EventRepository(memory_dir=Path(tempfile.mkdtemp()))
        service = EventStreamService(repo)
        config = _test_config()

        for tick in range(8):
            service.add_observation(
                session_id="s1",
                character_id="char_a",
                tick=tick,
                observation=Observation(
                    subject="Ren",
                    content=f"Event {tick}",
                    importance=2,
                    visibility="public",
                ),
                config=config,
            )

        pruned = service.prune(
            session_id="s1",
            character_id="char_a",
            current_tick=8,
            max_events=2,
        )

        assert pruned > 0
        remaining = service.get_recent_events("s1", "char_a", limit=20)
        assert len(remaining) <= 2

        repo.close()
