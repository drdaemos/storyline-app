import sys

import pytest
from textual._xterm_parser import XTermParser

if sys.platform == "win32":
    from storyline.tui.windows_input import SHIFT_PRESSED, VK_RETURN, key_record_text

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows console input only")


def test_shift_enter_record_becomes_kitty_sequence() -> None:
    text = key_record_text(VK_RETURN, SHIFT_PRESSED, "\r")

    assert text is not None
    assert [event.key for event in XTermParser().feed(text)] == ["shift+enter"]


@pytest.mark.parametrize(
    ("virtual_key_code", "control_key_state", "character", "expected"),
    [
        (0x0D, 0, "\r", "\r"),  # plain Enter
        (0x0D, 0x0010 | 0x0008, "\r", "\r"),  # Ctrl+Shift+Enter is left alone
        (0x41, 0x0010, "A", "A"),  # Shift+A
        (0, 0x0010, "\x1b", None),  # synthesized record with modifiers is dropped, as Textual does
    ],
)
def test_other_records_pass_through(virtual_key_code: int, control_key_state: int, character: str, expected: str | None) -> None:
    assert key_record_text(virtual_key_code, control_key_state, character) == expected
