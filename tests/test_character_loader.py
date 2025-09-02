import tempfile
from pathlib import Path

import pytest
import yaml

from src.character_loader import CharacterLoader


class TestCharacterLoader:
    def test_init_default_directory(self):
        loader = CharacterLoader()
        assert loader.characters_dir == Path("characters")

    def test_init_custom_directory(self):
        loader = CharacterLoader("custom_chars")
        assert loader.characters_dir == Path("custom_chars")

    def test_load_character_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            character_data = {
                "name": "Eldric",
                "role": "Village Blacksmith",
                "backstory": "A gruff but kind blacksmith who has lived in this village for 30 years.",
                "personality": "Gruff but kind",
                "appearance": "Tall and sturdy"
            }

            char_file = chars_dir / "eldric.yaml"
            with open(char_file, "w") as f:
                yaml.dump(character_data, f)

            loader = CharacterLoader(str(chars_dir))
            result = loader.load_character("eldric")

            assert result.name == "Eldric"
            assert result.role == "Village Blacksmith"
            assert "gruff but kind blacksmith" in result.backstory

    def test_load_character_file_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            loader = CharacterLoader(str(chars_dir))

            with pytest.raises(FileNotFoundError) as excinfo:
                loader.load_character("nonexistent")

            assert "Character file not found" in str(excinfo.value)
            assert "nonexistent.yaml" in str(excinfo.value)

    def test_list_characters_empty_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            loader = CharacterLoader(str(chars_dir))
            characters = loader.list_characters()

            assert characters == []

    def test_list_characters_nonexistent_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_dir = Path(temp_dir) / "nonexistent"

            loader = CharacterLoader(str(nonexistent_dir))
            characters = loader.list_characters()

            assert characters == []

    def test_list_characters_with_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            character_files = ["eldric.yaml", "myra.yaml", "thorin.yaml"]
            for filename in character_files:
                char_file = chars_dir / filename
                with open(char_file, "w") as f:
                    yaml.dump({"name": "Test", "role": "Test", "backstory": "Test"}, f)

            loader = CharacterLoader(str(chars_dir))
            characters = loader.list_characters()

            expected = ["eldric", "myra", "thorin"]
            assert sorted(characters) == sorted(expected)

    def test_list_characters_ignores_non_yaml_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            (chars_dir / "character1.yaml").touch()
            (chars_dir / "character2.yaml").touch()
            (chars_dir / "readme.txt").touch()
            (chars_dir / "config.json").touch()
            (chars_dir / "notes.md").touch()

            loader = CharacterLoader(str(chars_dir))
            characters = loader.list_characters()

            expected = ["character1", "character2"]
            assert sorted(characters) == sorted(expected)

    def test_list_characters_ignores_subdirectories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            (chars_dir / "character.yaml").touch()
            subdir = chars_dir / "subdirectory"
            subdir.mkdir()
            (subdir / "nested.yaml").touch()

            loader = CharacterLoader(str(chars_dir))
            characters = loader.list_characters()

            assert characters == ["character"]

    def test_get_character_info_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            character_data = {
                "name": "Luna",
                "role": "Mysterious Wizard",
                "backstory": "An ancient wizard with secrets",
            }

            char_file = chars_dir / "luna.yaml"
            with open(char_file, "w") as f:
                yaml.dump(character_data, f)

            loader = CharacterLoader(str(chars_dir))
            result = loader.get_character_info("luna")

            assert result.name == character_data["name"]
            assert result.role == character_data["role"]
            assert result.backstory == character_data["backstory"]

    def test_get_character_info_file_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            loader = CharacterLoader(str(chars_dir))
            result = loader.get_character_info("nonexistent")

            assert result is None

    def test_get_character_info_invalid_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            # Create a truly invalid file - completely empty
            char_file = chars_dir / "incomplete.yaml"
            char_file.touch()

            loader = CharacterLoader(str(chars_dir))
            result = loader.get_character_info("incomplete")

            assert result is None

    def test_load_character_with_extra_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            character_data = {
                "name": "Enhanced",
                "role": "Super Wizard",
                "backstory": "A wizard with extra properties",
                "personality": "Wise and powerful",
                "level": 50,
                "skills": ["magic", "alchemy"],
                "location": "Tower of Wisdom",
            }

            char_file = chars_dir / "enhanced.yaml"
            with open(char_file, "w") as f:
                yaml.dump(character_data, f)

            loader = CharacterLoader(str(chars_dir))
            result = loader.load_character("enhanced")

            assert result.name == character_data["name"]
            assert result.role == character_data["role"]
            assert result.backstory == character_data["backstory"]

    def test_load_character_empty_yaml_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            char_file = chars_dir / "empty.yaml"
            char_file.touch()

            loader = CharacterLoader(str(chars_dir))

            with pytest.raises(ValueError) as excinfo:
                loader.load_character("empty")

            assert "Missing required fields" in str(excinfo.value)

    def test_load_character_malformed_yaml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            char_file = chars_dir / "malformed.yaml"
            with open(char_file, "w") as f:
                f.write("invalid: yaml: content: [unclosed")

            loader = CharacterLoader(str(chars_dir))

            with pytest.raises(yaml.YAMLError):
                loader.load_character("malformed")

    def test_integration_with_real_character_files(self):
        loader = CharacterLoader("characters")

        if loader.characters_dir.exists():
            characters = loader.list_characters()

            for char_name in characters:
                char_info = loader.get_character_info(char_name)
                assert char_info is not None
                assert hasattr(char_info, "name")
                assert hasattr(char_info, "role")
                assert hasattr(char_info, "backstory")

                loaded_data = loader.load_character(char_name)
                assert loaded_data.name == char_info.name

    def test_character_loader_path_resolution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "test_chars"
            chars_dir.mkdir()

            char_data = {"name": "Test", "role": "Test", "backstory": "Test"}
            char_file = chars_dir / "test.yaml"
            with open(char_file, "w") as f:
                yaml.dump(char_data, f)

            loader = CharacterLoader(str(chars_dir))
            result = loader.load_character("test")
            assert result.name == char_data["name"]
            assert result.role == char_data["role"]
            assert result.backstory == char_data["backstory"]
