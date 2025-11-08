from typing import Any

from pydantic import BaseModel, Field


class Character(BaseModel):
    """Pydantic model for representing a character in the role-playing interaction."""

    # Basic information
    name: str = Field(..., min_length=1, description="Name of the character")
    tagline: str = Field(..., min_length=1, description="Short tagline or description of the character")
    backstory: str = Field(..., min_length=1, description="Previous experiences, events and relationships")
    personality: str = Field("", description="Personality traits and characteristics")
    appearance: str = Field("", description="Physical description")
    relationships: dict[str, str] = Field(default_factory=dict, description="Relationships with other characters")
    key_locations: list[str] = Field(default_factory=list, description="Important locations for the character")
    setting_description: str = Field("", description="Description of the world/setting the character exists in")
    interests: list[str] = Field(default_factory=list, description="Character's interests and hobbies")
    dislikes: list[str] = Field(default_factory=list, description="Things the character dislikes")
    desires: list[str] = Field(default_factory=list, description="Character's goals and desires")
    kinks: list[str] = Field(default_factory=list, description="Character's kinks and preferences")
    is_persona: bool = Field(default=False, description="Whether this character is a persona (user character)")

    @classmethod
    def from_dict(cls, data: dict[str, str | Any]) -> "Character":
        """Initialize the character from a dictionary."""
        return cls(**data)

    def to_prompt_card(self, role: str = "Character", controller: str | None = None, include_world_info: bool = False) -> str:
        """
        Generate a formatted character card for use in prompts.

        Only includes non-empty fields. Formats lists and dicts appropriately.

        Args:
            role: The role label for this character (e.g., "Character", "User", "Persona")
            controller: Who controls this character ("AI" or "Human"). If provided, adds a clear indicator.
            include_world_info: Whether to include world information (key_locations, setting_description)

        Returns:
            A formatted string with character information
        """
        if controller:
            lines = [f"## {role}: {self.name} [Controlled by {controller}]"]
        else:
            lines = [f"## {role}: {self.name}"]

        # Add tagline if present
        if self.tagline:
            lines.append(f"**{self.tagline}**")
            lines.append("")  # Empty line for spacing

        # Add backstory (required field, always present)
        if self.backstory:
            lines.append(f"[Backstory] {self.backstory}")

        # Add optional fields only if they have values
        if self.personality:
            lines.append(f"[Personality] {self.personality}")

        if self.appearance:
            lines.append(f"[Appearance] {self.appearance}")

        if self.interests:
            lines.append(f"[Interests] {', '.join(self.interests)}")

        if self.dislikes:
            lines.append(f"[Dislikes] {', '.join(self.dislikes)}")

        if self.desires:
            lines.append(f"[Desires] {', '.join(self.desires)}")

        if self.kinks:
            lines.append(f"[Kinks] {', '.join(self.kinks)}")

        if self.relationships:
            lines.append("**Relationships:**")
            for person, relationship in self.relationships.items():
                lines.append(f"  - {person}: {relationship}")

        # Only include world info if requested (typically for AI character only)
        if include_world_info:
            if self.setting_description:
                lines.append(f"**Setting/World description:** {self.setting_description}")

            if self.key_locations:
                lines.append("**Key Locations:**")
                for location in self.key_locations:
                    lines.append(f"  - {location}")

        return "\n".join(lines)


class PartialCharacter(BaseModel):
    """Pydantic model for representing a partial character (for API requests)."""

    # Basic information
    name: str = Field(default="", description="Name of the character")
    tagline: str = Field(default="", description="Short tagline or description of the character")
    backstory: str = Field(default="", description="Previous experiences, events and relationships")
    personality: str = Field(default="", description="Personality traits and characteristics")
    appearance: str = Field(default="", description="Physical description")
    relationships: dict[str, str] = Field(default_factory=dict, description="Relationships with other characters")
    key_locations: list[str] = Field(default_factory=list, description="Important locations for the character")
    setting_description: str = Field(default="", description="Description of the world/setting the character exists in")
    interests: list[str] = Field(default_factory=list, description="Character's interests and hobbies")
    dislikes: list[str] = Field(default_factory=list, description="Things the character dislikes")
    desires: list[str] = Field(default_factory=list, description="Character's goals and desires")
    kinks: list[str] = Field(default_factory=list, description="Character's kinks and preferences")
    is_persona: bool = Field(default=False, description="Whether this character is a persona (user character)")
