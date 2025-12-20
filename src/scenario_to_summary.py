"""Module for converting scenario data to initial StorySummary."""

from src.models.summary import (
    EmotionalState,
    PlotTracking,
    RelationshipState,
    StorySummary,
    TimeState,
)


def create_initial_summary_from_scenario(
    scenario_data: dict,
    character_name: str,
    persona_name: str = "User",
) -> StorySummary:
    """
    Create the first StorySummary from scenario fields.

    This programmatically builds a summary structure from scenario metadata,
    transforming generative scaffolding into runtime state.

    Args:
        scenario_data: The scenario dict containing fields like plot_hooks, stakes, etc.
        character_name: Name of the AI character
        persona_name: Name of the user's persona character

    Returns:
        A StorySummary with scenario data mapped to appropriate fields
    """
    # Extract scenario fields with defaults
    plot_hooks = scenario_data.get("plot_hooks", [])
    stakes = scenario_data.get("stakes", "")
    character_goals = scenario_data.get("character_goals", {})
    atmosphere = scenario_data.get("atmosphere", "")
    time_context = scenario_data.get("time_context", "Day 1, beginning")
    location = scenario_data.get("location", "Unknown location")

    # Transform plot_hooks into ongoing_plots
    # Reword from meta story structure to active tensions
    ongoing_plots = []
    for hook in plot_hooks[:3]:  # Max 3 threads
        # Transform from "secret threatens to surface" style to "active tension observable in scene"
        # Keep it factual and observable rather than meta
        if hook:
            # Simple transformation: make it feel like an active thread rather than a story hook
            if not hook.endswith((".", "!", "?")):
                hook = hook + " is present in the dynamic"
            ongoing_plots.append(hook)

    # Use stakes to inform story_beats
    story_beats = []
    if stakes:
        story_beats.append(f"Stakes: {stakes}")

    # Transform character_goals into emotional_state entries
    emotional_states = []

    # Add AI character emotional state
    ai_goal = character_goals.get(character_name, "")
    ai_emotions = atmosphere if atmosphere else "Present and engaged"
    ai_wants = ""
    if ai_goal:
        # Transform "Find the truth" → "Driven to uncover the truth"
        ai_wants = f"Internally focused on: {ai_goal.lower()}"

    emotional_states.append(
        EmotionalState(
            character_name=character_name,
            character_emotions=ai_emotions,
            character_wants=ai_wants if ai_wants else None,
        )
    )

    # Add user persona emotional state if goals exist
    if persona_name in character_goals:
        user_goal = character_goals[persona_name]
        user_wants = f"Internally focused on: {user_goal.lower()}"
        emotional_states.append(
            EmotionalState(
                character_name=persona_name,
                character_emotions=atmosphere if atmosphere else "Present and engaged",
                character_wants=user_wants,
            )
        )

    # Build the summary
    return StorySummary(
        time=TimeState(current_time=time_context),
        relationship=RelationshipState(
            trust=5,  # Neutral starting point
            attraction=5,
            emotional_intimacy=5,
            conflict=5,
            power_balance=5,
            relationship_label="New interaction",
        ),
        plot=PlotTracking(
            ongoing_plots=ongoing_plots,
            resolved_outcomes=[],
            location=location,
            notable_objects=None,
        ),
        physical_state=[],  # Will be filled by first summarization
        emotional_state=emotional_states,
        story_beats=story_beats,
        user_learnings=[],
        ai_quality_issues=[],
        character_goals=character_goals,  # Preserve for summarizer
    )
