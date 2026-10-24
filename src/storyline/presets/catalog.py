"""Story presets: the bundled kinds of story and how the writer works together with the user on each."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_PRESET_ID = "co-writing"
PRESETS_PATH = Path(__file__).parent
PRESET_FILENAME = "preset.md"
PRESET_SKILLS_DIRNAME = "skills"


class PresetError(ValueError):
    """Raised when a preset package is invalid or a preset id is unknown."""


@dataclass(frozen=True)
class Preset:
    """One kind of story: its picker text, its mechanics and the relationship layer of the writer's prompt."""

    id: str
    title: str
    description: str
    mechanics: tuple[str, ...]
    layer: str
    """The Markdown body of ``preset.md``: how the writer and the user share the work on this kind of story."""
    skills_dir: Path | None
    """The preset's own skills, which add to or override the core skills; None when it has none."""


@dataclass(frozen=True)
class PresetCatalog:
    """A set of presets, listed with the default preset first and the rest by id."""

    presets: Mapping[str, Preset]

    def get(self, preset_id: str) -> Preset:
        """Return the preset with this id; raise ``PresetError`` when there is none."""
        try:
            return self.presets[preset_id]
        except KeyError:
            known = ", ".join(self.presets) or "none"
            raise PresetError(f"Unknown story preset {preset_id!r}. Known presets: {known}.") from None

    def __iter__(self) -> Iterator[Preset]:
        return iter(self.presets.values())

    def __len__(self) -> int:
        return len(self.presets)

    def __contains__(self, preset_id: object) -> bool:
        return preset_id in self.presets


def load_presets(root: Path = PRESETS_PATH) -> PresetCatalog:
    """Load every preset package (a directory holding ``preset.md``) under ``root``; raise ``PresetError`` for an invalid one."""
    loaded = {path.parent.name: _load_preset(path) for path in sorted(root.glob(f"*/{PRESET_FILENAME}"))}
    ordered = sorted(loaded, key=lambda preset_id: (preset_id != DEFAULT_PRESET_ID, preset_id))
    return PresetCatalog(presets={preset_id: loaded[preset_id] for preset_id in ordered})


def _load_preset(path: Path) -> Preset:
    directory = path.parent
    header, body = _split_frontmatter(path)
    name = _required_text(header, "name", path)
    if name != directory.name:
        raise PresetError(f"{path}: name {name!r} must equal the directory name {directory.name!r}.")
    mechanics = header.get("mechanics", [])
    if not isinstance(mechanics, list) or not all(isinstance(item, str) for item in mechanics):
        raise PresetError(f"{path}: mechanics must be a list of mechanic ids.")
    layer = body.strip()
    if not layer:
        raise PresetError(f"{path}: the preset has no text after its header.")
    skills_dir = directory / PRESET_SKILLS_DIRNAME
    return Preset(
        id=name,
        title=_required_text(header, "title", path),
        description=_required_text(header, "description", path),
        mechanics=tuple(mechanics),
        layer=layer,
        skills_dir=skills_dir if skills_dir.is_dir() else None,
    )


def _split_frontmatter(path: Path) -> tuple[dict[str, object], str]:
    parts = path.read_text(encoding="utf-8").split("---\n", 2)
    if len(parts) != 3 or parts[0].strip():
        raise PresetError(f"{path}: the file must start with a --- delimited header.")
    try:
        header = yaml.safe_load(parts[1])
    except yaml.YAMLError as error:
        raise PresetError(f"{path}: the header is not valid YAML: {error}") from error
    if not isinstance(header, dict):
        raise PresetError(f"{path}: the header must be a mapping.")
    return header, parts[2]


def _required_text(header: dict[str, object], key: str, path: Path) -> str:
    value = header.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PresetError(f"{path}: {key} is required and must be non-empty text.")
    return value.strip()
