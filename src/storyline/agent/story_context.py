"""Per-turn story context for the writer agent.

The story is not part of the agent instructions: instructions sit at the top of every request, so changing them
after each edit would invalidate the provider's prompt cache for the whole conversation. Instead each user turn
starts with a bounded snapshot, and the agent reads anything else it needs with ``read_script``.
"""

from collections.abc import Sequence

from pydantic_ai.messages import UserContent

from storyline.workspace import Story
from storyline.workspace.text_edit import Paragraph, paragraphs

SNAPSHOT_OPEN = "<story-snapshot>"
SNAPSHOT_CLOSE = "</story-snapshot>"
TAIL_CHARACTERS = 2000
HEADING_LIMIT = 40


async def turn_prompt(story: Story, prompt: str) -> list[UserContent]:
    """Return the user content for one turn: a story snapshot followed by the user's prompt."""
    return [story_snapshot(await story.read_script()), prompt]


def story_snapshot(script: str) -> str:
    """Describe the story's size, headings and ending within a fixed budget."""
    story = paragraphs(script)
    if not story:
        return f"{SNAPSHOT_OPEN}\nThe story is empty.\n{SNAPSHOT_CLOSE}"

    lines = [SNAPSHOT_OPEN, f"script.md: {len(script)} characters in {len(story)} paragraphs."]
    headings = [paragraph for paragraph in story if paragraph.text.lstrip().startswith("#")][-HEADING_LIMIT:]
    if headings:
        lines.append("Headings:")
        lines.extend(f"¶{heading.number} {heading.text.splitlines()[0].strip()}" for heading in headings)

    tail = _tail(story)
    lines.append(f"Ending (paragraphs {tail[0].number}-{tail[-1].number}):")
    lines.append("\n\n".join(paragraph.text for paragraph in tail))
    lines.append(SNAPSHOT_CLOSE)
    return "\n".join(lines)


def visible_prompt_text(content: str | Sequence[UserContent]) -> str | None:
    """Return what the user typed, without the story snapshot added for the model."""
    if isinstance(content, str):
        return content
    texts = [item for item in content if isinstance(item, str) and not item.startswith(SNAPSHOT_OPEN)]
    return "\n\n".join(texts) or None


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
