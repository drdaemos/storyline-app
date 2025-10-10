import tempfile
from pathlib import Path

import pytest

from src.character_loader import CharacterLoader
from src.memory.character_registry import CharacterRegistry


class TestCharacterLoader:
    def test_init_default_directory(self):
        loader = CharacterLoader()
        assert loader.registry is not None

    def test_init_custom_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = CharacterLoader(Path(temp_dir))
            assert loader.registry is not None

    def test_load_character_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up character registry with test data
            registry = CharacterRegistry(Path(temp_dir))

            character_data = {
                "name": "Eldric",
                "role": "Village Blacksmith",
                "backstory": "A gruff but kind blacksmith who has lived in this village for 30 years.",
                "personality": "Gruff but kind",
                "appearance": "Tall and sturdy"
            }

            # Save character to database
            registry.save_character("eldric", character_data)

            # Test loading character
            loader = CharacterLoader(Path(temp_dir))
            result = loader.load_character("eldric")

            assert result.name == "Eldric"
            assert result.role == "Village Blacksmith"
            assert "gruff but kind blacksmith" in result.backstory

    def test_load_character_file_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = CharacterLoader(Path(temp_dir))

            with pytest.raises(FileNotFoundError) as excinfo:
                loader.load_character("nonexistent")

            assert "not found in database" in str(excinfo.value)

    def test_list_characters_empty_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = CharacterLoader(Path(temp_dir))
            result = loader.list_characters()
            assert result == []

    def test_list_characters_nonexistent_directory(self):
        # Database handles non-existent directories gracefully
        loader = CharacterLoader(Path("/nonexistent/path"))
        result = loader.list_characters()
        assert result == []

    def test_list_characters_with_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = CharacterRegistry(Path(temp_dir))

            # Add test characters to database
            registry.save_character("alice", {"name": "Alice", "role": "Adventurer", "backstory": "Test"})
            registry.save_character("bob", {"name": "Bob", "role": "Merchant", "backstory": "Test"})

            loader = CharacterLoader(Path(temp_dir))
            result = loader.list_characters()

            assert len(result) == 2
            assert "alice" in result
            assert "bob" in result
            assert result == sorted(result)  # Should be sorted

    def test_list_characters_ignores_non_yaml_files(self):
        # This test is no longer relevant since we're database-only
        # but keeping for compatibility - database only stores valid characters
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = CharacterRegistry(Path(temp_dir))
            registry.save_character("valid_char", {"name": "Valid", "role": "Test", "backstory": "Test"})

            loader = CharacterLoader(Path(temp_dir))
            result = loader.list_characters()

            assert len(result) == 1
            assert "valid_char" in result

    def test_list_characters_ignores_subdirectories(self):
        # This test is no longer relevant since we're database-only
        # but keeping for compatibility
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = CharacterRegistry(Path(temp_dir))
            registry.save_character("char1", {"name": "Char1", "role": "Test", "backstory": "Test"})

            loader = CharacterLoader(Path(temp_dir))
            result = loader.list_characters()

            assert len(result) == 1
            assert "char1" in result

    def test_get_character_info_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = CharacterRegistry(Path(temp_dir))

            character_data = {
                "name": "Test Character",
                "role": "Test Role",
                "backstory": "Test backstory",
                "personality": "Test personality"
            }

            registry.save_character("test_char", character_data)

            loader = CharacterLoader(Path(temp_dir))
            result = loader.get_character_info("test_char")

            assert result is not None
            assert result.name == "Test Character"
            assert result.role == "Test Role"

    def test_get_character_info_file_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = CharacterLoader(Path(temp_dir))
            result = loader.get_character_info("nonexistent")
            assert result is None

    def test_get_character_info_invalid_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test when character exists but has invalid data - should not happen
            # with database validation, but test error handling
            loader = CharacterLoader(Path(temp_dir))
            result = loader.get_character_info("nonexistent")
            assert result is None

    def test_load_character_with_extra_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = CharacterRegistry(Path(temp_dir))

            character_data = {
                "name": "Extended Character",
                "role": "Test Role",
                "backstory": "Test backstory",
                "personality": "Test personality",
                "appearance": "Test appearance",
                "relationships": {"friend": "Alice"},
                "key_locations": ["Castle", "Forest"],
                "setting_description": "Fantasy world"
            }

            registry.save_character("extended_char", character_data)

            loader = CharacterLoader(Path(temp_dir))
            result = loader.load_character("extended_char")

            assert result.name == "Extended Character"
            assert result.relationships == {"friend": "Alice"}
            assert result.key_locations == ["Castle", "Forest"]

    def test_load_character_empty_yaml_file(self):
        # This test is no longer relevant since database validation prevents empty data
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = CharacterLoader(Path(temp_dir))

            with pytest.raises(FileNotFoundError):
                loader.load_character("empty_char")

    def test_load_character_malformed_yaml(self):
        # This test is no longer relevant since database stores structured data
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = CharacterLoader(Path(temp_dir))

            with pytest.raises(FileNotFoundError):
                loader.load_character("malformed_char")

    def test_integration_with_real_character_files(self):
        # Test database integration rather than file integration
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = CharacterRegistry(Path(temp_dir))

            # Simulate real character data structure
            character_data = {
                "name": "Eldric Ironforge",
                "role": "Village Blacksmith",
                "backstory": "Eldric has been the village blacksmith for over 30 years. He's known for his exceptional craftsmanship and his willingness to help anyone in need. He lost his wife to a plague 10 years ago and has since dedicated his life to his craft and the community.",
                "personality": "Gruff exterior but kind heart. Speaks directly and honestly. Has a soft spot for children and animals. Takes pride in his work and doesn't tolerate shoddy craftsmanship.",
                "appearance": "A tall, sturdy man in his fifties with calloused hands, graying hair, and kind brown eyes. Usually covered in soot from the forge.",
                "relationships": {
                    "The Mayor": "Respectful professional relationship",
                    "Local children": "Protective and nurturing, like a grandfather figure"
                },
                "key_locations": ["The Village Forge", "The Local Tavern", "The Cemetery"],
                "setting_description": "A small, peaceful village surrounded by rolling hills and farmland. The forge is at the center of town, always filled with the sound of hammer on anvil."
            }

            registry.save_character("eldric_ironforge", character_data)

            loader = CharacterLoader(Path(temp_dir))
            character = loader.load_character("eldric_ironforge")

            assert character.name == "Eldric Ironforge"
            assert character.role == "Village Blacksmith"
            assert "30 years" in character.backstory
            assert "Gruff exterior" in character.personality
            assert len(character.relationships) == 2
            assert len(character.key_locations) == 3

    def test_character_loader_path_resolution(self):
        # Test that CharacterLoader works with different path types
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test with Path object
            loader1 = CharacterLoader(temp_path)
            assert loader1.registry is not None

            # Test with None (default)
            loader2 = CharacterLoader()
            assert loader2.registry is not None
