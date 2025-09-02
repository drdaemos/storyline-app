from pathlib import Path

import yaml

from .models.character import Character


class CharacterLoader:
    def __init__(self, characters_dir: str = "characters") -> None:
        self.characters_dir = Path(characters_dir)

    def load_character(self, character_name: str) -> Character:
        character_file = self.characters_dir / f"{character_name}.yaml"

        if not character_file.exists():
            raise FileNotFoundError(f"Character file not found: {character_file}")

        with open(character_file) as file:
            character_data = yaml.safe_load(file)

        if character_data is None:
            raise ValueError("Missing required fields: {'name', 'role', 'backstory'}")

        # Validate required fields
        required_fields = {'name', 'role', 'backstory'}
        missing_fields = required_fields - set(character_data.keys())
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        return Character.from_dict(character_data)

    def list_characters(self) -> list[str]:
        if not self.characters_dir.exists():
            return []

        return [file.stem for file in self.characters_dir.glob("*.yaml") if file.is_file()]

    def get_character_info(self, character_name: str) -> Character | None:
        try:
            return self.load_character(character_name)
        except (FileNotFoundError, ValueError):
            return None
