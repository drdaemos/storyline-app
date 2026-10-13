"""Pure text operations behind the workspace's anchored edits."""

import re
from dataclasses import dataclass

from storyline.workspace.contracts import TextEditError

SNIPPET_RADIUS = 150
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n\s*")
_QUOTE_EQUIVALENTS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


@dataclass(frozen=True)
class TextChange:
    """A document after one edit, with the span of the new text inside it."""

    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Paragraph:
    """One blank-line-separated block of a document, numbered from 1."""

    number: int
    text: str


def append_text(document: str, addition: str) -> TextChange:
    """Add text to the end of a document."""
    if not addition:
        raise TextEditError("Nothing to append.")
    return TextChange(text=f"{document}{addition}", start=len(document), end=len(document) + len(addition))


def replace_unique(document: str, find: str, replace: str) -> TextChange:
    """Replace the single passage matching ``find``.

    An exact match is required first; when there is none, a match that ignores differences in
    whitespace runs and typographic quotes or dashes is accepted if it is also unique.
    """
    if not find:
        raise TextEditError("find must not be empty.")

    start, end = _locate(document, find)
    return TextChange(
        text=f"{document[:start]}{replace}{document[end:]}",
        start=start,
        end=start + len(replace),
    )


def snippet(document: str, start: int, end: int, radius: int = SNIPPET_RADIUS) -> str:
    """Return the changed span with some surrounding text, abbreviating long spans so the result stays small."""
    snippet_start = max(0, start - radius)
    snippet_end = min(len(document), end + radius)
    prefix = "…" if snippet_start > 0 else ""
    suffix = "…" if snippet_end < len(document) else ""
    if end - start <= 2 * radius:
        return f"{prefix}{document[snippet_start:snippet_end]}{suffix}"
    return f"{prefix}{document[snippet_start : start + radius]} … {document[end - radius : snippet_end]}{suffix}"


def paragraphs(document: str) -> list[Paragraph]:
    """Split a document into numbered paragraphs."""
    blocks = [block for block in PARAGRAPH_BREAK.split(document.strip()) if block.strip()]
    return [Paragraph(number=index, text=block) for index, block in enumerate(blocks, start=1)]


def _locate(document: str, find: str) -> tuple[int, int]:
    exact_count = document.count(find)
    if exact_count == 1:
        start = document.index(find)
        return start, start + len(find)
    if exact_count > 1:
        raise TextEditError(f"find matches {exact_count} places. Include more surrounding text so it matches exactly once.")

    normalized_document, spans = _normalize_with_spans(document)
    normalized_find, _ = _normalize_with_spans(find)
    normalized_find = normalized_find.strip()
    if normalized_find:
        matches = [match.start() for match in re.finditer(re.escape(normalized_find), normalized_document)]
        if len(matches) == 1:
            first = matches[0]
            last = first + len(normalized_find) - 1
            return spans[first][0], spans[last][1]
        if len(matches) > 1:
            raise TextEditError(f"find matches {len(matches)} places. Include more surrounding text so it matches exactly once.")
    raise TextEditError("find does not match the current text. Read the passage again and copy it exactly.")


def _normalize_with_spans(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Collapse whitespace runs and unify quotes, remembering each character's original span."""
    characters: list[str] = []
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            run_end = index
            while run_end < len(text) and text[run_end].isspace():
                run_end += 1
            characters.append(" ")
            spans.append((index, run_end))
            index = run_end
        else:
            characters.append(text[index].translate(_QUOTE_EQUIVALENTS))
            spans.append((index, index + 1))
            index += 1
    return "".join(characters), spans
