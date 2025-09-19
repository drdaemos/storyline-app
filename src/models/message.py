from typing import Literal, TypedDict


class CacheControl(TypedDict):
    type: str
    ttl: str | None

class ContentObject(TypedDict):
    text: str
    type: str
    cache_control: CacheControl | None

type ClaudeContent = str | list[ContentObject]

class ClaudeMessage(TypedDict):
    role: str
    content: ClaudeContent

class GenericMessage(TypedDict):
    role: Literal["user", "assistant", "system", "developer"]
    content: str
    type: Literal["conversation", "evaluation", "summary"]
    created_at: str
