import pytest

from src.models.api_models import Scenario
from src.models.character import Character
from src.scenario_generator import ScenarioGenerator, ScenarioList


class MockPromptProcessor:
    """Mock prompt processor for testing."""

    def __init__(self, mock_scenarios: list[Scenario]):
        self.mock_scenarios = mock_scenarios

    def respond_with_model(self, prompt: str, user_prompt: str, output_type, **kwargs):
        """Mock response that returns a ScenarioList with the mock scenarios."""
        return ScenarioList(scenarios=self.mock_scenarios)

    def get_processor_specific_prompt(self) -> str:
        """Return a mock processor-specific prompt."""
        return "Mock processor guidelines."


class MockChatLogger:
    """Mock chat logger for testing."""

    def log_interaction(self, *args, **kwargs):
        """Mock log method that does nothing."""
        pass

    def log_exception(self, *args, **kwargs):
        """Mock log exception method that does nothing."""
        pass


class TestScenarioGenerator:
    def setup_method(self):
        """Setup test with mock character and prompt processor."""
        self.test_character = Character(
            name="Aria",
            role="Elven Ranger",
            backstory="Protector of the ancient forest",
            personality="Cautious but kind-hearted",
            appearance="Tall elf with silver hair and green eyes",
            relationships={"mentor": "Elder druid of the forest"},
            key_locations=["Whispering Woods", "Crystal Lake"],
            setting_description="A mystical forest realm filled with ancient magic"
        )

        # Mock scenarios
        self.mock_scenarios = [
            Scenario(
                summary="Tracking mysterious footprints in the Whispering Woods",
                intro_message="You find Aria tracking mysterious footprints through the Whispering Woods. "
                             "She gestures for silence as she points to strange markings on the trees. "
                             "The forest seems unusually quiet around you.",
                narrative_category="subtle mystery"
            ),
            Scenario(
                summary="Urgent encounter at Crystal Lake",
                intro_message="Aria emerges from the shadows near Crystal Lake, bow drawn and alert. 'Something's not right here,' she whispers urgently. The water's surface ripples unnaturally.",
                narrative_category="tension and urgency"
            ),
            Scenario(
                summary="Tending to an injured forest creature",
                intro_message="You discover Aria kneeling beside an injured forest creature, her hands glowing "
                             "with soft green light. She looks up with concern as you approach, relief crossing "
                             "her features.",
                narrative_category="conventional"
            )
        ]

        self.mock_prompt_processor = MockPromptProcessor(self.mock_scenarios)
        self.mock_logger = MockChatLogger()
        self.scenario_generator = ScenarioGenerator(
            processors=[self.mock_prompt_processor],
            logger=self.mock_logger
        )

    def test_generate_scenarios_default_count(self):
        """Test generating scenarios with default count (3)."""
        result = self.scenario_generator.generate_scenarios(self.test_character)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(scenario, Scenario) for scenario in result)
        assert result[0].summary == self.mock_scenarios[0].summary

    def test_generate_scenarios_custom_count(self):
        """Test generating scenarios with custom count."""
        # Create mock with 5 scenarios
        mock_scenarios_5 = [
            Scenario(
                summary=f"Scenario {i} summary",
                intro_message=f"This is the intro message for scenario {i} with more details about what's happening.",
                narrative_category=f"category {i}"
            ) for i in range(5)
        ]
        mock_processor = MockPromptProcessor(mock_scenarios_5)
        mock_logger = MockChatLogger()
        generator = ScenarioGenerator(processors=[mock_processor], logger=mock_logger)

        result = generator.generate_scenarios(self.test_character, count=5)

        assert len(result) == 5

    def test_generate_scenarios_count_validation_too_low(self):
        """Test that count < 1 raises ValueError."""
        with pytest.raises(ValueError, match="Scenario count must be between 1 and 10"):
            self.scenario_generator.generate_scenarios(self.test_character, count=0)

    def test_generate_scenarios_count_validation_too_high(self):
        """Test that count > 10 raises ValueError."""
        with pytest.raises(ValueError, match="Scenario count must be between 1 and 10"):
            self.scenario_generator.generate_scenarios(self.test_character, count=11)

    def test_generate_scenarios_empty_response(self):
        """Test that empty scenarios response raises ValueError."""
        empty_processor = MockPromptProcessor([])
        mock_logger = MockChatLogger()
        generator = ScenarioGenerator(processors=[empty_processor], logger=mock_logger)

        with pytest.raises(ValueError, match="Failed to generate scenarios"):
            generator.generate_scenarios(self.test_character)

    def test_generate_scenarios_single_scenario(self):
        """Test generating a single scenario."""
        single_scenario = [Scenario(
            summary="A single scenario",
            intro_message="This is a single scenario intro message with details about the scene.",
            narrative_category="conventional"
        )]
        mock_processor = MockPromptProcessor(single_scenario)
        mock_logger = MockChatLogger()
        generator = ScenarioGenerator(processors=[mock_processor], logger=mock_logger)

        result = generator.generate_scenarios(self.test_character, count=1)

        assert len(result) == 1
        assert result[0].summary == "A single scenario"
        assert "intro message" in result[0].intro_message
        assert result[0].narrative_category == "conventional"

    def test_generate_scenarios_with_minimal_character(self):
        """Test generating scenarios with minimal character data."""
        minimal_character = Character(
            name="Bob",
            role="Merchant",
            backstory="Sells goods"
        )

        result = self.scenario_generator.generate_scenarios(minimal_character)

        assert isinstance(result, list)
        assert len(result) == 3

    def test_build_user_prompt_includes_character_details(self):
        """Test that user prompt includes all character details."""
        prompt = self.scenario_generator._build_user_prompt(self.test_character, 3, 'normal')

        # Verify key character details are in prompt
        assert "Aria" in prompt
        assert "Protector of the ancient forest" in prompt  # backstory
        assert "Cautious but kind-hearted" in prompt
        assert "Tall elf with silver hair" in prompt
        assert "Whispering Woods" in prompt
        assert "Crystal Lake" in prompt
        assert "mystical forest realm" in prompt
        assert "exactly 3" in prompt

    def test_build_user_prompt_with_minimal_character(self):
        """Test user prompt with character having minimal fields."""
        minimal_character = Character(
            name="Test",
            role="Role",
            backstory="Story"
        )

        prompt = self.scenario_generator._build_user_prompt(minimal_character, 2, 'normal')

        # Should still include basic fields
        assert "Test" in prompt
        assert "Story" in prompt  # backstory
        assert "exactly 2" in prompt

    def test_scenario_structure(self):
        """Test that scenario objects have all required fields."""
        result = self.scenario_generator.generate_scenarios(self.test_character)

        for scenario in result:
            # Check all fields are present
            assert isinstance(scenario.summary, str)
            assert len(scenario.summary) > 0
            assert isinstance(scenario.intro_message, str)
            assert len(scenario.intro_message) > 0
            assert isinstance(scenario.narrative_category, str)
            assert 1 <= len(scenario.narrative_category) <= 50  # Based on the Field definition
