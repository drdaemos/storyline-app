"""Turning a preset into the setup record of a new story."""

from collections.abc import Mapping

from storyline.mechanics import MECHANICS, Mechanic, MechanicError, resolve_mechanics
from storyline.presets.catalog import Preset, PresetError
from storyline.workspace import StorySetup


def setup_for(preset: Preset, registry: Mapping[str, Mechanic] = MECHANICS) -> StorySetup:
    """Return the setup for a story created as ``preset``, with its mechanics resolved in full; raise ``PresetError`` when one is unknown."""
    try:
        mechanics = resolve_mechanics(preset.mechanics, registry)
    except MechanicError as error:
        raise PresetError(f"Preset {preset.id!r} cannot be used: {error}") from error
    return StorySetup(preset=preset.id, mechanics=tuple(mechanic.id for mechanic in mechanics))
