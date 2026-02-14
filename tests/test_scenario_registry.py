"""Tests for ScenarioRegistry."""

import os
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
        # Clear DATABASE_URL so ScenarioRegistry uses memory_dir, not a leaked env var
        self._original_db_url = os.environ.pop("DATABASE_URL", None)
        self.registry = ScenarioRegistry(memory_dir=Path(self.temp_dir))
        self.test_ruleset_id = "test-ruleset-1"
        self.test_scenario_data = {
            "summary": "Test Scenario",
            "intro_message": "This is a test intro message.",
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
        # Restore DATABASE_URL if it was set
        if self._original_db_url is not None:
            os.environ["DATABASE_URL"] = self._original_db_url

    def test_save_scenario_generates_id(self) -> None:
        """Test that save_scenario generates a UUID when none is provided."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
        )

        assert scenario_id is not None
        assert len(scenario_id) == 36  # UUID format

    def test_save_scenario_with_provided_id(self) -> None:
        """Test saving a scenario with a specific ID."""
        provided_id = "custom-scenario-id"
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
            scenario_id=provided_id,
        )

        assert scenario_id == provided_id

    def test_get_scenario(self) -> None:
        """Test retrieving a saved scenario."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
        )

        retrieved = self.registry.get_scenario(scenario_id)

        assert retrieved is not None
        assert retrieved["id"] == scenario_id
        assert retrieved["character_ids"] == ["test-character"]
        assert retrieved["scenario_data"]["summary"] == "Test Scenario"
        assert "created_at" in retrieved
        assert "updated_at" in retrieved

    def test_get_scenario_not_found(self) -> None:
        """Test retrieving a non-existent scenario returns None."""
        result = self.registry.get_scenario("non-existent-id")
        assert result is None

    def test_get_all_scenarios(self) -> None:
        """Test retrieving all scenarios for a user."""
        self.registry.save_scenario(
            scenario_data={**self.test_scenario_data, "summary": "Scenario 1"},
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
        )
        self.registry.save_scenario(
            scenario_data={**self.test_scenario_data, "summary": "Scenario 2"},
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
        )
        self.registry.save_scenario(
            scenario_data={**self.test_scenario_data, "summary": "Other"},
            character_ids=["other-character"],
            ruleset_id=self.test_ruleset_id,
        )

        scenarios = self.registry.get_all_scenarios()

        assert len(scenarios) == 3
        summaries = [s["scenario_data"]["summary"] for s in scenarios]
        assert "Scenario 1" in summaries
        assert "Scenario 2" in summaries
        assert "Other" in summaries

    def test_delete_scenario(self) -> None:
        """Test deleting a scenario."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
        )

        assert self.registry.scenario_exists(scenario_id)

        deleted = self.registry.delete_scenario(scenario_id)
        assert deleted is True

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
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
        )

        assert self.registry.scenario_exists(scenario_id) is True
        assert self.registry.scenario_exists("non-existent") is False

    def test_update_scenario(self) -> None:
        """Test updating an existing scenario."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
        )

        updated_data = {**self.test_scenario_data, "summary": "Updated Summary"}
        returned_id = self.registry.save_scenario(
            scenario_data=updated_data,
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
            scenario_id=scenario_id,
        )

        assert returned_id == scenario_id

        retrieved = self.registry.get_scenario(scenario_id)
        assert retrieved["scenario_data"]["summary"] == "Updated Summary"

    def test_get_scenario_count(self) -> None:
        """Test counting scenarios for a user."""
        assert self.registry.get_scenario_count() == 0

        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["char1"],
            ruleset_id=self.test_ruleset_id,
        )
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["char2"],
            ruleset_id=self.test_ruleset_id,
        )

        assert self.registry.get_scenario_count() == 2

    def test_multiple_character_ids(self) -> None:
        """Test saving a scenario with multiple character IDs."""
        scenario_id = self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["char-1", "char-2", "char-3"],
            ruleset_id=self.test_ruleset_id,
        )

        retrieved = self.registry.get_scenario(scenario_id)
        assert retrieved["character_ids"] == ["char-1", "char-2", "char-3"]

    def test_user_isolation(self) -> None:
        """Test that scenarios are isolated by user_id."""
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
            user_id="user1",
        )

        # User2 should not see user1's scenarios
        scenarios = self.registry.get_all_scenarios(user_id="user2")
        assert len(scenarios) == 0

        # User1 should see their own scenario
        scenarios = self.registry.get_all_scenarios(user_id="user1")
        assert len(scenarios) == 1

    def test_anonymous_scenarios_visible_to_all(self) -> None:
        """Test that anonymous scenarios are visible to all users."""
        self.registry.save_scenario(
            scenario_data=self.test_scenario_data,
            character_ids=["test-character"],
            ruleset_id=self.test_ruleset_id,
            user_id="anonymous",
        )

        # Should be visible to any user
        scenarios = self.registry.get_all_scenarios(user_id="some-user")
        assert len(scenarios) == 1

    def test_save_scenario_requires_ruleset_id(self) -> None:
        """Test that save_scenario raises ValueError without ruleset_id."""
        with pytest.raises(ValueError, match="ruleset_id"):
            self.registry.save_scenario(
                scenario_data=self.test_scenario_data,
                character_ids=["test-character"],
            )

        with pytest.raises(ValueError, match="ruleset_id"):
            self.registry.save_scenario(
                scenario_data=self.test_scenario_data,
                character_ids=["test-character"],
                ruleset_id="",
            )

    def test_health_check(self) -> None:
        """Test health check method."""
        result = self.registry.health_check()
        assert isinstance(result, bool)
