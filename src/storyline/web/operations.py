"""Where each operation of the room protocol lives in the HTTP API."""

from collections.abc import Mapping
from types import MappingProxyType

from storyline.room import Operation

OPERATION_ROUTES: Mapping[Operation, tuple[str, str]] = MappingProxyType(
    {
        Operation.LIST_STORIES: ("GET", "/api/stories"),
        Operation.CREATE_STORY: ("POST", "/api/stories"),
        Operation.OPEN_STORY: ("GET", "/api/stories/{story}/events"),
        Operation.SEND_PROMPT: ("POST", "/api/stories/{story}/prompts"),
        Operation.INTERRUPT: ("POST", "/api/stories/{story}/interrupt"),
        Operation.SET_MODEL: ("PUT", "/api/stories/{story}/model"),
        Operation.UNDO_LAST_TURN: ("POST", "/api/stories/{story}/undo"),
        Operation.CLEAR_CONVERSATION: ("POST", "/api/stories/{story}/clear"),
        Operation.READ_SCRIPT: ("GET", "/api/stories/{story}/script"),
        Operation.LIST_LORE: ("GET", "/api/stories/{story}/lore"),
        Operation.READ_LORE: ("GET", "/api/stories/{story}/lore/{filename}"),
    }
)
