"""Bundled story presets."""

from storyline.presets.catalog import DEFAULT_PRESET_ID, PRESETS_PATH, Preset, PresetCatalog, PresetError, PresetSummary, load_presets
from storyline.presets.setup import setup_for

BUNDLED_PRESETS: PresetCatalog = load_presets()

__all__ = (
    "BUNDLED_PRESETS",
    "DEFAULT_PRESET_ID",
    "PRESETS_PATH",
    "Preset",
    "PresetCatalog",
    "PresetError",
    "PresetSummary",
    "load_presets",
    "setup_for",
)
