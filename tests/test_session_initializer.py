import tempfile
from pathlib import Path

import pytest

from src.character_loader import CharacterLoader
from src.memory.character_registry import CharacterRegistry
from src.memory.character_state_repository import CharacterStateRepository
from src.memory.conversation_memory import ConversationMemory
from src.memory.event_repository import EventRepository
from src.memory.ruleset_registry import RulesetRegistry
from src.memory.scenario_registry import ScenarioRegistry
from src.memory.session_repository import SessionRepository
from src.memory.world_lore_registry import WorldLoreRegistry
from src.pipeline.session_initializer import SessionInitializer
from src.services.event_stream_service import EventStreamService
from src.services.ruleset_service import RulesetService
from src.services.session_state_service import SessionStateService


class TestSessionInitializer:
    @pytest.fixture(autouse=True)
    def setup_db(self, monkeypatch: pytest.MonkeyPatch) -> None:
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_session_initializer.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    def test_initialize_session_from_scenario(self) -> None:
        ruleset_registry = RulesetRegistry()
        scenario_registry = ScenarioRegistry()
        conversation_memory = ConversationMemory()
        world_lore_registry = WorldLoreRegistry()
        character_registry = CharacterRegistry()

        session_repository = SessionRepository()
        character_state_repository = CharacterStateRepository()
        event_repository = EventRepository()

        session_state_service = SessionStateService(session_repository, character_state_repository)
        ruleset_service = RulesetService(ruleset_registry)
        event_stream_service = EventStreamService(event_repository)
        character_loader = CharacterLoader()

        character_registry.save_character(
            "ren",
            {
                "name": "Ren",
                "tagline": "Investigator",
                "backstory": "Chases difficult truths.",
                "personality": "Focused and blunt.",
                "appearance": "Dark coat and tired eyes.",
                "starting_drives": {"energy": 7},
                "starting_skills": {"persuasion": 6},
                "starting_emotional_state": {"global_state": {"composure": 6}},
            },
        )
        character_registry.save_character(
            "persona",
            {
                "name": "You",
                "tagline": "Witness",
                "backstory": "Caught in the middle.",
                "personality": "Careful and observant.",
                "appearance": "Nervous posture.",
                "starting_drives": {"energy": 5},
            },
            is_persona=True,
        )

        ruleset_id = ruleset_registry.save_ruleset(
            name="Core",
            rules_text="Use checks only on uncertainty.",
            state_schemas={
                "drives": [{"name": "energy", "range_min": 0, "range_max": 10, "default": 5, "decay_rate": 1.0}],
                "skills": [{"name": "persuasion", "range_min": 0, "range_max": 20}],
                "emotional_state": {"global_dims": [{"name": "composure", "range_min": 0, "range_max": 10, "default": 5}], "per_relationship": []},
            },
            config={},
        )

        scenario_id = scenario_registry.save_scenario(
            scenario_data={
                "summary": "Opening",
                "intro_message": "Rain needles the alley as Ren arrives.",
                "ruleset_id": ruleset_id,
                "character_ids": ["ren"],
                "persona_id": "persona",
                "location": "Alley",
                "time_context": "22:00",
                "character_goals": {"ren": "Find who dropped the ledger."},
            },
            ruleset_id=ruleset_id,
            character_ids=["ren"],
        )

        initializer = SessionInitializer(
            session_state_service=session_state_service,
            ruleset_service=ruleset_service,
            event_stream_service=event_stream_service,
            character_loader=character_loader,
            scenario_registry=scenario_registry,
            conversation_memory=conversation_memory,
            world_lore_registry=world_lore_registry,
        )

        result = initializer.initialize(scenario_id=scenario_id, user_id="anonymous")

        assert result["session_id"]
        assert result["world_state"]["location"] == "Alley"
        assert result["character_ids"] == ["ren"]
        assert result["persona_id"] == "persona"
        assert "Rain needles" in result["intro"]

        ren_state = session_state_service.get_character_state(result["session_id"], "ren")
        assert ren_state is not None
        assert ren_state.drives["energy"] == 7
        assert ren_state.active_intent is not None
        assert "Find who dropped the ledger." in ren_state.active_intent.goal

        persona_state = session_state_service.get_character_state(result["session_id"], "persona")
        assert persona_state is not None
        assert persona_state.drives["energy"] == 5

        messages = conversation_memory.get_session_messages(result["session_id"], "anonymous")
        assert len(messages) == 1
        assert messages[0]["role"] == "narration"

        ruleset_registry.close()
        scenario_registry.close()
        conversation_memory.close()
        world_lore_registry.close()
        character_registry.close()
        character_loader.registry.close()
        session_repository.close()
        character_state_repository.close()
        event_repository.close()

    def test_initialize_raises_for_missing_ruleset(self) -> None:
        """Test that session initialization fails when the scenario has no ruleset."""
        ruleset_registry = RulesetRegistry()
        scenario_registry = ScenarioRegistry()
        conversation_memory = ConversationMemory()
        world_lore_registry = WorldLoreRegistry()

        session_repository = SessionRepository()
        character_state_repository = CharacterStateRepository()
        event_repository = EventRepository()

        session_state_service = SessionStateService(session_repository, character_state_repository)
        ruleset_service = RulesetService(ruleset_registry)
        event_stream_service = EventStreamService(event_repository)
        character_loader = CharacterLoader()

        # Create a scenario without a ruleset by inserting directly into DB
        # (save_scenario now requires ruleset_id, so we need a valid one)
        ruleset_id = ruleset_registry.save_ruleset(
            name="Minimal",
            rules_text="Basic rules.",
            state_schemas={"drives": [], "skills": [], "emotional_state": {}},
            config={},
        )

        # Scenario references a non-existent ruleset
        scenario_id = scenario_registry.save_scenario(
            scenario_data={
                "summary": "Gate Encounter",
                "intro_message": "A guard blocks the path.",
                "character_ids": ["guard"],
                "location": "Gate",
                "time_context": "Dawn",
                "ruleset_id": "nonexistent-ruleset",
            },
            ruleset_id=ruleset_id,  # DB-level reference is valid
            character_ids=["guard"],
        )

        initializer = SessionInitializer(
            session_state_service=session_state_service,
            ruleset_service=ruleset_service,
            event_stream_service=event_stream_service,
            character_loader=character_loader,
            scenario_registry=scenario_registry,
            conversation_memory=conversation_memory,
            world_lore_registry=world_lore_registry,
        )

        with pytest.raises(ValueError, match="not found"):
            initializer.initialize(scenario_id=scenario_id, user_id="anonymous")

        ruleset_registry.close()
        scenario_registry.close()
        conversation_memory.close()
        world_lore_registry.close()
        character_loader.registry.close()
        session_repository.close()
        character_state_repository.close()
        event_repository.close()

    def test_initialize_raises_for_missing_scenario(self) -> None:
        session_repo = SessionRepository()
        character_state_repo = CharacterStateRepository()
        ruleset_registry = RulesetRegistry()
        event_repo = EventRepository()
        scenario_registry = ScenarioRegistry()
        conversation_memory = ConversationMemory()
        lore_registry = WorldLoreRegistry()
        character_loader = CharacterLoader()

        initializer = SessionInitializer(
            session_state_service=SessionStateService(session_repo, character_state_repo),
            ruleset_service=RulesetService(ruleset_registry),
            event_stream_service=EventStreamService(event_repo),
            character_loader=character_loader,
            scenario_registry=scenario_registry,
            conversation_memory=conversation_memory,
            world_lore_registry=lore_registry,
        )

        with pytest.raises(ValueError, match="not found"):
            initializer.initialize("missing-scenario")

        session_repo.close()
        character_state_repo.close()
        ruleset_registry.close()
        event_repo.close()
        scenario_registry.close()
        conversation_memory.close()
        lore_registry.close()
        character_loader.registry.close()
