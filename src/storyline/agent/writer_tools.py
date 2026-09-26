"""Tool registry for writer-agent workspace operations."""

from pydantic_ai import FunctionToolset, RunContext, ToolFailed

from storyline.workspace import LoreAction, ScriptWorkspace, WorkspaceEditError

WRITER_TOOLSET = FunctionToolset[ScriptWorkspace](id="writer_workspace")
"""The writer agent's registered workspace tools."""


@WRITER_TOOLSET.tool
async def edit_script(
    ctx: RunContext[ScriptWorkspace],
    start_offset: int,
    replacement: str,
    end_offset: int | None = None,
) -> str:
    """Replace a character range in the story text without resending unchanged text.
    After an edit, briefly state what changed.

    Args:
        start_offset: Zero-based start of the half-open range to replace.
        end_offset: Zero-based end of the half-open range to replace. When omitted, it is start_offset plus replacement length.
        replacement: Text that replaces the selected range. Equal offsets insert text.
    """
    try:
        edit = await ctx.deps.apply_edit(
            start_offset=start_offset,
            end_offset=end_offset,
            replacement=replacement,
        )
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error
    return f"Updated story text {edit.start_offset}:{edit.end_offset}."


@WRITER_TOOLSET.tool
async def list_lore(ctx: RunContext[ScriptWorkspace]) -> str:
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
async def read_lore(ctx: RunContext[ScriptWorkspace], filename: str) -> str:
    """Read the full text of one Markdown lore file beside script.md.

    Args:
        filename: Markdown filename returned by list_lore, such as setting.md.
    """
    try:
        return await ctx.deps.read_lore(filename=filename)
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error


@WRITER_TOOLSET.tool
async def edit_lore(
    ctx: RunContext[ScriptWorkspace],
    filename: str,
    action: LoreAction,
    content: str | None = None,
    start_offset: int | None = None,
    end_offset: int | None = None,
) -> str:
    """Append to, replace within, or delete a Markdown lore file.

    Lore files require a hyphen-delimited metadata header with non-empty summary and keywords properties.

    Args:
        filename: Markdown filename beside script.md, such as setting.md. The .md extension is optional.
        action: append or replace creates a missing file. delete removes the file.
        content: Text to append or use as the replacement. delete does not require content.
        start_offset: Zero-based start of the half-open range for replace.
        end_offset: Zero-based end of the half-open range for replace. When omitted, it is start_offset plus content length.
    """
    try:
        edit = await ctx.deps.edit_lore(
            filename=filename,
            action=action,
            content=content,
            start_offset=start_offset,
            end_offset=end_offset,
        )
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error
    completed_action = {"append": "Updated", "replace": "Replaced", "delete": "Deleted"}[edit.action]
    return f"{completed_action} {edit.filename}; length changed from {edit.original_length} to {edit.new_length}."
