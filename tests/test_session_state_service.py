import tempfile
from pathlib import Path

import pytest

from src.memory.character_state_repository import CharacterStateRepository
from src.memory.session_repository import SessionRepository
from src.models.simulation import CharacterStateData, EmotionalStateData, Intent, SuccessCondition, WorldState
from src.services.session_state_service import SessionStateService


def _create_service() -> tuple[SessionStateService, SessionRepository, CharacterStateRepository, str]:
    temp_dir = Path(tempfile.mkdtemp())
    session_repo = SessionRepository(memory_dir=temp_dir)
    state_repo = CharacterStateRepository(memory_dir=temp_dir)
    service = SessionStateService(session_repo, state_repo)
    session_id = session_repo.create_session(
        scenario_id="scenario-1",
        world_state={"location": "Bar", "time": "22:00", "characters_present": ["npc-1"]},
        user_id="anonymous",
    )
    return service, session_repo, state_repo, session_id


class TestSessionStateService:
    @pytest.fixture(autouse=True)
    def clear_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)

    def test_world_state_management(self) -> None:
        service, session_repo, state_repo, session_id = _create_service()

        world = service.get_world_state(session_id)
        assert world is not None
        assert world.location == "Bar"

        updated = service.update_world_state(
            session_id,
            WorldState(location="Alley", time="22:10", characters_present=["npc-1", "npc-2"]),
        )
        assert updated is True

        world_after = service.get_world_state(session_id)
        assert world_after is not None
        assert world_after.location == "Alley"
        assert world_after.characters_present == ["npc-1", "npc-2"]

        session_repo.close()
        state_repo.close()

    def test_character_presence_and_departure_arrival(self) -> None:
        service, session_repo, state_repo, session_id = _create_service()

        state = CharacterStateData(
            drives={"energy": 5},
            skills={"stealth": 3},
            emotional_state=EmotionalStateData(global_state={"composure": 5}),
            active_intent=Intent(
                goal="Leave unnoticed",
                success_condition=SuccessCondition(type="narrative", description="Is outside"),
                source_refs=["obs-1"],
            ),
        )
        service.save_character_state(session_id, "npc-1", state)

        present = service.get_present_character_ids(session_id)
        assert "npc-1" in present

        service.mark_departure(session_id, "npc-1", destination="Street", tick=3)
        present_after_departure = service.get_present_character_ids(session_id)
        assert "npc-1" not in present_after_departure

        service.mark_arrival(session_id, "npc-1")
        present_after_arrival = service.get_present_character_ids(session_id)
        assert "npc-1" in present_after_arrival

        session_repo.close()
        state_repo.close()

    def test_get_all_character_states(self) -> None:
        service, session_repo, state_repo, session_id = _create_service()

        service.save_character_state(
            session_id,
            "npc-1",
            CharacterStateData(
                drives={"energy": 7},
                skills={"stealth": 3},
                emotional_state=EmotionalStateData(global_state={"composure": 5}),
            ),
        )
        service.save_character_state(
            session_id,
            "npc-2",
            CharacterStateData(
                drives={"energy": 4},
                skills={},
                emotional_state=EmotionalStateData(global_state={"composure": 8}),
            ),
        )

        all_states = service.get_all_character_states(session_id)
        assert "npc-1" in all_states
        assert "npc-2" in all_states
        assert all_states["npc-1"].drives["energy"] == 7
        assert all_states["npc-2"].drives["energy"] == 4

        session_repo.close()
        state_repo.close()

    def test_append_and_get_narration_history(self) -> None:
        service, session_repo, state_repo, session_id = _create_service()

        service.append_narration(session_id, "First narration")
        service.append_narration(session_id, "Second narration")

        history = service.get_narration_history(session_id, "anonymous")
        assert len(history) == 2
        assert history[0] == "First narration"
        assert history[1] == "Second narration"

        session_repo.close()
        state_repo.close()

    def test_snapshot_roundtrip_and_turn_counter(self) -> None:
        service, session_repo, state_repo, session_id = _create_service()

        service.save_character_state(
            session_id,
            "npc-1",
            CharacterStateData(
                drives={"energy": 8},
                skills={"persuasion": 6},
                emotional_state=EmotionalStateData(global_state={"composure": 6}),
            ),
        )
        service.append_narration(session_id, "Initial narration")
        assert service.get_turn_counter(session_id) == 0
        assert service.increment_turn(session_id) == 1

        saved = service.save_snapshot(session_id)
        assert saved is True

        # Mutate state and world, then restore from snapshot
        service.update_world_state(
            session_id,
            WorldState(location="Docks", time="23:00", characters_present=[]),
        )
        service.save_character_state(
            session_id,
            "npc-1",
            CharacterStateData(
                drives={"energy": 1},
                skills={"persuasion": 1},
                emotional_state=EmotionalStateData(global_state={"composure": 1}),
            ),
        )

        snapshot = service.restore_snapshot(session_id)
        assert snapshot is not None
        restored_world = service.get_world_state(session_id)
        restored_state = service.get_character_state(session_id, "npc-1")
        assert restored_world is not None
        assert restored_world.location == "Bar"
        assert restored_state is not None
        assert restored_state.drives["energy"] == 8

        session_repo.close()
        state_repo.close()
