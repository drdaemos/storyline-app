"""Per-turn story context for the writer agent.

The story is not part of the agent instructions: instructions sit at the top of every request, so changing them
after each edit would invalidate the provider's prompt cache for the whole conversation. Instead each user turn
starts with a bounded snapshot, and the agent reads anything else it needs with ``read_script`` and ``read_lore``.
The plan, the style guide and the collaboration agreement steer every turn, so their text travels in the snapshot
instead of costing a tool call each turn. So does the agenda, which is the agent's working list for the story.
"""

from collections.abc import Mapping, Sequence

from pydantic_ai.messages import UserContent

from storyline.workspace import AgendaItem, LoreFile, Story, render_agenda
from storyline.workspace.lore_format import lore_body
from storyline.workspace.text_edit import Paragraph, paragraphs

SNAPSHOT_OPEN = "<story-snapshot>"
SNAPSHOT_CLOSE = "</story-snapshot>"
TAIL_CHARACTERS = 4000
HEADING_LIMIT = 40
PLAN_FILENAME = "plan.md"
STYLE_GUIDE_FILENAME = "style.md"
COLLABORATION_FILENAME = "collaboration.md"
GUIDE_FILENAMES = (COLLABORATION_FILENAME, PLAN_FILENAME, STYLE_GUIDE_FILENAME)
GUIDE_CHARACTERS = 4000
AGENDA_CHARACTERS = 3000


async def turn_prompt(story: Story, prompt: str) -> list[UserContent]:
    """Return the user content for one turn: a story snapshot followed by the user's prompt."""
    lore = await story.list_lore()
    present = {lore_file.filename for lore_file in lore}
    guides = {filename: lore_body(await story.read_lore(filename=filename)) for filename in GUIDE_FILENAMES if filename in present}
    snapshot = story_snapshot(await story.read_script(), lore=lore, guides=guides, agenda=await story.read_agenda())
    return [snapshot, prompt]


def story_snapshot(
    script: str,
    *,
    lore: Sequence[LoreFile] = (),
    guides: Mapping[str, str] | None = None,
    agenda: Sequence[AgendaItem] = (),
) -> str:
    """Describe the story's size, headings, ending, lore, guiding files and agenda within a fixed budget."""
    lines = [SNAPSHOT_OPEN, *_script_section(script), *_lore_section(lore)]
    for filename in GUIDE_FILENAMES:
        lines.extend(_guide_section(filename, (guides or {}).get(filename)))
    lines.extend(_agenda_section(agenda))
    lines.append(SNAPSHOT_CLOSE)
    return "\n".join(lines)


def visible_prompt_text(content: str | Sequence[UserContent]) -> str | None:
    """Return what the user typed, without the story snapshot added for the model."""
    if isinstance(content, str):
        return content
    texts = [item for item in content if isinstance(item, str) and not item.startswith(SNAPSHOT_OPEN)]
    return "\n\n".join(texts) or None


def _script_section(script: str) -> list[str]:
    story = paragraphs(script)
    if not story:
        return ["The story is empty."]

    lines = [f"script.md: {len(script)} characters in {len(story)} paragraphs."]
    headings = [paragraph for paragraph in story if paragraph.text.lstrip().startswith("#")][-HEADING_LIMIT:]
    if headings:
        lines.append("Headings:")
        lines.extend(f"¶{heading.number} {heading.text.splitlines()[0].strip()}" for heading in headings)

    tail = _tail(story)
    lines.append(f"Ending (paragraphs {tail[0].number}-{tail[-1].number}):")
    lines.append("\n\n".join(paragraph.text for paragraph in tail))
    return lines


def _lore_section(lore: Sequence[LoreFile]) -> list[str]:
    if not lore:
        return ["No lore files yet."]
    return ["Lore files:", *(f"- {lore_file.filename}: {lore_file.summary or 'missing summary'}" for lore_file in lore)]


def _guide_section(filename: str, body: str | None) -> list[str]:
    if body is None:
        return [f"{filename} does not exist yet."]
    if len(body) > GUIDE_CHARACTERS:
        body = f"{body[:GUIDE_CHARACTERS]}… (cut here; read_lore shows the rest)"
    return [f"{filename}:", body or "(empty)"]


def _agenda_section(agenda: Sequence[AgendaItem]) -> list[str]:
    rendered = render_agenda(agenda)
    if len(rendered) > AGENDA_CHARACTERS:
        rendered = f"{rendered[:AGENDA_CHARACTERS]}… (cut here; the agenda is longer)"
    return ["Agenda:", rendered]


def _tail(story: list[Paragraph]) -> list[Paragraph]:
    """Return the last paragraphs that fit the budget; a single oversized paragraph is cut from the front."""
    tail: list[Paragraph] = []
    size = 0
    for paragraph in reversed(story):
        if tail and size + len(paragraph.text) > TAIL_CHARACTERS:
            break
        tail.insert(0, paragraph)
        size += len(paragraph.text)
    if size > TAIL_CHARACTERS:
        last = tail[-1]
        tail = [Paragraph(number=last.number, text=f"…{last.text[-TAIL_CHARACTERS:]}")]
    return tail
