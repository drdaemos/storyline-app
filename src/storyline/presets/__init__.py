"""Bundled story presets."""

from storyline.presets.catalog import DEFAULT_PRESET_ID, PRESETS_PATH, Preset, PresetCatalog, PresetError, load_presets

BUNDLED_PRESETS: PresetCatalog = load_presets()

__all__ = (
    "BUNDLED_PRESETS",
    "DEFAULT_PRESET_ID",
    "PRESETS_PATH",
    "Preset",
    "PresetCatalog",
    "PresetError",
    "load_presets",
)
