
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


class InteractRequest(BaseModel):
    character_name: str = Field(..., min_length=1, description="Name of the character to interact with")
    user_message: str = Field(..., min_length=1, description="User's message to the character")
    session_id: str | None = Field(None, description="Optional session ID for conversation continuity")
    processor_type: str = Field("google", description="AI processor type (google, openai, cohere, etc.)")


class SessionInfo(BaseModel):
    session_id: str
    character_name: str
    message_count: int
    last_message_time: str
    last_character_response: str | None = None


class HealthStatus(BaseModel):
    status: str
    conversation_memory: str
    summary_memory: str
    details: dict[str, str] | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str