"""What a signed-in user can do with their stories, independent of HTTP."""

from storyline.agent import ModelNameError
from storyline.web.errors import InvalidRequestError, LoreFileNotFoundError
from storyline.web.room_host import RoomHost, RoomSubscription
from storyline.web.schemas import LoreList, LoreSummary, StoryList
from storyline.web.user_workspaces import UserWorkspaces
from storyline.workspace import LoreEditError, StoryLibrary, StorySelectionError


class StoryService:
    """The room operations for one user at a time: every call names the user, and reaches only that user's stories."""

    def __init__(self, *, workspaces: UserWorkspaces, rooms: RoomHost) -> None:
        self._workspaces = workspaces
        self._rooms = rooms

    async def list_stories(self, user_id: str) -> StoryList:
        workspace = self._workspaces.workspace_for(user_id)
        stories = await workspace.list_stories()
        active = await workspace.read_active_story()
        return StoryList(stories=list(stories), active=active if active in stories else None)

    async def create_story(self, user_id: str, name: str) -> str:
        library = StoryLibrary(self._workspaces.workspace_for(user_id))
        try:
            story = await library.create(name=name)
        except StorySelectionError as error:
            raise InvalidRequestError(str(error)) from error
        return story.name

    async def open_story(self, user_id: str, story: str) -> RoomSubscription:
        return await self._rooms.subscribe(user_id, story)

    async def send_prompt(self, user_id: str, story: str, text: str) -> None:
        if not text.strip():
            raise InvalidRequestError("The prompt is empty.")
        async with self._rooms.use(user_id, story) as room:
            await room.send_prompt(text)

    async def interrupt(self, user_id: str, story: str) -> None:
        async with self._rooms.use(user_id, story) as room:
            room.interrupt()

    async def set_model(self, user_id: str, story: str, model_name: str) -> None:
        name = model_name.strip()
        if not name:
            raise InvalidRequestError("The model name is empty.")
        async with self._rooms.use(user_id, story) as room:
            try:
                await room.set_model(name)
            except ModelNameError as error:
                raise InvalidRequestError(str(error)) from error

    async def undo_last_turn(self, user_id: str, story: str) -> bool:
        async with self._rooms.use(user_id, story) as room:
            return await room.undo_last_turn()

    async def clear_conversation(self, user_id: str, story: str) -> None:
        async with self._rooms.use(user_id, story) as room:
            await room.clear_conversation()

    async def read_script(self, user_id: str, story: str) -> str:
        async with self._rooms.use(user_id, story) as room:
            return await room.read_script()

    async def list_lore(self, user_id: str, story: str) -> LoreList:
        async with self._rooms.use(user_id, story) as room:
            files = await room.list_lore()
        return LoreList(files=[LoreSummary(filename=file.filename, summary=file.summary, keywords=file.keywords) for file in files])

    async def read_lore(self, user_id: str, story: str, filename: str) -> str:
        async with self._rooms.use(user_id, story) as room:
            try:
                return await room.read_lore(filename)
            except LoreEditError as error:
                raise LoreFileNotFoundError(str(error)) from error
