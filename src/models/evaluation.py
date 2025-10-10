from pydantic import BaseModel, Field


class Evaluation(BaseModel):
    """Pydantic model for representing a message evaluation result in the role-playing interaction."""

    # Basic information
    patterns_to_avoid: str = Field(..., min_length=1, description="Patterns to avoid in future responses")
    status_update: str = Field(..., min_length=1, description="Evaluation of the previous interaction and new user message")
    time_passed: str = Field(..., min_length=1, description="Time passed during the last interaction")
    user_name: str = Field("", description="User name in the story, if it was introduced")

    def to_string(self) -> str:
        """Convert the evaluation to a readable string format."""
        return (
            f"## Patterns to Avoid: \n{self.patterns_to_avoid}\n"
            f"## Scene Evaluation: \n{self.status_update}\n"
            f"## Time Passed: {self.time_passed}\n"
            f"## User Name: {self.user_name if self.user_name else 'N/A'}"
        )
