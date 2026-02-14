from collections.abc import Iterable
from typing import Literal, TypedDict

from anthropic.types import TextBlockParam


class CacheControl(TypedDict):
    type: str
    ttl: str | None


class ContentObject(TypedDict):
    text: str
    type: str
    cache_control: CacheControl | None


type ClaudeContent = str | Iterable[TextBlockParam]


class ClaudeMessage(TypedDict):
    role: str
    content: ClaudeContent


class GenericMessage(TypedDict):
    role: Literal["user", "narration", "assistant", "system", "developer"]
    content: str
    created_at: str
