from typing import List, Optional
from pydantic import BaseModel, Field


# class Summary(BaseModel):
#     """Pydantic model for representing a summary in the role-playing interaction."""

#     # Basic information
#     story_information: str = Field(..., description="")
#     story_summary: list[str] = Field(default_factory=list, description="Story details")
#     narrative_overview: str = Field(..., description="")
#     character_learnings: list[str] = Field(default_factory=list, description="Important locations for the character")

#     def to_string(self) -> str:
#         """Convert the evaluation to a readable string format."""
#         return f"""
# Story Information:
# {self.story_information}

# Direct user instructions or corrections (meta-commentary, adhere to these in future interactions):
# {'\n'.join(self.character_learnings)}

# Previous events:
# {'\n'.join(self.story_summary)}

# Bad patterns to avoid in future:
# {self.narrative_overview}
# """.strip()

class TimeState(BaseModel):
    """Tracks temporal progression in the story"""
    current_time: str = Field(
        ..., 
        description=(
            "Current story time in dateparser-compatible format. Use ONE of these patterns:\n"
            "- Relative: 'Day 5, morning' | 'Day 5, 2:30 PM' | 'Day 5, late evening'\n"
            "- Absolute (if story established dates): 'June 15th 2024, morning' | 'Monday June 15th 2024, 3:00 PM'\n"
            "Be as specific as story content allows"
        )
    )


class RelationshipState(BaseModel):
    """Tracks relationship between characters on 1-10 scales"""
    
    trust: int = Field(
        ...,
        ge=1,
        le=10,
        description="1=complete distrust/betrayed, 5=neutral/uncertain, 10=absolute trust"
    )
    
    attraction: int = Field(
        ...,
        ge=1,
        le=10,
        description="1=repulsed/none, 5=neutral/uncertain, 10=intense desire. Use 5 if not applicable to genre"
    )
    
    emotional_intimacy: int = Field(
        ...,
        ge=1,
        le=10,
        description="1=complete strangers/guarded, 5=friendly/surface-level, 10=deeply vulnerable/no barriers"
    )
    
    conflict: int = Field(
        ...,
        ge=1,
        le=10,
        description="1=harmonious/aligned, 5=minor tension, 10=intense opposition/fighting"
    )
    
    power_balance: int = Field(
        ...,
        ge=1,
        le=10,
        description="1=user character completely controls dynamic, 5=equal partnership, 10=ai character completely controls dynamic"
    )
    
    relationship_label: str = Field(
        ..., 
        description="Current status in plain language (e.g., 'strangers', 'colleagues', 'friends', 'dating', 'enemies', 'it's complicated')"
    )

    def to_string(self) -> str:
        return f"""
Relationship Status:
- Label: {self.relationship_label}
- Trust (1: complete distrust/betrayed, 5: neutral/uncertain, 10: absolute trust): {self.trust}/10
- Attraction (1: repulsed/none, 5: neutral/uncertain, 10: intense desire): {self.attraction}/10
- Emotional Intimacy (1: complete strangers/guarded, 5: friendly/surface-level, 10: deeply vulnerable/no barriers): {self.emotional_intimacy}/10
- Conflict (1: harmonious/aligned, 5: minor tension, 10: intense opposition/fighting): {self.conflict}/10
- Power Balance (1: user character completely controls dynamic, 5: equal partnership, 10: ai character completely controls dynamic): {self.power_balance}/10
"""


class PlotTracking(BaseModel):
    """Simple plot tracking - ongoing and resolved"""
    ongoing_plots: List[str] = Field(
        default_factory=list,
        description="Active plot threads as brief, factual descriptions (e.g., 'Investigating the murder', 'Completing big work commission', 'Planning the heist'). Max 3 threads."
    )
    resolved_outcomes: List[str] = Field(
        default_factory=list,
        description="Plot resolutions and their outcomes (e.g., 'Murder solved: victim's partner was the killer', 'Work commission completed successfully')"
    )
    location: str = Field(
        ..., 
        description="Where characters are right now (e.g., '<character's> workshop', '<character's> apartment bedroom', 'coffee shop'. If they are separate, list both locations with reference to character)"
    )
    notable_objects: Optional[str] = Field(
        None,
        description="Only objects actively in use or plot-relevant (e.g., 'bloodied knife on table', 'engagement ring in pocket', 'timer counting down N minutes')"
    )

    def to_string(self) -> str:
        return f"""
Ongoing plot threads:
{'\n'.join(self.ongoing_plots) if self.ongoing_plots else 'None'}
Resolved plot outcomes:
{'\n'.join(self.resolved_outcomes) if self.resolved_outcomes else 'None'}

In-story location: {self.location}
Plot-relevant objects: {self.notable_objects or 'none'}
"""


class PhysicalState(BaseModel):
    """Physical positioning and state - be precise enough to resume scene"""
    character_name: str = Field(..., description="Name of the character")
    character_position: str = Field(
        ...,
        description="Exact physical position of the character (e.g., '<character> sitting at desk, <character> standing behind', 'both lying in bed', 'facing each other across table')"
    )
    clothing_status: Optional[str] = Field(
        None, 
        description="Only if relevant/changed (e.g., 'fully dressed', '<character> shirtless', '<character> in towel')"
    )
    physical_contact: Optional[str] = Field(
        None, 
        description="Any ongoing touch/contact (e.g., '<character>'s hand on <character>'s shoulder', 'embracing', 'no contact')"
    )
    conditions: Optional[str] = Field(
        None, 
        description="Physical conditions affecting the character (e.g., 'injured leg, limping', 'exhausted, struggling to stay awake', 'healthy and alert')"
    )

    def to_string(self) -> str:
        return f"""{self.character_name}: 
- Physical position: {self.character_position},
- Clothing: {self.clothing_status or 'unknown'}, 
- Ongoing touch/contact: {self.physical_contact or 'none'}, 
- Physical conditions: {self.conditions or 'none'}"
"""
    

class EmotionalState(BaseModel):
    character_name: str = Field(..., description="Name of the character")
    """Character emotional states - ONLY major shifts, leave fields None if unchanged"""
    character_emotions: Optional[str] = Field(
        None,
        description="Character's emotional state"
    )
    character_wants: Optional[str] = Field(
        None,
        description="What the character currently desires or aims for in story (short-term)"
    )

    def to_string(self) -> str:
        return f"""{self.character_name}: 
- Emotional state: {self.character_emotions or 'neutral'},
- Current desires/aims: {self.character_wants or 'unknown'}
"""


class QualityIssue(BaseModel):
    """AI quality problems detected"""
    issue_type: str = Field(
        ...,
        description="Specific type: 'repetitive_phrase', 'echoing_user', 'purple_prose', 'character_sheet_fixation', 'physical_impossibility', 'over_analysis'"
    )
    example: str = Field(
        ...,
        description="Direct quote or specific description of the problem"
    )

    def to_string(self) -> str:
        return f"- {self.issue_type}: {self.example}"


class StorySummary(BaseModel):
    """Complete story state summary"""
    time: TimeState
    relationship: RelationshipState
    plot: PlotTracking
    physical_state: List[PhysicalState] = Field(
        default_factory=list,
        description="One entry per character being tracked"
    )
    emotional_state: List[EmotionalState] = Field(
        default_factory=list,
        description="One entry per character being tracked"
    )
    
    story_beats: List[str] = Field(
        default_factory=list,
        description="Maximum 5 beats - only events that would matter when resuming scene later"
    )
    
    user_learnings: List[str] = Field(
        default_factory=list,
        description="Accumulated learnings about user preferences from OOC commands or behavior patterns"
    )
    
    ai_quality_issues: List[QualityIssue] = Field(
        default_factory=list,
        description="Only populate if problems detected in the conversation"
    )

    def to_string(self) -> str:
        """Convert the summary to a prompt string."""
        return f"""
Current in-story time: {self.time.current_time}
{self.plot.to_string()}

Previous events:
{'\n'.join(self.story_beats)}

Direct user instructions or corrections (meta-commentary, you MUST adhere to these in future interactions):
{'\n'.join(self.user_learnings)}

Story quality issues that must be avoided:
{'\n'.join(issue.to_string() for issue in self.ai_quality_issues) if self.ai_quality_issues else 'None'}

Characters physical states:
{'\n'.join(state.to_string() for state in self.physical_state) if self.physical_state else 'Unknown'}

Characters emotional states:
{'\n'.join(state.to_string() for state in self.emotional_state) if self.emotional_state else 'Unknown'}

Relationship between characters:
{self.relationship.to_string()}
""".strip()