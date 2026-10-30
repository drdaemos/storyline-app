"""The mechanic contract: one unit of machinery a story can run with.

A mechanic adds to the writer what its kind of story needs: a prompt section, tools, skills and a section of the
per-turn story snapshot. Which mechanics a story uses is recorded in its ``story.json``; the agent assembles the
mechanics of the story for every run. See ``agent-specs/story-presets.md``.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import ClassVar

from pydantic_ai import FunctionToolset

from storyline.workspace import Story


class MechanicError(ValueError):
    """Raised when a mechanic id is unknown."""


class Mechanic:
    """A mechanic contributes nothing until a subclass says otherwise; subclasses set the class attributes they need."""

    id: ClassVar[str]
    """Stable id, as presets and ``story.json`` name it, e.g. ``sealed``."""
    description: ClassVar[str]
    """One sentence on what the mechanic does, shown to the writer when it considers enabling one."""
    requires: ClassVar[tuple[str, ...]] = ()
    """Ids of mechanics this one needs; they are enabled with it."""
    prompt_path: ClassVar[Path | None] = None
    """Markdown added to the writer's instructions in every run of a story that uses the mechanic."""
    toolset: FunctionToolset[Story] | None = None
    """The tools added to the writer. A class attribute for a mechanic whose tools need nothing from an instance, otherwise built per instance."""
    skills_dir: ClassVar[Path | None] = None
    """A skill library (``<name>/SKILL.md`` directories) added to the story's skill catalog."""

    @property
    def prompt(self) -> str:
        """The mechanic's prompt section, or an empty string when it has none."""
        return self.prompt_path.read_text(encoding="utf-8").strip() if self.prompt_path is not None else ""

    async def snapshot_section(self, story: Story) -> list[str]:
        """Lines added to the per-turn story snapshot; none by default."""
        return []

    def seals(self, tool_name: str, arguments: Mapping[str, object]) -> bool:
        """Whether a call of this tool reads or changes what is hidden from the user, so interfaces fold it."""
        return False


def resolve_mechanics(ids: Iterable[str], registry: Mapping[str, Mechanic]) -> tuple[Mechanic, ...]:
    """Return the named mechanics with everything they require, each once, requirements before what needs them.

    Raise ``MechanicError`` for an unknown id.
    """
    resolved: dict[str, Mechanic] = {}
    adding: set[str] = set()

    def add(mechanic_id: str, needed_by: str | None) -> None:
        if mechanic_id in resolved:
            return
        if mechanic_id in adding:
            raise MechanicError(f"Mechanic {mechanic_id!r} requires itself through {needed_by!r}.")
        mechanic = registry.get(mechanic_id)
        if mechanic is None:
            known = ", ".join(registry) or "none"
            context = f" (needed by {needed_by})" if needed_by else ""
            raise MechanicError(f"Unknown mechanic {mechanic_id!r}{context}. Known mechanics: {known}.")
        adding.add(mechanic_id)
        for requirement in mechanic.requires:
            add(requirement, mechanic_id)
        resolved[mechanic_id] = mechanic

    for mechanic_id in ids:
        add(mechanic_id, None)
    return tuple(resolved.values())
