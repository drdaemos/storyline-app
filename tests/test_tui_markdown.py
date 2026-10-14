"""Tests for the terminal UI's Markdown handling."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Markdown

from storyline.tui.markdown import terminal_markdown

REPLY = (
    "Before.\n\n"
    "<details> <summary>Why *lean*</summary> It is **mostly** chemistry. <script>alert(1)</script> </details>\n\n"
    "After."
)


def _types(source: str) -> list[str]:
    return [token.type for token in terminal_markdown().parse(source)]


def _html(source: str) -> str:
    return terminal_markdown().render(source)


def test_details_become_a_quoted_section_with_a_bold_summary() -> None:
    html = _html(REPLY)

    assert "<blockquote>" in html
    assert "<strong>Why <em>lean</em></strong>" in html
    assert "<strong>mostly</strong>" in html
    assert "<details" not in html
    assert "<summary" not in html


def test_other_raw_html_is_shown_as_text() -> None:
    html = _html(REPLY)

    assert "<script" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img" in _html("<img src=x>")


def test_sections_are_always_balanced() -> None:
    assert _types("<details><summary>Open</summary> Never closed.").count("blockquote_open") == 1
    assert _types("<details><summary>Open</summary> Never closed.").count("blockquote_close") == 1
    assert "blockquote_close" not in _types("Stray </details> tag")


def test_text_around_the_section_stays_in_place() -> None:
    html = _html(REPLY)

    assert html.index("Before.") < html.index("Why") < html.index("After.")


class _ReplyApp(App[None]):
    def compose(self) -> ComposeResult:
        yield Markdown(REPLY, parser_factory=terminal_markdown)


@pytest.mark.asyncio
async def test_the_markdown_widget_shows_the_section_text() -> None:
    async with _ReplyApp().run_test() as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(Markdown)
        shown = " ".join(str(block.render()) for block in widget.query("MarkdownBlock"))

        assert "Why lean" in shown
        assert "mostly chemistry" in shown
        assert "<details>" not in shown
