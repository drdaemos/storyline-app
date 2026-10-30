"""The cast mechanic: sealed sheets for the characters the writer plays."""

from pathlib import Path

from storyline.mechanics.base import Mechanic


class CastMechanic(Mechanic):
    """Tells the writer to commit to what each character wants in a sealed cast sheet, and adds the skill for writing one."""

    id = "cast"
    description = "Every character who matters gets a sealed cast sheet, so their wants and limits are fixed before the user is in the room."
    requires = ("sealed",)
    prompt_path = Path(__file__).with_name("cast.md")
    skills_dir = Path(__file__).with_name("cast") / "skills"
