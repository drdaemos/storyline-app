from pathlib import Path

from .memory import CharacterRegistry
from .models.character import Character


class CharacterLoader:
    def __init__(self, memory_dir: Path | None = None) -> None:
        self.registry = CharacterRegistry(memory_dir)

    def load_character(self, character_name: str) -> Character:
        """
        Load character from database.

        Args:
            character_name: Character ID/name to load

        Returns:
            Character object

        Raises:
            FileNotFoundError: If character not found in database
            ValueError: If character data is invalid
        """
        db_character = self.registry.get_character(character_name)
        if not db_character:
            raise FileNotFoundError(f"Character '{character_name}' not found in database")

        character_data = db_character["character_data"]
        return Character.from_dict(character_data)

    def list_characters(self) -> list[str]:
        """
        List all available characters from database.

        Returns:
            List of character IDs/names
        """
        try:
            db_chars = self.registry.get_all_characters()
            return sorted([char["id"] for char in db_chars])
        except Exception:
            return []

    def get_character_info(self, character_name: str) -> Character | None:
        """
        Get character info, returning None if not found.

        Args:
            character_name: Character ID/name to get info for

        Returns:
            Character object or None if not found
        """
        try:
            return self.load_character(character_name)
        except (FileNotFoundError, ValueError):
            return None
