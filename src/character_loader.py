from pathlib import Path
from typing import Any

import yaml


class CharacterLoader:
    def __init__(self, characters_dir: str = "characters") -> None:
        self.characters_dir = Path(characters_dir)

    def load_character(self, character_name: str) -> dict[str, Any]:
        character_file = self.characters_dir / f"{character_name}.yaml"

        if not character_file.exists():
            raise FileNotFoundError(f"Character file not found: {character_file}")

        with open(character_file) as file:
            character_data = yaml.safe_load(file)

        if character_data is None:
            character_data = {}

        required_fields = ["name", "role", "backstory"]
        for field in required_fields:
            if field not in character_data:
                raise ValueError(f"Missing required field '{field}' in {character_file}")

        return character_data

    def list_characters(self) -> list[str]:
        if not self.characters_dir.exists():
            return []

        return [file.stem for file in self.characters_dir.glob("*.yaml") if file.is_file()]

    def get_character_info(self, character_name: str) -> dict[str, Any] | None:
        try:
            return self.load_character(character_name)
        except (FileNotFoundError, ValueError):
            return None
