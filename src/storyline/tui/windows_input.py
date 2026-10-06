"""Windows terminal driver that reports Shift+Enter as its own key.

Textual's stock Windows input thread forwards only each key record's character, so Shift+Enter arrives as a
bare carriage return and is indistinguishable from Enter. This driver reads the modifier state from the
console record and feeds the kitty keyboard sequence for Shift+Enter instead, which Textual parses as
``shift+enter``. Import this module only on Windows.
"""

import asyncio
from ctypes import byref, wintypes

from textual import constants
from textual._xterm_parser import XTermParser
from textual.drivers import win32
from textual.drivers._writer_thread import WriterThread
from textual.drivers.windows_driver import WindowsDriver

VK_RETURN = 0x0D
SHIFT_PRESSED = 0x0010
CTRL_OR_ALT_PRESSED = 0x0001 | 0x0002 | 0x0004 | 0x0008
KEY_EVENT = 0x0001
WINDOW_BUFFER_SIZE_EVENT = 0x0004
MAX_EVENTS = 1024
SHIFT_ENTER_SEQUENCE = "\x1b[13;2u"


def key_record_text(virtual_key_code: int, control_key_state: int, character: str) -> str | None:
    """Return the text to feed the parser for a key-down record, or None to drop the record."""
    if control_key_state and virtual_key_code == 0:
        return None
    is_shift_only = control_key_state & SHIFT_PRESSED and not control_key_state & CTRL_OR_ALT_PRESSED
    if virtual_key_code == VK_RETURN and is_shift_only:
        return SHIFT_ENTER_SEQUENCE
    return character


class _ModifierAwareEventMonitor(win32.EventMonitor):
    """Textual's Windows input thread, with key records translated by ``key_record_text``."""

    def run(self) -> None:
        exit_requested = self.exit_event.is_set
        parser = XTermParser(debug=constants.DEBUG)
        try:
            read_count = wintypes.DWORD(0)
            handle = win32.GetStdHandle(win32.STD_INPUT_HANDLE)
            input_records = (win32.INPUT_RECORD * MAX_EVENTS)()
            while not exit_requested():
                for event in parser.tick():
                    self.process_event(event)
                if win32.wait_for_handles([handle], 100) is None:
                    continue
                win32.KERNEL32.ReadConsoleInputW(handle, byref(input_records), MAX_EVENTS, byref(read_count))
                keys: list[str] = []
                new_size: tuple[int, int] | None = None
                for input_record in input_records[: read_count.value]:
                    if input_record.EventType == KEY_EVENT:
                        key_event = input_record.Event.KeyEvent
                        if not key_event.bKeyDown:
                            continue
                        text = key_record_text(key_event.wVirtualKeyCode, key_event.dwControlKeyState, key_event.uChar.UnicodeChar)
                        if text is not None:
                            keys.append(text)
                    elif input_record.EventType == WINDOW_BUFFER_SIZE_EVENT:
                        size = input_record.Event.WindowBufferSizeEvent.dwSize
                        new_size = (size.X, size.Y)
                if keys:
                    # See https://github.com/Textualize/textual/issues/3178 for the encode/decode round trip.
                    for event in parser.feed("".join(keys).encode("utf-16", "surrogatepass").decode("utf-16")):
                        self.process_event(event)
                if new_size is not None:
                    self.on_size_change(*new_size)
        except Exception as error:
            self.app.log.error("EVENT MONITOR ERROR", error)


class ModifierAwareWindowsDriver(WindowsDriver):
    """Textual's Windows driver, using an input thread that distinguishes Shift+Enter from Enter."""

    def start_application_mode(self) -> None:
        loop = asyncio.get_running_loop()
        self._restore_console = win32.enable_application_mode()
        self._writer_thread = WriterThread(self._file)
        self._writer_thread.start()
        self.write("\x1b[?1049h")  # Enable alt screen
        self._enable_mouse_support()
        self.write("\x1b[?25l")  # Hide cursor
        self.write("\033[?1004h")  # Enable FocusIn/FocusOut
        self.write("\x1b[>1u")  # https://sw.kovidgoyal.net/kitty/keyboard-protocol/
        self.flush()
        self._enable_bracketed_paste()
        self._event_thread = _ModifierAwareEventMonitor(loop, self._app, self.exit_event, self.process_message)
        self._event_thread.start()
