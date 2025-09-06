from dataclasses import dataclass
from typing import Any


@dataclass
class Character:
    """Class for representing a character in the role-playing interaction."""

    # Basic information
    name: str  # Name of the character
    role: str  # Profession or role in the story
    backstory: str  # Previous experiences, events and relationships
    personality: str  # Personality traits and characteristics
    appearance: str  # Physical description
    relationships: dict[str, str]  # Relationships with other characters (e.g., "user": "description")
    key_locations: list[str]  # Important locations for the character
    setting_description: str  # Description of the world/setting the character exists in

    @classmethod
    def from_dict(cls, data: dict[str, str | Any]) -> "Character":
        """Initialize the character from a dictionary."""
        # Handle default values for optional fields
        relationships = data.get('relationships', {})
        key_locations = data.get('key_locations', [])

        return cls(
            name=data['name'],
            role=data['role'],
            backstory=data['backstory'],
            personality=data.get('personality', ''),
            appearance=data.get('appearance', ''),
            relationships=relationships,
            key_locations=key_locations,
            setting_description=data.get('setting_description', '')
        )
