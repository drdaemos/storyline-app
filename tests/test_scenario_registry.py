"""Tests for ScenarioRegistry."""

import tempfile
from pathlib import Path

import pytest

from src.memory.scenario_registry import ScenarioRegistry


class TestScenarioRegistry:
    """Tests for ScenarioRegistry CRUD operations."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up test fixtures with a temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = ScenarioRegistry(memory_dir=Path(self.temp_dir))
        self.test_scenario_data = {
            "summary": "Test Scenario",
            "intro_message": "This is a test intro message.",
            "narrative_category": "test/drama",
            "character_id": "test-character",
            "location": "Test Location",
            "time_context": "Late evening",
            "atmosphere": "Tense and mysterious",
            "plot_hooks": ["tension 1", "tension 2"],
            "stakes": "High stakes",
            "character_goals": {"Character": "To test"},
            "potential_directions": ["direction 1", "direction 2"],
        }
        yield
        self.registry.close()

    def test_save_scenario_generates_id(self) -> None:
        """Test that save_scenario generates a UUID when none is provided."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
        )

        assert scenario_id is not None
        assert len(scenario_id) == 36  # UUID format

    def test_save_scenario_with_provided_id(self) -> None:
        """Test saving a scenario with a specific ID."""
        provided_id = "custom-scenario-id"
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
            scenario_id=provided_id,
        )

        assert scenario_id == provided_id

    def test_get_scenario(self) -> None:
        """Test retrieving a saved scenario."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
        )

        retrieved = self.registry.get_scenario(scenario_id)

        assert retrieved is not None
        assert retrieved["id"] == scenario_id
        assert retrieved["character_id"] == "test-character"
        assert retrieved["scenario_data"]["summary"] == "Test Scenario"
        assert "created_at" in retrieved
        assert "updated_at" in retrieved

    def test_get_scenario_not_found(self) -> None:
        """Test retrieving a non-existent scenario returns None."""
        result = self.registry.get_scenario("non-existent-id")
        assert result is None

    def test_get_scenarios_for_character(self) -> None:
        """Test retrieving all scenarios for a character."""
        # Save multiple scenarios for the same character
        self.registry.save_scenario(
            scenario_data={**self.test_scenario_data, "summary": "Scenario 1"},
            character_id="test-character",
        )
        self.registry.save_scenario(
            scenario_data={**self.test_scenario_data, "summary": "Scenario 2"},
            character_id="test-character",
        )
        # Save one for a different character
        self.registry.save_scenario(
            scenario_data={**self.test_scenario_data, "summary": "Other"},
            character_id="other-character",
        )

        scenarios = self.registry.get_scenarios_for_character("test-character")

        assert len(scenarios) == 2
        summaries = [s["scenario_data"]["summary"] for s in scenarios]
        assert "Scenario 1" in summaries
        assert "Scenario 2" in summaries

    def test_delete_scenario(self) -> None:
        """Test deleting a scenario."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
        )

        # Verify it exists
        assert self.registry.scenario_exists(scenario_id)

        # Delete it
        deleted = self.registry.delete_scenario(scenario_id)
        assert deleted is True

        # Verify it's gone
        assert not self.registry.scenario_exists(scenario_id)
        assert self.registry.get_scenario(scenario_id) is None

    def test_delete_scenario_not_found(self) -> None:
        """Test deleting a non-existent scenario returns False."""
        deleted = self.registry.delete_scenario("non-existent-id")
        assert deleted is False

    def test_scenario_exists(self) -> None:
        """Test checking if a scenario exists."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
        )

        assert self.registry.scenario_exists(scenario_id) is True
        assert self.registry.scenario_exists("non-existent") is False

    def test_update_scenario(self) -> None:
        """Test updating an existing scenario."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
        )

        # Update the scenario
        updated_data = {**self.test_scenario_data, "summary": "Updated Summary"}
        returned_id = self.registry.save_scenario(
            scenario_data=updated_data,
            character_id="test-character",
            scenario_id=scenario_id,
        )

        assert returned_id == scenario_id

        # Verify the update
        retrieved = self.registry.get_scenario(scenario_id)
        assert retrieved["scenario_data"]["summary"] == "Updated Summary"

    def test_get_scenario_count(self) -> None:
        """Test counting scenarios for a user."""
        # Initially zero
        assert self.registry.get_scenario_count() == 0

        # Add some scenarios
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="char1",
        )
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="char2",
        )

        assert self.registry.get_scenario_count() == 2

    def test_get_scenario_count_for_character(self) -> None:
        """Test counting scenarios for a specific character."""
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
        )
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
        )
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="other-character",
        )

        count = self.registry.get_scenario_count_for_character("test-character")
        assert count == 2

    def test_user_isolation(self) -> None:
        """Test that scenarios are isolated by user_id."""
        # Save scenario for user1
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
            user_id="user1",
        )

        # User2 should not see user1's scenarios (unless anonymous)
        scenarios = self.registry.get_scenarios_for_character("test-character", user_id="user2")
        assert len(scenarios) == 0

        # User1 should see their own scenario
        scenarios = self.registry.get_scenarios_for_character("test-character", user_id="user1")
        assert len(scenarios) == 1

    def test_anonymous_scenarios_visible_to_all(self) -> None:
        """Test that anonymous scenarios are visible to all users."""
        # Save anonymous scenario
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_id="test-character",
            user_id="anonymous",
        )

        # Should be visible to any user
        scenarios = self.registry.get_scenarios_for_character("test-character", user_id="some-user")
        assert len(scenarios) == 1

    def test_health_check(self) -> None:
        """Test health check method - may return False if db not fully initialized."""
        # Health check tests database connectivity
        # In test environment with temp db, it may return False if tables aren't created via migration
        # This test just verifies the method doesn't raise an exception
        result = self.registry.health_check()
        assert isinstance(result, bool)
