
from pydantic import BaseModel, Field

from .character import Character


class CreateCharacterRequest(BaseModel):
    """Request model for creating a character card."""
    data: Character | str = Field(
        ...,
        description="Either structured character data or freeform YAML text"
    )
    is_yaml_text: bool = Field(
        False,
        description="Set to true if 'data' contains freeform YAML text"
    )


class CreateCharacterResponse(BaseModel):
    """Response model for character creation."""
    message: str
    character_filename: str
