import tempfile

import pytest

from src.character_creator import CharacterCreator
from src.character_manager import CharacterManager
from src.models.character import Character


class MockPromptProcessor:
    """Mock prompt processor for testing."""

    def __init__(self, mock_character_data: dict):
        self.mock_character_data = mock_character_data

    def respond_with_model(self, prompt: str, user_prompt: str, output_type, **kwargs):
        """Mock response that returns a Character with the mock data."""
        return Character.from_dict(self.mock_character_data)


class TestCharacterCreator:
    def setup_method(self):
        """Setup test with temporary directory and mock prompt processor."""
        self.temp_dir = tempfile.mkdtemp()
        self.character_manager = CharacterManager(self.temp_dir)

        # Complete character data for mock responses
        self.complete_character_data = {
            "name": "Generated Character",
            "tagline": "Adventurer",
            "backstory": "A brave soul seeking adventure",
            "personality": "Courageous and curious",
            "appearance": "Tall with weathered features",
            "relationships": {"mentor": "Old wizard who taught them magic"},
            "key_locations": ["Ancient Library", "Mountain Peak"],
            "setting_description": "A fantasy world of magic and mystery",
        }

        self.mock_prompt_processor = MockPromptProcessor(self.complete_character_data)
        self.character_creator = CharacterCreator(prompt_processor=self.mock_prompt_processor, character_manager=self.character_manager)

    def test_generate_with_empty_input(self):
        """Test generating a character from completely empty input."""
        partial_character = {}

        result = self.character_creator.generate(partial_character)

        assert isinstance(result, Character)
        assert result.name == "Generated Character"
        assert result.tagline == "Adventurer"
        assert result.backstory == "A brave soul seeking adventure"
        assert result.personality == "Courageous and curious"
        assert result.appearance == "Tall with weathered features"
        assert len(result.relationships) > 0
        assert len(result.key_locations) > 0
        assert result.setting_description == "A fantasy world of magic and mystery"

    def test_generate_with_partial_input(self):
        """Test generating a character with some fields already provided."""
        partial_character = {"name": "Existing Hero", "tagline": "Knight", "backstory": "Served the realm for many years"}

        result = self.character_creator.generate(partial_character)

        assert isinstance(result, Character)
        # Existing fields should be preserved
        assert result.name == "Existing Hero"
        assert result.tagline == "Knight"
        assert result.backstory == "Served the realm for many years"
        # Generated fields should be populated
        assert result.personality == "Courageous and curious"
        assert result.appearance == "Tall with weathered features"

    def test_generate_with_complete_input(self):
        """Test that no generation occurs when all fields are provided."""
        complete_character = {
            "name": "Complete Character",
            "tagline": "Mage",
            "backstory": "Studied magic for decades",
            "personality": "Wise and patient",
            "appearance": "Robed figure with a long beard",
            "relationships": {"apprentice": "Young student of magic"},
            "key_locations": ["Tower of Learning"],
            "setting_description": "A world where magic is common",
        }

        # Create a processor that would return different data
        different_data = {**self.complete_character_data, "name": "Should Not Be Used"}
        mock_processor = MockPromptProcessor(different_data)
        creator = CharacterCreator(mock_processor, self.character_manager)

        result = creator.generate(complete_character)

        assert isinstance(result, Character)
        # All original fields should be preserved
        assert result.name == "Complete Character"
        assert result.tagline == "Mage"
        assert result.backstory == "Studied magic for decades"
        assert result.personality == "Wise and patient"
        assert result.appearance == "Robed figure with a long beard"
        assert result.relationships == {"apprentice": "Young student of magic"}
        assert result.key_locations == ["Tower of Learning"]
        assert result.setting_description == "A world where magic is common"

    def test_generate_and_save(self):
        """Test generating and saving a character to file."""
        partial_character = {"name": "Save Test Character"}

        character, filename = self.character_creator.generate_and_save(partial_character)

        assert isinstance(character, Character)
        assert character.name == "Save Test Character"
        assert filename == "save_test_character"

        # Verify file was created
        character_file = self.character_manager.characters_dir / f"{filename}.yaml"
        assert character_file.exists()

    def test_identify_missing_fields(self):
        """Test identification of missing character fields."""
        # Test with some fields present
        partial_data = {
            "name": "Test",
            "tagline": "Warrior",
            "personality": "",  # Empty string should be considered missing
            "relationships": {},  # Empty dict should be considered missing
        }

        missing = self.character_creator._identify_missing_fields(partial_data)

        expected_missing = ["backstory", "personality", "appearance", "relationships", "key_locations", "setting_description"]
        assert set(missing) == set(expected_missing)

    def test_identify_missing_fields_empty_input(self):
        """Test identification of missing fields with empty input."""
        missing = self.character_creator._identify_missing_fields({})

        expected_all_fields = ["name", "tagline", "backstory", "personality", "appearance", "relationships", "key_locations", "setting_description"]
        assert set(missing) == set(expected_all_fields)

    def test_generate_missing_fields(self):
        """Test the internal method for generating missing fields."""
        existing_data = {"name": "Test Character", "tagline": "Fighter"}
        missing_fields = ["backstory", "personality"]

        generated = self.character_creator._generate_missing_fields(existing_data, missing_fields)

        # Should only contain the requested missing fields
        assert "backstory" in generated
        assert "personality" in generated
        # Should not contain fields that weren't requested
        assert "name" not in generated
        assert "tagline" not in generated

    def test_build_user_prompt_with_existing_data(self):
        """Test user prompt building with existing character data."""
        existing_data = {"name": "Test", "tagline": "Mage"}
        missing_fields = ["backstory", "personality"]

        prompt = self.character_creator._build_user_prompt(existing_data, missing_fields)

        assert "Existing character information:" in prompt
        assert "name: Test" in prompt
        assert "tagline: Mage" in prompt
        assert "backstory, personality" in prompt
        assert "consistent with the existing character information" in prompt

    def test_build_user_prompt_no_existing_data(self):
        """Test user prompt building without existing character data."""
        missing_fields = ["name", "tagline", "backstory"]

        prompt = self.character_creator._build_user_prompt({}, missing_fields)

        assert "Existing character information:" not in prompt
        assert "name, tagline, backstory" in prompt
        assert "Create an engaging, original character" in prompt

    def test_validation_error_propagation(self):
        """Test that validation errors are properly propagated."""
        # Create a character creator with invalid mock data
        invalid_data = {"name": "", "tagline": "Test", "backstory": "Test"}  # Empty name
        mock_processor = MockPromptProcessor(invalid_data)
        creator = CharacterCreator(mock_processor, self.character_manager)

        with pytest.raises((ValueError, Exception)):  # Could be ValueError or ValidationError
            creator.generate({})

    def test_default_character_manager(self):
        """Test that CharacterCreator works with default CharacterManager."""
        creator = CharacterCreator(self.mock_prompt_processor)

        # Should not raise an exception
        result = creator.generate({"name": "Default Test"})
        assert isinstance(result, Character)
        assert result.name == "Default Test"
