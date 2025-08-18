from dataclasses import dataclass


@dataclass
class Character:
    """Class for representing a character in the role-playing interaction."""

    # Basic information
    name: str  # Name of the character
    role: str  # Profession or role in the story
    backstory: str  # Previous experiences, events and relationships
    appearance: str  # Physical description

    # Psychological state
    autonomy: str  # Independent vs. dependent
    safety: str  # Vulnerable, cautious, secure

    # Personality traits
    openmindedness: str  # Openness to new experience
    emotional_stability: str  # Calmness vs. volatility
    attachment_pattern: str  # Secure, anxious, avoidant, etc.
    conscientiousness: str  # Tendency to be organized and dependable
    sociability: str  # Extraversion vs. introversion
    social_trust: str  # Paranoid, suspicious, trusting, naive
    risk_approach: str  # Recklessness vs. risk-averseness
    conflict_approach: str  # Avoidant, accommodating, compromising, assertive, confrontational
    leadership_style: str  # Follwer, contributor, director

    # Current state variables
    stress_level: str  # Relaxed, calm, pressured, anxious, overwhelmed
    energy_level: str  # Exhausted, tired, moderate, energetic
    mood: str  # Sad, melancholic, bored, relaxed, upbeat, excited, aroused, worried, angry, frustrated

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        """Initialize the character from a dictionary."""
        return cls(**data)
