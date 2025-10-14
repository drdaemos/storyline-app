from typing import Any

from .character_manager import CharacterManager
from .models.character import Character
from .models.prompt_processor import PromptProcessor


class CharacterCreator:
    """Service for creating complete, engaging characters from partial character data."""

    def __init__(self, prompt_processor: PromptProcessor, character_manager: CharacterManager | None = None) -> None:
        """
        Initialize the CharacterCreator.

        Args:
            prompt_processor: The prompt processor to use for generating character fields
            character_manager: Optional character manager for validation and storage
        """
        self.prompt_processor = prompt_processor
        self.character_manager = character_manager or CharacterManager()

    def generate(self, partial_character: dict[str, Any]) -> Character:
        """
        Generate a complete, engaging character from partial character data.

        Takes a Character-like object with optional fields and uses the prompt processor
        to generate missing fields, creating a consistent and interesting character.

        Args:
            partial_character: Dictionary with optional character fields

        Returns:
            Complete Character object with all fields populated

        Raises:
            ValueError: If the generated character data is invalid
        """
        # Start with the provided partial data
        character_data = dict(partial_character)

        # Identify missing required and optional fields
        missing_fields = self._identify_missing_fields(character_data)

        if missing_fields:
            # Generate missing fields using the prompt processor
            generated_data = self._generate_missing_fields(character_data, missing_fields)
            character_data.update(generated_data)

        # Create Character object and validate through character manager
        self.character_manager.validate_character_data(character_data)

        return Character.from_dict(character_data)

    def generate_and_save(self, partial_character: dict[str, Any]) -> tuple[Character, str]:
        """
        Generate a complete character and save it to file.

        Args:
            partial_character: Dictionary with optional character fields

        Returns:
            Tuple of (Character object, filename)

        Raises:
            ValueError: If the generated character data is invalid
            FileExistsError: If character file already exists
        """
        character = self.generate(partial_character)
        character_dict = character.model_dump()

        filename = self.character_manager.create_character_file(character_dict)

        return character, filename

    def _identify_missing_fields(self, character_data: dict[str, Any]) -> list[str]:
        """Identify which character fields are missing or empty."""
        all_fields = ["name", "tagline", "backstory", "personality", "appearance", "relationships", "key_locations", "setting_description"]

        missing_fields = []
        for field in all_fields:
            value = character_data.get(field)
            if not value or (isinstance(value, str | list | dict) and not value):
                missing_fields.append(field)

        return missing_fields

    def _generate_missing_fields(self, existing_data: dict[str, Any], missing_fields: list[str]) -> dict[str, Any]:
        """Generate values for missing character fields using the prompt processor."""
        system_prompt = self._build_character_generation_prompt()

        # Build user prompt with existing data and requested fields
        user_prompt = self._build_user_prompt(existing_data, missing_fields)

        # Use prompt processor to generate the missing fields
        generated_character = self.prompt_processor.respond_with_model(prompt=system_prompt, user_prompt=user_prompt, output_type=Character, max_tokens=2000)

        # Extract only the requested missing fields
        generated_data = {}
        character_dict = generated_character.model_dump()

        for field in missing_fields:
            if field in character_dict and character_dict[field]:
                generated_data[field] = character_dict[field]

        return generated_data

    def _build_character_generation_prompt(self) -> str:
        """Build the system prompt for character generation."""
        return """You are an expert character creator for role-playing scenarios. Your task is to generate engaging, consistent, and interesting character details.

Guidelines:
- Create characters that are compelling and have depth
- Ensure all character details are consistent with each other
- Make characters feel authentic and relatable
- Include interesting quirks and flaws that make characters memorable
- Consider how different aspects of the character (backstory, personality, appearance) interconnect
- Create characters suitable for role-playing interactions
- If relationships are needed, make them meaningful and specific
- If locations are needed, make them relevant to the character's story

Always output a complete Character object with all requested fields filled in thoughtfully."""

    def _build_user_prompt(self, existing_data: dict[str, Any], missing_fields: list[str]) -> str:
        """Build the user prompt with existing character data and missing field requests."""
        prompt_parts = []

        if existing_data:
            prompt_parts.append("Existing character information:")
            for key, value in existing_data.items():
                if value:  # Only include non-empty values
                    prompt_parts.append(f"- {key}: {value}")
            prompt_parts.append("")

        prompt_parts.append(f"Please generate the following missing character fields: {', '.join(missing_fields)}")

        if existing_data:
            prompt_parts.append("\nEnsure all generated fields are consistent with the existing character information.")
        else:
            prompt_parts.append("\nCreate an engaging, original character with interesting details.")

        return "\n".join(prompt_parts)
