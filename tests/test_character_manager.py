import tempfile
from pathlib import Path

import pytest
import yaml

from src.character_manager import CharacterManager


class TestCharacterManager:
    def setup_method(self):
        """Setup test with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.character_manager = CharacterManager(self.temp_dir)

    def test_validate_character_data_valid(self):
        """Test validation with valid character data."""
        valid_data = {
            "name": "Test Character",
            "role": "Test Role",
            "backstory": "Test backstory",
            "personality": "Test personality",
            "appearance": "Test appearance",
            "setting_description": "Test setting",
            "relationships": {"user": "Test relationship"},
            "key_locations": ["Location 1", "Location 2"]
        }

        # Should not raise any exception
        self.character_manager.validate_character_data(valid_data)

    def test_validate_character_data_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        invalid_data = {
            "name": "Test Character",
            "role": "Test Role"
            # Missing backstory
        }

        with pytest.raises(ValueError, match="Missing required fields: {'backstory'}"):
            self.character_manager.validate_character_data(invalid_data)

    def test_validate_character_data_empty_required_fields(self):
        """Test validation fails when required fields are empty."""
        invalid_data = {
            "name": "",
            "role": "Test Role",
            "backstory": "Test backstory"
        }

        with pytest.raises(ValueError, match="'name' must be a non-empty string"):
            self.character_manager.validate_character_data(invalid_data)

    def test_validate_character_data_wrong_types(self):
        """Test validation fails with wrong field types."""
        invalid_data = {
            "name": "Test Character",
            "role": "Test Role",
            "backstory": "Test backstory",
            "relationships": "not a dict"
        }

        with pytest.raises(ValueError, match="'relationships' must be a dictionary"):
            self.character_manager.validate_character_data(invalid_data)

    def test_validate_yaml_text_valid(self):
        """Test YAML text validation with valid input."""
        yaml_text = """
name: Test Character
role: Test Role
backstory: Test backstory
personality: Test personality
"""

        result = self.character_manager.validate_yaml_text(yaml_text)
        assert result["name"] == "Test Character"
        assert result["role"] == "Test Role"
        assert result["backstory"] == "Test backstory"
        assert result["personality"] == "Test personality"

    def test_validate_yaml_text_invalid_yaml(self):
        """Test YAML text validation with invalid YAML syntax."""
        invalid_yaml = """
name: Test Character
role: Test Role
backstory: [unclosed bracket
"""

        with pytest.raises(ValueError, match="Invalid YAML format"):
            self.character_manager.validate_yaml_text(invalid_yaml)

    def test_validate_yaml_text_empty(self):
        """Test YAML text validation with empty content."""
        with pytest.raises(ValueError, match="YAML text cannot be empty"):
            self.character_manager.validate_yaml_text("")

    def test_create_character_file_success(self):
        """Test successful character file creation."""
        character_data = {
            "name": "Test Character",
            "role": "Test Role",
            "backstory": "Test backstory",
            "personality": "Test personality"
        }

        filename = self.character_manager.create_character_file(character_data)

        # Check that file was created
        character_file = Path(self.temp_dir) / f"{filename}.yaml"
        assert character_file.exists()

        # Check file contents
        with open(character_file) as f:
            saved_data = yaml.safe_load(f)

        assert saved_data["name"] == "Test Character"
        assert saved_data["role"] == "Test Role"
        assert saved_data["backstory"] == "Test backstory"
        assert saved_data["personality"] == "Test personality"

    def test_create_character_file_already_exists(self):
        """Test character file creation when file already exists."""
        character_data = {
            "name": "Test Character",
            "role": "Test Role",
            "backstory": "Test backstory"
        }

        # Create character first time
        self.character_manager.create_character_file(character_data)

        # Try to create again - should fail
        with pytest.raises(FileExistsError, match="Character 'Test Character' already exists"):
            self.character_manager.create_character_file(character_data)

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Test normal name
        assert self.character_manager._sanitize_filename("Test Character") == "test_character"

        # Test with special characters
        assert self.character_manager._sanitize_filename("Test-Character@123!") == "test-character_123"

        # Test with multiple spaces/underscores
        assert self.character_manager._sanitize_filename("Test   Character___Name") == "test_character_name"

        # Test empty result
        with pytest.raises(ValueError, match="Character name produces empty filename"):
            self.character_manager._sanitize_filename("!@#$%^&*()")

    def test_filename_collision_detection_same_character(self):
        """Test that creating the same character twice raises FileExistsError."""
        character_data = {
            "name": "Test Character",
            "role": "Test Role",
            "backstory": "Test backstory"
        }

        # Create character first time
        self.character_manager.create_character_file(character_data)

        # Try to create the same character again
        with pytest.raises(FileExistsError, match="Character 'Test Character' already exists"):
            self.character_manager.create_character_file(character_data)

    def test_filename_collision_detection_different_characters(self):
        """Test that different character names generating the same filename raises ValueError."""
        # Create first character
        character1_data = {
            "name": "Test Character",
            "role": "Test Role",
            "backstory": "Test backstory"
        }
        self.character_manager.create_character_file(character1_data)

        # Try to create second character with different name but same sanitized filename
        character2_data = {
            "name": "Test@Character",  # This will sanitize to "test_character"
            "role": "Different Role",
            "backstory": "Different backstory"
        }

        with pytest.raises(ValueError, match="Filename collision detected"):
            self.character_manager.create_character_file(character2_data)

    def test_filename_collision_detection_special_characters(self):
        """Test filename collision with special characters that sanitize to same result."""
        # Create first character
        character1_data = {
            "name": "Test Character",
            "role": "Test Role",
            "backstory": "Test backstory"
        }
        self.character_manager.create_character_file(character1_data)

        # Try characters with different special characters that result in same filename
        collision_names = [
            "Test@Character",
            "Test_Character",
            "Test   Character",  # Multiple spaces
            "Test!!!Character",
        ]

        for name in collision_names:
            character_data = {
                "name": name,
                "role": "Different Role",
                "backstory": "Different backstory"
            }

            with pytest.raises(ValueError, match="Filename collision detected"):
                self.character_manager.create_character_file(character_data)

    def test_no_collision_with_different_sanitized_names(self):
        """Test that characters with different sanitized names can coexist."""
        character1_data = {
            "name": "Test Character A",
            "role": "Test Role",
            "backstory": "Test backstory"
        }

        character2_data = {
            "name": "Test Character B",
            "role": "Different Role",
            "backstory": "Different backstory"
        }

        # Both should succeed as they generate different filenames
        filename1 = self.character_manager.create_character_file(character1_data)
        filename2 = self.character_manager.create_character_file(character2_data)

        assert filename1 == "test_character_a"
        assert filename2 == "test_character_b"
