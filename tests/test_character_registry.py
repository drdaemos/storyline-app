import os
import tempfile
from pathlib import Path

from src.memory.character_registry import CharacterRegistry


class TestCharacterRegistry:
    def setup_method(self):
        """Set up a temporary memory directory with test database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        # Set environment variable to use test database in temp directory
        self.original_database_url = os.environ.get("DATABASE_URL")
        test_db_path = Path(self.temp_dir) / "test_characters.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
        # Create custom registry instance that uses test database
        self.registry = CharacterRegistry(memory_dir=Path(self.temp_dir))
        self.character_id = "test_character"

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        # Close database connection
        if hasattr(self, 'registry'):
            self.registry.close()

        # Clean up temp directory
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        # Restore original environment
        if self.original_database_url is not None:
            os.environ["DATABASE_URL"] = self.original_database_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

    def test_save_character_new(self):
        """Test saving a new character."""
        character_data = {"name": "Test Character", "description": "A test character", "personality": ["friendly", "curious"], "background": "Lives in a test environment"}

        success = self.registry.save_character(self.character_id, character_data)
        assert success

        # Verify character was saved
        retrieved = self.registry.get_character(self.character_id, "anonymous")
        assert retrieved is not None
        assert retrieved["id"] == self.character_id
        assert retrieved["character_data"] == character_data
        assert retrieved["schema_version"] == 1

    def test_save_character_update(self):
        """Test updating an existing character."""
        initial_data = {"name": "Initial Name", "age": 25}
        updated_data = {"name": "Updated Name", "age": 26, "location": "New Place"}

        # Save initial character
        self.registry.save_character(self.character_id, initial_data)

        # Update character
        success = self.registry.save_character(self.character_id, updated_data, schema_version=2)
        assert success

        # Verify update
        retrieved = self.registry.get_character(self.character_id, "anonymous")
        assert retrieved is not None
        assert retrieved["character_data"] == updated_data
        assert retrieved["schema_version"] == 2

    def test_get_character_not_found(self):
        """Test retrieving a non-existent character."""
        result = self.registry.get_character("nonexistent", "anonymous")
        assert result is None

    def test_character_exists(self):
        """Test checking if a character exists."""
        character_data = {"name": "Existence Test"}

        # Initially doesn't exist
        assert not self.registry.character_exists(self.character_id, "anonymous")

        # Save character
        self.registry.save_character(self.character_id, character_data)

        # Now it exists
        assert self.registry.character_exists(self.character_id, "anonymous")

    def test_delete_character(self):
        """Test deleting a character."""
        character_data = {"name": "To Be Deleted"}

        # Save character
        self.registry.save_character(self.character_id, character_data)
        assert self.registry.character_exists(self.character_id, "anonymous")

        # Delete character
        success = self.registry.delete_character(self.character_id, "anonymous")
        assert success
        assert not self.registry.character_exists(self.character_id, "anonymous")

    def test_delete_nonexistent_character(self):
        """Test deleting a character that doesn't exist."""
        success = self.registry.delete_character("nonexistent", "anonymous")
        assert not success

    def test_get_all_characters(self):
        """Test retrieving all characters."""
        characters = [
            ("char1", {"name": "Character 1"}, 1),
            ("char2", {"name": "Character 2"}, 1),
            ("char3", {"name": "Character 3"}, 2),
        ]

        # Save characters
        for char_id, data, version in characters:
            self.registry.save_character(char_id, data, version)

        # Get all characters
        all_chars = self.registry.get_all_characters("anonymous")
        assert len(all_chars) == 3

        # Verify all characters are present
        char_ids = {char["id"] for char in all_chars}
        assert char_ids == {"char1", "char2", "char3"}

    def test_get_characters_by_schema_version(self):
        """Test retrieving characters by schema version."""
        characters = [
            ("char1", {"name": "Character 1"}, 1),
            ("char2", {"name": "Character 2"}, 1),
            ("char3", {"name": "Character 3"}, 2),
        ]

        # Save characters
        for char_id, data, version in characters:
            self.registry.save_character(char_id, data, version)

        # Get characters with schema version 1
        v1_chars = self.registry.get_characters_by_schema_version("anonymous", 1)
        assert len(v1_chars) == 2
        v1_ids = {char["id"] for char in v1_chars}
        assert v1_ids == {"char1", "char2"}

        # Get characters with schema version 2
        v2_chars = self.registry.get_characters_by_schema_version("anonymous", 2)
        assert len(v2_chars) == 1
        assert v2_chars[0]["id"] == "char3"

    def test_update_character_schema(self):
        """Test updating only the schema version of a character."""
        character_data = {"name": "Schema Test"}

        # Save character with version 1
        self.registry.save_character(self.character_id, character_data, 1)

        # Update schema version to 2
        success = self.registry.update_character_schema(self.character_id, "anonymous", 2)
        assert success

        # Verify schema version was updated
        retrieved = self.registry.get_character(self.character_id, "anonymous")
        assert retrieved is not None
        assert retrieved["schema_version"] == 2
        assert retrieved["character_data"] == character_data  # Data unchanged

    def test_update_schema_nonexistent_character(self):
        """Test updating schema version of a non-existent character."""
        success = self.registry.update_character_schema("nonexistent", "anonymous", 2)
        assert not success

    def test_get_character_count(self):
        """Test getting the total character count."""
        # Initially no characters
        assert self.registry.get_character_count("anonymous") == 0

        # Add some characters
        for i in range(3):
            self.registry.save_character(f"char{i}", {"name": f"Character {i}"})

        # Verify count
        assert self.registry.get_character_count("anonymous") == 3

    def test_json_character_data(self):
        """Test storing complex JSON character data."""
        complex_data = {
            "name": "Complex Character",
            "stats": {"strength": 15, "intelligence": 18, "charisma": 12},
            "inventory": ["sword", "potion", "map"],
            "relationships": {"allies": ["hero", "wizard"], "enemies": ["dragon", "villain"]},
            "metadata": {"created_by": "test_user", "tags": ["fantasy", "protagonist"], "active": True},
        }

        # Save complex character
        success = self.registry.save_character(self.character_id, complex_data)
        assert success

        # Retrieve and verify
        retrieved = self.registry.get_character(self.character_id, "anonymous")
        assert retrieved is not None
        assert retrieved["character_data"] == complex_data

    def test_close_method(self):
        """Test the close method."""
        # Should not raise any exceptions
        self.registry.close()

    def test_character_timestamps(self):
        """Test that created_at and updated_at timestamps work correctly."""
        character_data = {"name": "Timestamp Test"}

        # Save character
        self.registry.save_character(self.character_id, character_data)
        initial_char = self.registry.get_character(self.character_id, "anonymous")

        assert initial_char is not None
        assert "created_at" in initial_char
        assert "updated_at" in initial_char

        # Update character
        updated_data = {"name": "Updated Timestamp Test"}
        self.registry.save_character(self.character_id, updated_data)
        updated_char = self.registry.get_character(self.character_id, "anonymous")

        assert updated_char is not None
        # created_at should remain the same
        assert updated_char["created_at"] == initial_char["created_at"]
        # updated_at should be different (more recent)
        assert updated_char["updated_at"] != initial_char["updated_at"]
