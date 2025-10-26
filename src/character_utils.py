"""Utility functions for character-related operations."""

from .models.character import Character


def format_character_description(character: Character) -> dict[str, str]:
    """
    Format character information into a dictionary suitable for prompt templates.

    Args:
        character: The character to format

    Returns:
        Dictionary mapping prompt variable names to character-derived values
    """
    return {
        "character_name": character.name,
        "character_background": character.backstory,
        "character_appearance": character.appearance,
        "character_personality": character.personality,
        "character_interests": "\n".join([f"- {item}" for item in character.interests]),
        "character_desires": "\n".join([f"- {item}" for item in character.desires]),
        "character_dislikes": "\n".join([f"- {item}" for item in character.dislikes]),
        "character_kinks": "\n".join([f"- {item}" for item in character.kinks]),
        "relationships": "\n".join([f"- {key}: {value}" for key, value in character.relationships.items()]),
        "setting_description": character.setting_description or "Not specified",
        "key_locations": "\n".join([f"- {location}" for location in character.key_locations]),
    }
