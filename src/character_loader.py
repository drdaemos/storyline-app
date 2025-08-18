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
            raise ValueError("Missing required field")

        # For backward compatibility, if the character data doesn't have all required fields,
        # add default values
        required_fields = {
            'name': 'Unknown',
            'role': 'Unknown',
            'backstory': 'Unknown',
            'appearance': 'Unknown',
            'autonomy': 'independent',
            'safety': 'secure',
            'openmindedness': 'moderate',
            'emotional_stability': 'stable',
            'attachment_pattern': 'secure',
            'conscientiousness': 'organized',
            'sociability': 'moderate',
            'social_trust': 'trusting',
            'risk_approach': 'balanced',
            'conflict_approach': 'collaborative',
            'leadership_style': 'democratic',
            'stress_level': 'low',
            'energy_level': 'medium',
            'mood': 'neutral'
        }

        # Fill in missing fields with defaults
        for field, default_value in required_fields.items():
            if field not in character_data:
                character_data[field] = default_value

        # Filter out extra fields that aren't part of the Character model
        filtered_data = {k: v for k, v in character_data.items() if k in required_fields}

        return Character.from_dict(filtered_data)

    def list_characters(self) -> list[str]:
        if not self.characters_dir.exists():
            return []

        return [file.stem for file in self.characters_dir.glob("*.yaml") if file.is_file()]

    def get_character_info(self, character_name: str) -> Character | None:
        try:
            return self.load_character(character_name)
        except (FileNotFoundError, ValueError):
            return None
