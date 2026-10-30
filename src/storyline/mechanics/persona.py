"""The persona mechanic: the user plays one character, whose sheet is persona.md."""

from pathlib import Path

from storyline.mechanics.base import Mechanic


class PersonaMechanic(Mechanic):
    """Tells the writer to keep the sheet of the character the user plays."""

    id = "persona"
    description = "The user plays one character, kept on a sheet (persona.md) that the writer updates after every scene."
    prompt_path = Path(__file__).with_name("persona.md")
