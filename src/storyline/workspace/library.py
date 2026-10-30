"""Story selection rules shared by every interface."""

from dataclasses import dataclass

from storyline.workspace.contracts import Story, StorySetup, Workspace

DEFAULT_SETUP = StorySetup()
"""A co-written story with no extra mechanics."""


@dataclass(frozen=True)
class StoryLibrary:
    """Chooses, switches and creates the active story, remembering the choice in the workspace."""

    workspace: Workspace

    async def list_stories(self) -> tuple[str, ...]:
        """Return the names of every story in the workspace."""
        return await self.workspace.list_stories()

    async def open_initial(self, *, requested: str | None = None) -> Story | None:
        """Open the story to start a session with, or ``None`` when the user has to choose.

        A requested story wins; otherwise the last active story is resumed, or the only story if there is one.
        """
        if requested is not None:
            return await self.switch(name=requested)
        stories = await self.workspace.list_stories()
        remembered = await self.workspace.read_active_story()
        if remembered in stories:
            return await self.switch(name=remembered)
        if len(stories) == 1:
            return await self.switch(name=stories[0])
        return None

    async def switch(self, *, name: str) -> Story:
        """Open an existing story and make it the active one."""
        story = await self.workspace.open_story(name=name)
        await self.workspace.write_active_story(name=story.name)
        return story

    async def create(self, *, name: str, setup: StorySetup = DEFAULT_SETUP) -> Story:
        """Create a story with the given setup (co-writing unless said otherwise) and make it the active one."""
        story = await self.workspace.create_story(name=name)
        await story.write_setup(setup=setup)
        await self.workspace.write_active_story(name=story.name)
        return story
