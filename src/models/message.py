from collections.abc import Iterable
from typing import Literal, NotRequired, TypedDict

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
    role: Literal["user", "assistant", "system", "developer"]
    content: str
    type: Literal["conversation", "evaluation", "summary"]
    created_at: str
    meta_text: NotRequired[str | None]
