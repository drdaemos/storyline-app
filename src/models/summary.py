import re

from pydantic import BaseModel, Field


class TimeState(BaseModel):
    """Tracks temporal progression in the story."""

    current_time: str = Field(
        ...,
        description=(
            "Current story time in dateparser-compatible format. Use ONE of these patterns:\n"
            "- Relative: 'Day 5, morning' | 'Day 5, 2:30 PM' | 'Day 5, late evening'\n"
            "- Absolute: 'June 15th 2024, morning' | 'Monday June 15th 2024, 3:00 PM'"
        ),
    )


class RelationshipState(BaseModel):
    """Tracks relationship between characters on 1-10 scales."""

    trust: int = Field(..., ge=1, le=10)
    attraction: int = Field(..., ge=1, le=10)
    emotional_intimacy: int = Field(..., ge=1, le=10)
    conflict: int = Field(..., ge=1, le=10)
    power_balance: int = Field(..., ge=1, le=10)
    relationship_label: str = Field(...)

    def to_string(self) -> str:
        return (
            "Relationship Status:\n"
            f"- Label: {self.relationship_label}\n"
            f"- Trust: {self.trust}/10\n"
            f"- Attraction: {self.attraction}/10\n"
            f"- Emotional Intimacy: {self.emotional_intimacy}/10\n"
            f"- Conflict: {self.conflict}/10\n"
            f"- Power Balance: {self.power_balance}/10\n"
        )


class PlotTracking(BaseModel):
    """Simple plot tracking - ongoing and resolved."""

    ongoing_plots: list[str] = Field(default_factory=list)
    resolved_outcomes: list[str] = Field(default_factory=list)
    location: str = Field(...)
    notable_objects: str | None = Field(default=None)

    def to_string(self) -> str:
        ongoing = "\n".join(self.ongoing_plots) if self.ongoing_plots else "None"
        resolved = "\n".join(self.resolved_outcomes) if self.resolved_outcomes else "None"
        return (
            "Ongoing plot threads:\n"
            f"{ongoing}\n"
            "Resolved plot outcomes:\n"
            f"{resolved}\n\n"
            f"In-story location: {self.location}\n"
            f"Plot-relevant objects: {self.notable_objects or 'none'}\n"
        )


class PhysicalState(BaseModel):
    """Physical positioning and state."""

    character_name: str = Field(...)
    character_position: str = Field(...)
    clothing_status: str | None = Field(default=None)
    physical_contact: str | None = Field(default=None)
    conditions: str | None = Field(default=None)

    def to_string(self) -> str:
        return (
            f"{self.character_name}:\n"
            f"- Physical position: {self.character_position}\n"
            f"- Clothing: {self.clothing_status or 'unknown'}\n"
            f"- Ongoing touch/contact: {self.physical_contact or 'none'}\n"
            f"- Physical conditions: {self.conditions or 'none'}\n"
        )


class EmotionalState(BaseModel):
    character_name: str = Field(...)
    character_emotions: str | None = Field(default=None)
    character_wants: str | None = Field(default=None)

    def to_string(self) -> str:
        return (
            f"{self.character_name}:\n"
            f"- Emotional state: {self.character_emotions or 'neutral'}\n"
            f"- Current desires/aims: {self.character_wants or 'unknown'}\n"
        )


class QualityIssue(BaseModel):
    """AI quality problems detected."""

    issue_type: str = Field(...)
    example: str = Field(...)

    def to_string(self) -> str:
        return f"- {self.issue_type}: {self.example}"


class StorySummary(BaseModel):
    """Complete story state summary."""

    time: TimeState
    relationship: RelationshipState
    plot: PlotTracking
    physical_state: list[PhysicalState] = Field(default_factory=list)
    emotional_state: list[EmotionalState] = Field(default_factory=list)
    story_beats: list[str] = Field(default_factory=list)
    user_learnings: list[str] = Field(default_factory=list)
    ai_quality_issues: list[QualityIssue] = Field(default_factory=list)
    character_goals: dict[str, str] = Field(default_factory=dict)

    @property
    def story_summary(self) -> list[str]:
        """Legacy compatibility alias."""
        return self.story_beats

    @property
    def character_learnings(self) -> list[str]:
        """Legacy compatibility alias."""
        return self.user_learnings

    @classmethod
    def from_legacy_text(cls, summary_text: str) -> "StorySummary":
        """Build a minimal structured summary from legacy/plain-text summary payloads."""
        beats = re.findall(r"<story_summary>(.*?)</story_summary>", summary_text, flags=re.IGNORECASE | re.DOTALL)
        learnings = re.findall(r"<character_learnings>(.*?)</character_learnings>", summary_text, flags=re.IGNORECASE | re.DOTALL)

        cleaned_beats = [item.strip() for item in beats if item.strip()]
        cleaned_learnings = [item.strip() for item in learnings if item.strip()]

        if not cleaned_beats and summary_text.strip():
            cleaned_beats = [summary_text.strip()]

        return cls(
            time=TimeState(current_time="Unknown"),
            relationship=RelationshipState(
                trust=5,
                attraction=5,
                emotional_intimacy=5,
                conflict=1,
                power_balance=5,
                relationship_label="",
            ),
            plot=PlotTracking(location="unknown"),
            story_beats=cleaned_beats,
            user_learnings=cleaned_learnings,
        )

    def to_string(self) -> str:
        beats = "\n".join(self.story_beats)
        learnings = "\n".join(self.user_learnings)
        issues = "\n".join(issue.to_string() for issue in self.ai_quality_issues) if self.ai_quality_issues else "None"
        physical = "\n".join(state.to_string() for state in self.physical_state) if self.physical_state else "Unknown"
        emotional = "\n".join(state.to_string() for state in self.emotional_state) if self.emotional_state else "Unknown"
        return (
            f"Current in-story time: {self.time.current_time}\n"
            f"{self.plot.to_string()}\n"
            "Previous events:\n"
            f"{beats}\n\n"
            "Direct user instructions or corrections:\n"
            f"{learnings}\n\n"
            "Story quality issues that must be avoided:\n"
            f"{issues}\n\n"
            "Characters physical states:\n"
            f"{physical}\n\n"
            "Characters emotional states:\n"
            f"{emotional}\n\n"
            "Relationship between characters:\n"
            f"{self.relationship.to_string()}"
        ).strip()


class Summary(BaseModel):
    """Legacy summary model retained for compatibility with older pipeline/tests."""

    story_information: str = Field(default="")
    story_summary: list[str] = Field(default_factory=list)
    character_learnings: list[str] = Field(default_factory=list)
    narrative_overview: str = Field(default="")

    def to_string(self) -> str:
        story_summary = "\n".join(self.story_summary) if self.story_summary else "None"
        learnings = "\n".join(self.character_learnings) if self.character_learnings else "None"
        return (
            "Story information:\n"
            f"{self.story_information}\n\n"
            "Story summary:\n"
            f"{story_summary}\n\n"
            "Character learnings:\n"
            f"{learnings}\n\n"
            "Narrative overview:\n"
            f"{self.narrative_overview}"
        )
