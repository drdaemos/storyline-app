from typing import Any

from pydantic import BaseModel, Field


class Character(BaseModel):
    """Pydantic model for representing a character in the role-playing interaction."""

    # Basic information
    name: str = Field(..., min_length=1, description="Name of the character")
    role: str = Field(..., min_length=1, description="Profession or role in the story")
    backstory: str = Field(..., min_length=1, description="Previous experiences, events and relationships")
    personality: str = Field("", description="Personality traits and characteristics")
    appearance: str = Field("", description="Physical description")
    relationships: dict[str, str] = Field(default_factory=dict, description="Relationships with other characters")
    key_locations: list[str] = Field(default_factory=list, description="Important locations for the character")
    setting_description: str = Field("", description="Description of the world/setting the character exists in")

    @classmethod
    def from_dict(cls, data: dict[str, str | Any]) -> "Character":
        """Initialize the character from a dictionary."""
        return cls(**data)
