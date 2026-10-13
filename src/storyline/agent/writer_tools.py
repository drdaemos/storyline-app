"""Tool registry for writer-agent story operations.

Edits are anchored on text, never on offsets or line numbers, and the model only sends what changes:
new prose is appended, and revisions name a short unique excerpt to replace.
"""

from functools import partial

from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import FunctionToolset, RunContext, ToolFailed

from storyline.workspace import (
    AgendaItem,
    AgendaStatus,
    Story,
    TextEdit,
    WorkspaceEditError,
    render_agenda,
    replace_agenda,
)
from storyline.workspace import (
    update_agenda_item as change_agenda_item,
)
from storyline.workspace.text_edit import paragraphs

WRITER_TOOLSET = FunctionToolset[Story](id="writer_workspace")
"""The writer agent's registered story tools."""

SCRIPT_WRITING_TOOL_NAMES = frozenset({"append_to_script", "edit_script"})
LORE_WRITING_TOOL_NAMES = frozenset({"write_lore", "append_lore", "edit_lore", "delete_lore"})
AGENDA_TOOL_NAMES = frozenset({"set_agenda", "update_agenda_item"})
"""Tools grouped by what they change, so an interface knows what to show again after one runs."""


@WRITER_TOOLSET.tool
async def append_to_script(ctx: RunContext[Story], text: str) -> str:
    """Add new prose to the end of the story. This is the normal way to continue writing.

    Args:
        text: The new text only. Start it with a blank line to begin a new paragraph.
    """
    try:
        return _describe("Appended to", await ctx.deps.append_script(text=text))
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error


@WRITER_TOOLSET.tool
async def edit_script(ctx: RunContext[Story], find: str, replace: str) -> str:
    """Revise one passage of the story without resending unchanged text.

    To delete, use an empty replace. To insert, find a short nearby excerpt and repeat it in replace together with the new text.

    Args:
        find: A short excerpt copied exactly from the story that occurs only once. Keep it as small as possible while unique.
        replace: The text that takes its place.
    """
    try:
        return _describe("Edited", await ctx.deps.replace_in_script(find=find, replace=replace))
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error


@WRITER_TOOLSET.tool
async def read_script(ctx: RunContext[Story], from_paragraph: int = 1, to_paragraph: int | None = None) -> str:
    """Read part of the story. Paragraphs are separated by blank lines and numbered from 1.

    Args:
        from_paragraph: First paragraph to return.
        to_paragraph: Last paragraph to return, inclusive. Omit to read to the end.
    """
    story = paragraphs(await ctx.deps.read_script())
    if not story:
        return "The story is empty."
    last = len(story) if to_paragraph is None else min(to_paragraph, len(story))
    if not 1 <= from_paragraph <= last:
        raise ToolFailed(f"The story has {len(story)} paragraphs; choose a range within 1-{len(story)}.")
    selected = story[from_paragraph - 1 : last]
    body = "\n\n".join(paragraph.text for paragraph in selected)
    return f"Paragraphs {from_paragraph}-{last} of {len(story)}:\n\n{body}"


@WRITER_TOOLSET.tool
async def list_lore(ctx: RunContext[Story]) -> str:
    """List every lore file with its short summary from the metadata header."""
    lore_files = await ctx.deps.list_lore()
    if not lore_files:
        return "No lore files found."

    lines = ["Lore files:"]
    for lore_file in lore_files:
        summary = lore_file.summary or "Invalid or missing summary"
        lines.append(f"- {lore_file.filename}: {summary}")
    return "\n".join(lines)


@WRITER_TOOLSET.tool
async def read_lore(ctx: RunContext[Story], filename: str) -> str:
    """Read the full text of one Markdown lore file.

    Args:
        filename: Markdown filename returned by list_lore, such as setting.md.
    """
    try:
        return await ctx.deps.read_lore(filename=filename)
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error


@WRITER_TOOLSET.tool
async def write_lore(ctx: RunContext[Story], filename: str, content: str) -> str:
    """Create a lore file, or replace all of its content. For changes to an existing file prefer append_lore or edit_lore.

    Lore files must start with a hyphen-delimited metadata header with non-empty summary and keywords properties, e.g.
    "---\\nsummary: One line.\\nkeywords: a, b\\n---\\n".

    Args:
        filename: Markdown filename beside script.md, such as setting.md. The .md extension is optional.
        content: The complete file content, including the metadata header.
    """
    try:
        return _describe("Wrote", await ctx.deps.write_lore(filename=filename, content=content))
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error


@WRITER_TOOLSET.tool
async def append_lore(ctx: RunContext[Story], filename: str, text: str) -> str:
    """Add text to the end of an existing lore file.

    Args:
        filename: Existing lore filename, such as setting.md.
        text: The new text only.
    """
    try:
        return _describe("Appended to", await ctx.deps.append_lore(filename=filename, text=text))
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error


@WRITER_TOOLSET.tool
async def edit_lore(ctx: RunContext[Story], filename: str, find: str, replace: str) -> str:
    """Revise one passage of a lore file without resending unchanged text.

    Args:
        filename: Existing lore filename, such as setting.md.
        find: A short excerpt copied exactly from the file that occurs only once.
        replace: The text that takes its place. Use an empty string to delete.
    """
    try:
        return _describe("Edited", await ctx.deps.replace_in_lore(filename=filename, find=find, replace=replace))
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error


@WRITER_TOOLSET.tool
async def delete_lore(ctx: RunContext[Story], filename: str) -> str:
    """Delete a lore file.

    Args:
        filename: Existing lore filename, such as setting.md.
    """
    try:
        await ctx.deps.delete_lore(filename=filename)
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error
    return f"Deleted {filename}."


class AgendaItemInput(BaseModel):
    """One agenda item as the model writes it."""

    title: str = Field(min_length=1, description="What is to be worked out or written, in a few words, e.g. 'The city'.")
    id: str | None = Field(default=None, description="Keep the id of an existing item when restructuring the list; omit for a new item.")
    status: AgendaStatus = Field(default="open", description="open, working, waiting, settled or dropped.")
    outcome: str = Field(default="", description="The decision in a few words. Required once the item is settled.")


@WRITER_TOOLSET.tool
async def set_agenda(ctx: RunContext[Story], items: list[AgendaItemInput]) -> str:
    """Replace the whole agenda: the ordered list of things to work through with the user, shown to them at all times.

    Use it to draw up the agenda, or to restructure it (add, remove, reorder or split items). For a status change on one
    item use update_agenda_item. When restructuring, pass the id of every item you keep so its history is preserved;
    items without an id are new.

    Statuses: open = not started; working = you are on it this turn; waiting = put to the user, waiting for their
    decision; settled = decided, with the decision in outcome (required); dropped = no longer needed.

    Args:
        items: The complete agenda in order. Early items are decisions and research; once writing starts they become scenes.
    """
    try:
        agenda = replace_agenda([_agenda_item(item) for item in items])
        await ctx.deps.write_agenda(items=agenda)
    except (WorkspaceEditError, ValidationError) as error:
        raise ToolFailed(str(error)) from error
    return render_agenda(agenda)


@WRITER_TOOLSET.tool
async def update_agenda_item(
    ctx: RunContext[Story],
    item_id: str,
    status: AgendaStatus | None = None,
    outcome: str | None = None,
    title: str | None = None,
) -> str:
    """Change one agenda item; fields you leave out stay as they are. Returns the whole agenda with ids.

    Statuses: open = not started; working = you are on it this turn; waiting = put to the user, waiting for their
    decision; settled = decided, with the decision in outcome; dropped = no longer needed. Settling an item requires an
    outcome: the decision in a few words, e.g. 'Buffalo, 1970s'.

    Args:
        item_id: The id shown in the agenda, e.g. '3f2a9c1d'.
        status: The new status.
        outcome: The decision in a few words. Required when settling.
        title: A reworded title.
    """
    try:
        agenda = await ctx.deps.change_agenda(change=partial(change_agenda_item, item_id=item_id, status=status, outcome=outcome, title=title))
    except (WorkspaceEditError, ValidationError) as error:
        raise ToolFailed(str(error)) from error
    return render_agenda(agenda)


def _agenda_item(item: AgendaItemInput) -> AgendaItem:
    if item.id is None:
        return AgendaItem(title=item.title.strip(), status=item.status, outcome=item.outcome.strip())
    return AgendaItem(id=item.id, title=item.title.strip(), status=item.status, outcome=item.outcome.strip())


def _describe(verb: str, edit: TextEdit) -> str:
    return f"{verb} {edit.filename} ({edit.original_length} → {edit.new_length} characters). Around the change it now reads:\n{edit.snippet}"
