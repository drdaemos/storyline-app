from pathlib import Path

from .memory import CharacterRegistry
from .models.api_models import CharacterSummary
from .models.character import Character


class CharacterLoader:
    def __init__(self, memory_dir: Path | None = None) -> None:
        self.registry = CharacterRegistry(memory_dir)

    def load_character(self, character_name: str, user_id: str = "anonymous") -> Character:
        """
        Load character from database.

        Args:
            character_name: Character ID/name to load
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            Character object

        Raises:
            FileNotFoundError: If character not found in database
            ValueError: If character data is invalid
        """
        db_character = self.registry.get_character(character_name, user_id)
        if not db_character:
            raise FileNotFoundError(f"Character '{character_name}' not found in database")

        character_data = db_character["character_data"]
        return Character.from_dict(character_data)

    def list_characters(self, user_id: str = "anonymous") -> list[str]:
        """
        List all available characters from database for a specific user.

        Args:
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            List of character IDs/names
        """
        try:
            db_chars = self.registry.get_all_characters(user_id)
            return sorted([char["id"] for char in db_chars])
        except Exception:
            return []

    def list_character_summaries(self, user_id: str = "anonymous") -> list[CharacterSummary]:
        """
        List all available characters with their basic info (name and tagline) for a specific user.

        Args:
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            List of CharacterSummary objects with name and tagline
        """
        try:
            db_chars = self.registry.get_all_characters(user_id)
            summaries = []
            for char in db_chars:
                character_data = char.get("character_data", {})
                summaries.append(CharacterSummary(id=char["id"], name=character_data.get("name", char["id"]), tagline=character_data.get("tagline", "")))
            return sorted(summaries, key=lambda x: x.name)
        except Exception:
            return []

    def list_persona_summaries(self, user_id: str = "anonymous") -> list[CharacterSummary]:
        """
        List all available persona characters with their basic info (name and tagline) for a specific user.

        Args:
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            List of CharacterSummary objects with name and tagline for personas only
        """
        try:
            db_chars = self.registry.get_personas(user_id)
            summaries = []
            for char in db_chars:
                character_data = char.get("character_data", {})
                summaries.append(CharacterSummary(id=char["id"], name=character_data.get("name", char["id"]), tagline=character_data.get("tagline", "")))
            return sorted(summaries, key=lambda x: x.name)
        except Exception:
            return []

    def get_character_info(self, character_name: str, user_id: str = "anonymous") -> Character | None:
        """
        Get character info, returning None if not found.

        Args:
            character_name: Character ID/name to get info for
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            Character object or None if not found
        """
        try:
            return self.load_character(character_name, user_id)
        except (FileNotFoundError, ValueError):
            return None
