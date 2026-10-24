"""The HTTP API: thin handlers that authenticate, call the story service and shape the answer."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from storyline.room import Operation
from storyline.web.auth import Authenticator
from storyline.web.operations import OPERATION_ROUTES
from storyline.web.schemas import (
    Accepted,
    CreateStoryRequest,
    LoreList,
    LoreText,
    ModelChoice,
    PresetList,
    PromptRequest,
    ScriptText,
    StoryCreated,
    StoryList,
    UndoResult,
)
from storyline.web.service import StoryService
from storyline.web.sse import KEEPALIVE_SECONDS, EventStreamResponse


def create_api_router(*, authenticator: Authenticator, service: StoryService, keepalive_seconds: float = KEEPALIVE_SECONDS) -> APIRouter:
    """Build the router that serves every operation in ``OPERATION_ROUTES``."""
    router = APIRouter()

    async def authenticated_user(request: Request) -> str:
        return await authenticator.authenticate(request.headers)

    user = Annotated[str, Depends(authenticated_user)]

    def route(operation: Operation, **options: object) -> Callable[[Callable[..., object]], Callable[..., object]]:
        method, path = OPERATION_ROUTES[operation]
        return router.api_route(path, methods=[method], **options)

    @route(Operation.LIST_PRESETS, response_model=PresetList)
    async def list_presets(user_id: user) -> PresetList:
        return service.list_presets()

    @route(Operation.LIST_STORIES, response_model=StoryList)
    async def list_stories(user_id: user) -> StoryList:
        return await service.list_stories(user_id)

    @route(Operation.CREATE_STORY, status_code=201, response_model=StoryCreated)
    async def create_story(body: CreateStoryRequest, user_id: user) -> StoryCreated:
        return StoryCreated(name=await service.create_story(user_id, body.name, body.preset))

    @route(Operation.OPEN_STORY, status_code=200, response_class=EventStreamResponse)
    async def open_story(story: str, user_id: user) -> EventStreamResponse:
        subscription = await service.open_story(user_id, story)
        return EventStreamResponse(subscription, keepalive_seconds=keepalive_seconds)

    @route(Operation.SEND_PROMPT, status_code=202, response_model=Accepted)
    async def send_prompt(story: str, body: PromptRequest, user_id: user) -> Accepted:
        await service.send_prompt(user_id, story, body.text)
        return Accepted()

    @route(Operation.INTERRUPT, status_code=204, response_class=Response)
    async def interrupt(story: str, user_id: user) -> Response:
        await service.interrupt(user_id, story)
        return Response(status_code=204)

    @route(Operation.SET_MODEL, status_code=204, response_class=Response)
    async def set_model(story: str, body: ModelChoice, user_id: user) -> Response:
        await service.set_model(user_id, story, body.model_name)
        return Response(status_code=204)

    @route(Operation.UNDO_LAST_TURN, response_model=UndoResult)
    async def undo_last_turn(story: str, user_id: user) -> UndoResult:
        return UndoResult(undone=await service.undo_last_turn(user_id, story))

    @route(Operation.CLEAR_CONVERSATION, status_code=204, response_class=Response)
    async def clear_conversation(story: str, user_id: user) -> Response:
        await service.clear_conversation(user_id, story)
        return Response(status_code=204)

    @route(Operation.READ_SCRIPT, response_model=ScriptText)
    async def read_script(story: str, user_id: user) -> ScriptText:
        return ScriptText(text=await service.read_script(user_id, story))

    @route(Operation.LIST_LORE, response_model=LoreList)
    async def list_lore(story: str, user_id: user) -> LoreList:
        return await service.list_lore(user_id, story)

    @route(Operation.READ_LORE, response_model=LoreText)
    async def read_lore(story: str, filename: str, user_id: user) -> LoreText:
        return LoreText(filename=filename, text=await service.read_lore(user_id, story, filename))

    return router
