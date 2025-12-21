"""Tests for scenario integration with summary system."""

import pytest

from src.character_loader import CharacterLoader
from src.memory.conversation_memory import ConversationMemory
from src.memory.scenario_registry import ScenarioRegistry
from src.memory.summary_memory import SummaryMemory
from src.models.character import Character
from src.scenario_to_summary import create_initial_summary_from_scenario
from src.session_starter import SessionStarter


@pytest.fixture
def sample_scenario_data() -> dict:
    """Create sample scenario data for testing."""
    return {
        "summary": "The Midnight Encounter",
        "intro_message": "The clock strikes midnight as shadows dance across the room...",
        "narrative_category": "mystery/thriller",
        "character_id": "test-character",
        "plot_hooks": [
            "Trust is fragile between them",
            "A secret threatens to surface",
            "Time is running out",
        ],
        "stakes": "Their relationship hangs in the balance",
        "character_goals": {
            "Alice": "Find the truth",
            "Bob": "Hide the secret",
        },
        "atmosphere": "Tense, with underlying fear",
        "time_context": "Day 1, late evening",
        "location": "Dimly lit apartment",
    }


class TestScenarioToSummary:
    """Tests for scenario to summary conversion."""

    def test_create_initial_summary_basic(self, sample_scenario_data: dict) -> None:
        """Test creating initial summary from scenario data."""
        summary = create_initial_summary_from_scenario(
            scenario_data=sample_scenario_data,
            character_name="Alice",
            persona_name="User",
        )

        # Check time mapping
        assert summary.time.current_time == "Day 1, late evening"

        # Check plot tracking
        assert summary.plot.location == "Dimly lit apartment"
        assert len(summary.plot.ongoing_plots) == 3
        assert "Trust is fragile" in summary.plot.ongoing_plots[0]

        # Check story beats include stakes
        assert any("relationship hangs in the balance" in beat.lower() for beat in summary.story_beats)

        # Check character goals preserved
        assert summary.character_goals == {"Alice": "Find the truth", "Bob": "Hide the secret"}

    def test_character_goals_mapped_to_emotional_state(self, sample_scenario_data: dict) -> None:
        """Test that character goals are transformed into emotional states."""
        summary = create_initial_summary_from_scenario(
            scenario_data=sample_scenario_data,
            character_name="Alice",
            persona_name="User",
        )

        # Should have Alice's emotional state
        alice_state = next((s for s in summary.emotional_state if s.character_name == "Alice"), None)
        assert alice_state is not None
        assert alice_state.character_wants is not None
        assert "find the truth" in alice_state.character_wants.lower()

    def test_atmosphere_influences_emotional_state(self, sample_scenario_data: dict) -> None:
        """Test that atmosphere is used in emotional state."""
        summary = create_initial_summary_from_scenario(
            scenario_data=sample_scenario_data,
            character_name="Alice",
            persona_name="User",
        )

        alice_state = next((s for s in summary.emotional_state if s.character_name == "Alice"), None)
        assert alice_state is not None
        assert "tense" in alice_state.character_emotions.lower() or "fear" in alice_state.character_emotions.lower()

    def test_handles_missing_optional_fields(self) -> None:
        """Test that summary creation works with minimal scenario data."""
        minimal_scenario = {
            "intro_message": "Hello world",
            "character_id": "test-char",
        }

        summary = create_initial_summary_from_scenario(
            scenario_data=minimal_scenario,
            character_name="TestChar",
            persona_name="User",
        )

        assert summary.time.current_time == "Day 1, beginning"
        assert summary.plot.location == "Unknown location"
        assert len(summary.plot.ongoing_plots) == 0
        assert len(summary.character_goals) == 0


class TestSessionStarterWithScenario:
    """Tests for SessionStarter integration with scenarios."""

    @pytest.fixture
    def character_loader_with_test_char(self) -> CharacterLoader:
        """Create a character loader with a test character in database."""
        from src.memory.character_registry import CharacterRegistry

        loader = CharacterLoader()

        # Create test character in database
        test_char = Character(
            name="TestChar",
            tagline="A test character",
            backstory="For testing purposes",
        )

        registry = CharacterRegistry()
        registry.save_character(
            character_id="testchar",
            character_data=test_char.model_dump(),
            user_id="test-user",
        )

        return loader

    def test_start_session_with_scenario_creates_summary(
        self,
        character_loader_with_test_char: CharacterLoader,
        sample_scenario_data: dict,
    ) -> None:
        """Test that starting a session with a scenario creates an initial summary."""
        conversation_memory = ConversationMemory()
        scenario_registry = ScenarioRegistry()
        summary_memory = SummaryMemory()

        # Save the scenario
        scenario_id = scenario_registry.save_scenario(
            scenario_data=sample_scenario_data,
            character_id="testchar",
            user_id="test-user",
        )

        # Create session starter
        session_starter = SessionStarter(
            character_loader=character_loader_with_test_char,
            conversation_memory=conversation_memory,
            scenario_registry=scenario_registry,
            summary_memory=summary_memory,
        )

        # Start session with scenario
        session_id = session_starter.start_session_with_scenario_id(
            character_name="testchar",
            scenario_id=scenario_id,
            user_id="test-user",
        )

        # Verify summary was created
        summaries = summary_memory.get_session_summaries(session_id, "test-user")
        assert len(summaries) == 1

        # Verify summary has scenario data
        import json
        summary_dict = json.loads(summaries[0]["summary"])
        assert summary_dict["time"]["current_time"] == "Day 1, late evening"
        assert summary_dict["plot"]["location"] == "Dimly lit apartment"
        assert len(summary_dict["plot"]["ongoing_plots"]) == 3
        assert summary_dict["character_goals"] == {"Alice": "Find the truth", "Bob": "Hide the secret"}

    def test_summary_created_before_intro_message(
        self,
        character_loader_with_test_char: CharacterLoader,
        sample_scenario_data: dict,
    ) -> None:
        """Test that summary is created at offset 0, before the intro message."""
        conversation_memory = ConversationMemory()
        scenario_registry = ScenarioRegistry()
        summary_memory = SummaryMemory()

        # Save the scenario
        scenario_id = scenario_registry.save_scenario(
            scenario_data=sample_scenario_data,
            character_id="testchar",
            user_id="test-user",
        )

        # Create session starter
        session_starter = SessionStarter(
            character_loader=character_loader_with_test_char,
            conversation_memory=conversation_memory,
            scenario_registry=scenario_registry,
            summary_memory=summary_memory,
        )

        # Start session with scenario
        session_id = session_starter.start_session_with_scenario_id(
            character_name="testchar",
            scenario_id=scenario_id,
            user_id="test-user",
        )

        # Verify summary offsets
        summaries = summary_memory.get_session_summaries(session_id, "test-user")
        assert len(summaries) == 1
        assert summaries[0]["start_offset"] == 0
        assert summaries[0]["end_offset"] == 0

        # Verify intro message exists after summary
        messages = conversation_memory.get_recent_messages(session_id, "test-user", limit=10)
        assert len(messages) == 1
        assert messages[0]["content"] == sample_scenario_data["intro_message"]
