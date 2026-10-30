"""Which tool calls touch what is hidden from the user, so interfaces can fold them."""

from collections.abc import Mapping, Sequence

from storyline.agent.writer_tools import LORE_WRITING_TOOL_NAMES
from storyline.mechanics import Mechanic
from storyline.workspace.file_story import SEALED_DIRNAME

LORE_FILE_TOOL_NAMES = LORE_WRITING_TOOL_NAMES | {"read_lore"}
"""The core tools that name one lore file in their ``filename`` argument."""
INVALID_JSON_KEY = "INVALID_JSON"
"""Where Pydantic AI keeps tool arguments that are not valid JSON (``ToolCallPart.args_as_dict``)."""


def tool_call_is_sealed(tool_name: str, arguments: Mapping[str, object], mechanics: Sequence[Mechanic]) -> bool:
    """Whether a call reads or changes sealed content: a core lore tool on a ``sealed/`` file, or a call one of the mechanics seals."""
    if tool_name in LORE_FILE_TOOL_NAMES and (_names_sealed_file(arguments.get("filename")) or _may_name_sealed_file(arguments.get(INVALID_JSON_KEY))):
        return True
    return any(mechanic.seals(tool_name, arguments) for mechanic in mechanics)


def _may_name_sealed_file(raw_arguments: object) -> bool:
    """Arguments that are not valid JSON cannot be parsed for a filename, so any mention of the sealed folder seals them."""
    return isinstance(raw_arguments, str) and f"{SEALED_DIRNAME}/" in raw_arguments.replace("\\\\", "/").replace("\\", "/")


def _names_sealed_file(filename: object) -> bool:
    if not isinstance(filename, str):
        return False
    return filename.strip().replace("\\", "/").startswith(f"{SEALED_DIRNAME}/")
