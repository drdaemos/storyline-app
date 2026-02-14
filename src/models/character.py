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
    interests: list[str] = Field(default_factory=list, description="Character's interests and hobbies")
    dislikes: list[str] = Field(default_factory=list, description="Things the character dislikes")
    desires: list[str] = Field(default_factory=list, description="Character's goals and desires")
    kinks: list[str] = Field(default_factory=list, description="Character's kinks and preferences")
    is_persona: bool = Field(default=False, description="Whether this character is a persona (user character)")

    # New simulation fields — starting values per ruleset schema.
    # Set per scenario-character pairing, not at character creation time.
    starting_drives: dict[str, float] = Field(default_factory=dict, description="Initial drive values")
    starting_skills: dict[str, float] = Field(default_factory=dict, description="Initial skill values")
    starting_emotional_state: dict[str, Any] = Field(default_factory=dict, description="Initial emotional state matching ruleset schema")

    @classmethod
    def from_dict(cls, data: dict[str, str | Any]) -> "Character":
        """Initialize the character from a dictionary."""
        # Filter out removed fields for backwards compat with old character data
        known_fields = cls.model_fields.keys()
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def to_prompt_card(self, role: str = "Character", controller: str | None = None, include_world_info: bool = False) -> str:
        """
        Generate a formatted character card for use in prompts.

        Only includes non-empty fields. Formats lists and dicts appropriately.

        Args:
            role: The role label for this character (e.g., "Character", "User", "Persona")
            controller: Who controls this character ("AI" or "Human"). If provided, adds a clear indicator.

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
            lines.append(f"[Preferences] {', '.join(self.kinks)}")

        return "\n".join(lines)


class PartialCharacter(BaseModel):
    """Pydantic model for representing a partial character (for API requests)."""

    # Basic information
    name: str = Field(default="", description="Name of the character")
    tagline: str = Field(default="", description="Short tagline or description of the character")
    backstory: str = Field(default="", description="Previous experiences, events and relationships")
    personality: str = Field(default="", description="Personality traits and characteristics")
    appearance: str = Field(default="", description="Physical description")
    interests: list[str] = Field(default_factory=list, description="Character's interests and hobbies")
    dislikes: list[str] = Field(default_factory=list, description="Things the character dislikes")
    desires: list[str] = Field(default_factory=list, description="Character's goals and desires")
    kinks: list[str] = Field(default_factory=list, description="Character's kinks and preferences")
    is_persona: bool = Field(default=False, description="Whether this character is a persona (user character)")
    starting_drives: dict[str, float] = Field(default_factory=dict, description="Initial drive values")
    starting_skills: dict[str, float] = Field(default_factory=dict, description="Initial skill values")
    starting_emotional_state: dict[str, Any] = Field(default_factory=dict, description="Initial emotional state")
