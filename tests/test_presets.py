"""Tests for the bundled story presets and the preset package format."""

from pathlib import Path

import pytest

from storyline.agent.writer import WRITER_INSTRUCTIONS, writer_prompt_version
from storyline.presets import BUNDLED_PRESETS, DEFAULT_PRESET_ID, Preset, PresetError, load_presets
from storyline.workspace import StorySetup

VALID_HEADER = "---\nname: {name}\ntitle: A title\ndescription: A description.\nmechanics: []\n---\n"


def _write_preset(root: Path, name: str, text: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "preset.md").write_text(text, encoding="utf-8")


def test_bundled_presets_include_co_writing_as_the_default() -> None:
    preset = BUNDLED_PRESETS.get(DEFAULT_PRESET_ID)

    assert preset.id == "co-writing"
    assert preset.title.strip() and preset.description.strip() and preset.layer.strip()
    assert preset.mechanics == ()
    assert preset.skills_dir is None
    assert next(iter(BUNDLED_PRESETS)).id == DEFAULT_PRESET_ID


def test_the_default_preset_id_matches_the_default_story_setup() -> None:
    assert StorySetup().preset == DEFAULT_PRESET_ID


def test_an_unknown_preset_is_refused_naming_the_known_ones() -> None:
    with pytest.raises(PresetError, match="co-writing"):
        BUNDLED_PRESETS.get("nonexistent")


def test_a_valid_package_loads_with_its_skills_directory(tmp_path: Path) -> None:
    _write_preset(tmp_path, "mine", VALID_HEADER.format(name="mine") + "Layer text.\n")
    (tmp_path / "mine" / "skills" / "extra").mkdir(parents=True)
    _write_preset(tmp_path, "co-writing", VALID_HEADER.format(name="co-writing") + "Default layer.\n")

    catalog = load_presets(tmp_path)

    assert [preset.id for preset in catalog] == ["co-writing", "mine"]
    assert catalog.get("mine") == Preset(id="mine", title="A title", description="A description.", mechanics=(), layer="Layer text.", skills_dir=tmp_path / "mine" / "skills")


@pytest.mark.parametrize(
    "text",
    [
        "No header, just text.\n",
        "---\nname: other\ntitle: T\ndescription: D\nmechanics: []\n---\nBody.\n",
        VALID_HEADER.format(name="broken") + "   \n",
        "---\nname: broken\ntitle: ' '\ndescription: D\nmechanics: []\n---\nBody.\n",
        "---\nname: broken\ntitle: T\nmechanics: []\n---\nBody.\n",
        "---\nname: broken\ntitle: T\ndescription: D\nmechanics: sealed\n---\nBody.\n",
        "---\nname: broken\ntitle: T\ndescription: D\nmechanics: [1]\n---\nBody.\n",
    ],
    ids=["no-header", "name-mismatch", "empty-body", "blank-title", "missing-description", "mechanics-not-a-list", "mechanics-not-strings"],
)
def test_an_invalid_package_is_refused(tmp_path: Path, text: str) -> None:
    _write_preset(tmp_path, "broken", text)

    with pytest.raises(PresetError):
        load_presets(tmp_path)


def test_the_prompt_version_covers_the_core_and_the_layer() -> None:
    co_writing = BUNDLED_PRESETS.get(DEFAULT_PRESET_ID)
    other = Preset(id="other", title="T", description="D", mechanics=(), layer="A different layer.", skills_dir=None)

    assert writer_prompt_version(WRITER_INSTRUCTIONS, co_writing) == writer_prompt_version(WRITER_INSTRUCTIONS, co_writing)
    assert writer_prompt_version(WRITER_INSTRUCTIONS, co_writing) != writer_prompt_version(WRITER_INSTRUCTIONS, other)
    assert writer_prompt_version(WRITER_INSTRUCTIONS, co_writing) != writer_prompt_version("Another core.", co_writing)
