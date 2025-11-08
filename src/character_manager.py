import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .memory import CharacterRegistry
from .models.character import Character


class CharacterManager:
    """Service for managing character cards - creation, validation, and storage."""

    def __init__(self, characters_dir: str = "characters", memory_dir: Path | None = None) -> None:
        self.characters_dir = Path(characters_dir)
        # Ensure characters directory exists
        self.characters_dir.mkdir(exist_ok=True)
        self.registry = CharacterRegistry(memory_dir)

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
        required_fields = {"name", "tagline", "backstory"}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        # Validate field types
        if not isinstance(data.get("name"), str) or not data["name"].strip():
            raise ValueError("'name' must be a non-empty string")

        if not isinstance(data.get("tagline"), str) or not data["tagline"].strip():
            raise ValueError("'tagline' must be a non-empty string")

        if not isinstance(data.get("backstory"), str) or not data["backstory"].strip():
            raise ValueError("'backstory' must be a non-empty string")

        # Validate optional fields if present
        optional_string_fields = ["personality", "appearance", "setting_description"]
        for field in optional_string_fields:
            if field in data and not isinstance(data[field], str):
                raise ValueError(f"'{field}' must be a string")

        if "relationships" in data:
            if not isinstance(data["relationships"], dict):
                raise ValueError("'relationships' must be a dictionary")
            for key, value in data["relationships"].items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError("All keys and values in 'relationships' must be strings")

        if "key_locations" in data:
            if not isinstance(data["key_locations"], list):
                raise ValueError("'key_locations' must be a list")
            for location in data["key_locations"]:
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

    def create_character_file(self, character_data: dict[str, Any], user_id: str = "anonymous", is_persona: bool = False) -> str:
        """
        Create a character file from validated data.

        Args:
            character_data: Validated character data dictionary
            user_id: ID of the user (defaults to 'anonymous')
            is_persona: Whether this character is a persona (user character) (default: False)

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
        with open(character_file, "w", encoding="utf-8") as file:
            yaml.dump(character_data, file, default_flow_style=False, allow_unicode=True)

        # Also save to database
        self.save_character_to_database(filename, character_data, user_id=user_id, is_persona=is_persona)

        return filename

    def save_character_to_database(self, character_id: str, character_data: dict[str, Any], schema_version: int = 1, user_id: str = "anonymous", is_persona: bool = False) -> bool:
        """
        Save character data to the database.

        Args:
            character_id: Character ID (same as filename)
            character_data: Character data dictionary
            schema_version: Schema version for the character data
            user_id: ID of the user (defaults to 'anonymous')
            is_persona: Whether this character is a persona (user character) (default: False)

        Returns:
            True if saved successfully
        """
        # Validate the data first
        self.validate_character_data(character_data)

        return self.registry.save_character(character_id, character_data, schema_version, user_id, is_persona)

    def load_character_from_file_to_database(self, character_id: str) -> bool:
        """
        Load character from file and save to database.

        Args:
            character_id: Character ID (filename without extension)

        Returns:
            True if loaded and saved successfully

        Raises:
            FileNotFoundError: If character file not found
            ValueError: If character data is invalid
        """
        character_file = self.characters_dir / f"{character_id}.yaml"

        if not character_file.exists():
            raise FileNotFoundError(f"Character file not found: {character_file}")

        with open(character_file, encoding="utf-8") as file:
            character_data = yaml.safe_load(file)

        if character_data is None:
            raise ValueError("Character file is empty or invalid")

        # Validate character data
        self.validate_character_data(character_data)

        # Extract is_persona flag from character data (defaults to False if not present)
        is_persona = character_data.get("is_persona", False)

        # Save to database
        return self.registry.save_character(character_id, character_data, is_persona=is_persona)

    def _calculate_data_hash(self, data: dict[str, Any]) -> str:
        """Calculate a hash of character data for comparison."""
        # Sort keys to ensure consistent hashing
        sorted_data = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(sorted_data.encode()).hexdigest()

    def sync_files_to_database(self) -> dict[str, Any]:
        """
        Sync all character files to the database.

        Returns:
            Dictionary with sync results:
            {
                "added": [list of character IDs added to database],
                "updated": [list of character IDs updated in database],
                "skipped": [list of character IDs that were unchanged],
                "errors": [list of {"character_id": str, "error": str}]
            }
        """
        results = {"added": [], "updated": [], "skipped": [], "errors": []}

        if not self.characters_dir.exists():
            return results

        # Get all YAML files
        character_files = list(self.characters_dir.glob("*.yaml"))

        for character_file in character_files:
            character_id = character_file.stem
            try:
                # Load file data
                with open(character_file, encoding="utf-8") as file:
                    file_data = yaml.safe_load(file)

                if file_data is None:
                    results["errors"].append({"character_id": character_id, "error": "Character file is empty or invalid"})
                    continue

                # Validate file data
                self.validate_character_data(file_data)

                # Extract is_persona flag from file data (defaults to False if not present)
                is_persona = file_data.get("is_persona", False)

                # Check if character exists in database (use 'anonymous' for sync operations)
                db_character = self.registry.get_character(character_id, "anonymous")

                if db_character is None:
                    # Character doesn't exist in database - add it
                    self.registry.save_character(character_id, file_data, is_persona=is_persona)
                    results["added"].append(character_id)
                else:
                    # Character exists - check if data is different
                    db_data = db_character["character_data"]
                    file_hash = self._calculate_data_hash(file_data)
                    db_hash = self._calculate_data_hash(db_data)

                    if file_hash != db_hash:
                        # Data is different - update database
                        self.registry.save_character(character_id, file_data, is_persona=is_persona)
                        results["updated"].append(character_id)
                    else:
                        # Data is the same - skip
                        results["skipped"].append(character_id)

            except Exception as e:
                results["errors"].append({"character_id": character_id, "error": str(e)})

        return results

    def check_sync_status(self) -> dict[str, Any]:
        """
        Check the sync status between files and database without making changes.

        Returns:
            Dictionary with status information:
            {
                "file_only": [list of character IDs only in files],
                "db_only": [list of character IDs only in database],
                "both_same": [list of character IDs in both with same data],
                "both_different": [list of character IDs in both with different data],
                "file_errors": [list of {"character_id": str, "error": str}]
            }
        """
        status = {"file_only": [], "db_only": [], "both_same": [], "both_different": [], "file_errors": []}

        # Get all database characters (use 'anonymous' for sync operations)
        try:
            db_characters = {char["id"]: char for char in self.registry.get_all_characters("anonymous")}
        except Exception:
            db_characters = {}

        # Get all file characters
        file_characters = {}
        if self.characters_dir.exists():
            for character_file in self.characters_dir.glob("*.yaml"):
                character_id = character_file.stem
                try:
                    with open(character_file, encoding="utf-8") as file:
                        file_data = yaml.safe_load(file)

                    if file_data is None:
                        status["file_errors"].append({"character_id": character_id, "error": "Character file is empty or invalid"})
                        continue

                    self.validate_character_data(file_data)
                    file_characters[character_id] = file_data

                except Exception as e:
                    status["file_errors"].append({"character_id": character_id, "error": str(e)})

        # Compare file and database characters
        all_character_ids = set(file_characters.keys()) | set(db_characters.keys())

        for character_id in all_character_ids:
            in_file = character_id in file_characters
            in_db = character_id in db_characters

            if in_file and not in_db:
                status["file_only"].append(character_id)
            elif not in_file and in_db:
                status["db_only"].append(character_id)
            elif in_file and in_db:
                # Compare data
                file_hash = self._calculate_data_hash(file_characters[character_id])
                db_hash = self._calculate_data_hash(db_characters[character_id]["character_data"])

                if file_hash == db_hash:
                    status["both_same"].append(character_id)
                else:
                    status["both_different"].append(character_id)

        return status

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
            with open(character_file, encoding="utf-8") as file:
                existing_data = yaml.safe_load(file)

            # If existing file has the same character name, it's a duplicate character
            if existing_data and existing_data.get("name") == character_name:
                raise FileExistsError(f"Character '{character_name}' already exists")

            # Different character name but same filename - collision detected
            existing_name = existing_data.get("name", "Unknown") if existing_data else "Unknown"
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

        sanitized = re.sub(r"[^\w\-_]", "_", sanitized)
        # Remove consecutive underscores
        sanitized = re.sub(r"_+", "_", sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")

        if not sanitized:
            raise ValueError("Character name produces empty filename")

        return sanitized
