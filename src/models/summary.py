from pydantic import BaseModel, Field


class Summary(BaseModel):
    """Pydantic model for representing a summary in the role-playing interaction."""

    # Basic information
    story_information: str = Field(..., description="")
    story_summary: list[str] = Field(default_factory=list, description="Story details")
    narrative_overview: str = Field(..., description="")
    character_learnings: list[str] = Field(default_factory=list, description="Important locations for the character")

    def to_string(self) -> str:
        """Convert the evaluation to a readable string format."""
        return f"""
Story Information:
{self.story_information}

Direct user instructions or corrections (meta-commentary, adhere to these in future interactions):
{'\n'.join(self.character_learnings)}

Previous events:
{'\n'.join(self.story_summary)}

Bad patterns to avoid in future:
{self.narrative_overview}
""".strip()
