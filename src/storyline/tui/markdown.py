"""Markdown for the terminal: ``<details>`` sections become quoted sections, other raw HTML shows as text."""

import re

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.token import Token

_ALLOWED_TAG = re.compile(r"</?(?:details|summary)>", re.IGNORECASE)
_SPLIT_ALLOWED_TAGS = re.compile(r"(</?(?:details|summary)>)", re.IGNORECASE)


def terminal_markdown() -> MarkdownIt:
    """A parser for agent replies, for the Markdown widget's ``parser_factory``."""
    parser = MarkdownIt("gfm-like")
    parser.core.ruler.after("inline", "restrict_html", _restrict_html)
    return parser


def _text(content: str) -> Token:
    return Token("text", "", 0, content=content)


def _inline(content: str) -> Token:
    return Token("inline", "", 0, content=content, children=[_text(content)])


def _paragraph(inline: Token) -> list[Token]:
    return [Token("paragraph_open", "p", 1), inline, Token("paragraph_close", "p", -1)]


def _summary(parser: MarkdownIt, text: str) -> list[Token]:
    """The summary line of a section, in bold."""
    inline = parser.parseInline(text)[0]
    inline.children = [
        Token("strong_open", "strong", 1, markup="**"),
        *(inline.children or []),
        Token("strong_close", "strong", -1, markup="**"),
    ]
    return _paragraph(inline)


def _expand_html_block(parser: MarkdownIt, content: str, depth: int) -> tuple[list[Token], int]:
    """Turn a raw HTML block into tokens; ``depth`` is how many sections are open."""
    if not _SPLIT_ALLOWED_TAGS.search(content):
        return _paragraph(_inline(content.strip())), depth
    tokens: list[Token] = []
    in_summary = False
    for piece in _SPLIT_ALLOWED_TAGS.split(content):
        if _ALLOWED_TAG.fullmatch(piece):
            tag = piece.lower()
            in_summary = tag == "<summary>"
            if tag == "<details>":
                tokens.append(Token("blockquote_open", "blockquote", 1, markup=">"))
                depth += 1
            elif tag == "</details>" and depth > 0:
                tokens.append(Token("blockquote_close", "blockquote", -1, markup=">"))
                depth -= 1
            continue
        text = piece.strip()
        if not text:
            continue
        tokens.extend(_summary(parser, text) if in_summary else parser.parse(text))
    return tokens, depth


def _restrict_html(state: StateCore) -> None:
    """Raw HTML is parsed but not trusted: sections are kept, everything else becomes text."""
    tokens: list[Token] = []
    depth = 0
    for token in state.tokens:
        if token.type == "html_block":
            expanded, depth = _expand_html_block(state.md, token.content, depth)
            tokens.extend(expanded)
            continue
        for child in token.children or []:
            if child.type == "html_inline":
                child.type = "text"
                if _ALLOWED_TAG.fullmatch(child.content):
                    child.content = ""
        tokens.append(token)
    tokens.extend(Token("blockquote_close", "blockquote", -1, markup=">") for _ in range(depth))
    state.tokens = tokens
