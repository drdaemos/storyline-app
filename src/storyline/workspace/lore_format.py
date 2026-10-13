"""The lore file format: a hyphen-delimited metadata header followed by free Markdown."""

import re

LORE_HEADER_DELIMITER = re.compile(r"-{3,}\s*")
LORE_HEADER_PROPERTY = re.compile(r"(?P<key>[^:\s][^:]*):\s*(?P<value>.*)")


def lore_metadata(content: str) -> dict[str, str] | None:
    """Return the header properties, or None when the file has no valid header."""
    header = _parse_header(content)
    return header[0] if header is not None else None


def lore_body(content: str) -> str:
    """Return the text after the metadata header, or the whole text when there is no valid header."""
    header = _parse_header(content)
    if header is None:
        return content.strip()
    lines = content.splitlines()
    return "\n".join(lines[header[1] + 1 :]).strip()


def _parse_header(content: str) -> tuple[dict[str, str], int] | None:
    """Return the header properties and the index of the closing delimiter line."""
    lines = content.splitlines()
    if not lines or LORE_HEADER_DELIMITER.fullmatch(lines[0]) is None:
        return None

    properties: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if LORE_HEADER_DELIMITER.fullmatch(line):
            return (properties, index) if properties else None
        if not line.strip():
            continue
        property_match = LORE_HEADER_PROPERTY.fullmatch(line)
        if property_match is None:
            return None
        key = property_match.group("key").strip().lower()
        if key in properties:
            return None
        properties[key] = property_match.group("value").strip()
    return None
