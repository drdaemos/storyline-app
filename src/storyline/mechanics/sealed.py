"""The sealed mechanic: notes only the writer reads by default, kept in the story's ``sealed/`` folder."""

from collections.abc import Mapping
from pathlib import Path

from storyline.mechanics.base import Mechanic


class SealedMechanic(Mechanic):
    """Tells the writer to keep what is hidden from the user in sealed lore files."""

    id = "sealed"
    description = "Hidden notes in sealed files, which the user opens only past a spoiler warning."
    prompt_path = Path(__file__).with_name("sealed.md")

    def seals(self, tool_name: str, arguments: Mapping[str, object]) -> bool:
        """Listing the lore lists the sealed files' summaries too."""
        return tool_name == "list_lore"
