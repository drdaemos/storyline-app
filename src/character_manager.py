from pathlib import Path
from typing import Any

import yaml

from .models.character import Character


class CharacterManager:
    """Service for managing character cards - creation, validation, and storage."""

    def __init__(self, characters_dir: str = "characters") -> None:
        self.characters_dir = Path(characters_dir)
        # Ensure characters directory exists
        self.characters_dir.mkdir(exist_ok=True)

    def validate_character_data(self, data: dict[str, Any]) -> None:
        """
        Validate character data structure.

        Args:
            data: Character data dictionary

        Raises:
            ValueError: If required fields are missing or data is invalid
        """
        if not isinstance(data, dict):
            raise ValueError("Character data must be a dictionary")

        if not data:
            raise ValueError("Character data cannot be empty")

        # Validate required fields
        required_fields = {'name', 'role', 'backstory'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        # Validate field types
        if not isinstance(data.get('name'), str) or not data['name'].strip():
            raise ValueError("'name' must be a non-empty string")

        if not isinstance(data.get('role'), str) or not data['role'].strip():
            raise ValueError("'role' must be a non-empty string")

        if not isinstance(data.get('backstory'), str) or not data['backstory'].strip():
            raise ValueError("'backstory' must be a non-empty string")

        # Validate optional fields if present
        optional_string_fields = ['personality', 'appearance', 'setting_description']
        for field in optional_string_fields:
            if field in data and not isinstance(data[field], str):
                raise ValueError(f"'{field}' must be a string")

        if 'relationships' in data:
            if not isinstance(data['relationships'], dict):
                raise ValueError("'relationships' must be a dictionary")
            for key, value in data['relationships'].items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError("All keys and values in 'relationships' must be strings")

        if 'key_locations' in data:
            if not isinstance(data['key_locations'], list):
                raise ValueError("'key_locations' must be a list")
            for location in data['key_locations']:
                if not isinstance(location, str):
                    raise ValueError("All items in 'key_locations' must be strings")

    def validate_yaml_text(self, yaml_text: str) -> dict[str, Any]:
        """
        Parse and validate YAML text.

        Args:
            yaml_text: Raw YAML text string

        Returns:
            Parsed character data dictionary

        Raises:
            ValueError: If YAML is invalid or character data is invalid
        """
        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {str(e)}") from e

        if data is None:
            raise ValueError("YAML text cannot be empty")

        self.validate_character_data(data)
        return data

    def create_character_file(self, character_data: dict[str, Any]) -> str:
        """
        Create a character file from validated data.

        Args:
            character_data: Validated character data dictionary

        Returns:
            The filename of the created character file (without extension)

        Raises:
            ValueError: If character validation fails or filename collision occurs
            FileExistsError: If character file already exists
        """
        # Validate the data first
        self.validate_character_data(character_data)

        # Create Character object to ensure compatibility
        character = Character.from_dict(character_data)

        # Generate filename from character name (sanitized)
        filename = self._sanitize_filename(character.name)

        # Check for filename collision before creating file
        self._validate_filename_collision(filename, character.name)

        character_file = self.characters_dir / f"{filename}.yaml"

        # Write character data to YAML file
        with open(character_file, 'w', encoding='utf-8') as file:
            yaml.dump(character_data, file, default_flow_style=False, allow_unicode=True)

        return filename

    def _validate_filename_collision(self, filename: str, character_name: str) -> None:
        """
        Validate that the generated filename doesn't collide with existing characters.

        Args:
            filename: The sanitized filename that will be used
            character_name: The original character name

        Raises:
            ValueError: If filename collision detected with a different character
            FileExistsError: If character with same name already exists
        """
        character_file = self.characters_dir / f"{filename}.yaml"

        # If file doesn't exist, no collision
        if not character_file.exists():
            return

        # File exists - check if it's the same character name
        try:
            with open(character_file, encoding='utf-8') as file:
                existing_data = yaml.safe_load(file)

            # If existing file has the same character name, it's a duplicate character
            if existing_data and existing_data.get('name') == character_name:
                raise FileExistsError(f"Character '{character_name}' already exists")

            # Different character name but same filename - collision detected
            existing_name = existing_data.get('name', 'Unknown') if existing_data else 'Unknown'
            raise ValueError(
                f"Filename collision detected: Character name '{character_name}' would generate "
                f"filename '{filename}' which is already used by character '{existing_name}'. "
                f"Please use a different character name."
            )

        except (FileExistsError, ValueError):
            # Re-raise our intentional exceptions
            raise
        except yaml.YAMLError:
            # If we can't parse the existing YAML file, assume it's corrupted
            # and allow overwrite - this is a rare edge case
            return
        except OSError:
            # If we can't read the file for other reasons, assume it's corrupted and allow overwrite
            return

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize character name for use as filename.

        Args:
            name: Character name

        Returns:
            Sanitized filename
        """
        # Remove or replace problematic characters
        sanitized = name.lower().strip()
        # Replace spaces and special characters with underscores
        import re
        sanitized = re.sub(r'[^\w\-_]', '_', sanitized)
        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')

        if not sanitized:
            raise ValueError("Character name produces empty filename")

        return sanitized
