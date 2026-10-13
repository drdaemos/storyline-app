"""JSON bodies of the HTTP API."""

from pydantic import BaseModel, ConfigDict


class CreateStoryRequest(BaseModel):
    name: str


class StoryCreated(BaseModel):
    name: str


class StoryList(BaseModel):
    stories: list[str]
    active: str | None
    """The story opened last, if it still exists."""


class PromptRequest(BaseModel):
    text: str


class Accepted(BaseModel):
    """An empty JSON object: the request was taken and its effects arrive on the events stream."""


class ModelChoice(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str


class UndoResult(BaseModel):
    undone: bool


class ScriptText(BaseModel):
    text: str


class LoreSummary(BaseModel):
    filename: str
    summary: str | None
    keywords: str | None


class LoreList(BaseModel):
    files: list[LoreSummary]


class LoreText(BaseModel):
    filename: str
    text: str
