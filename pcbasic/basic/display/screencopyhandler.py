"""
PC-BASIC - display.screencopyhandler
Clipboard copy & print screen handler

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import scancode
from ..base import signals


class ScreenCopyHandler(object):
    """Event handler for clipboard copy and print screen."""

    # handle an input signal, read the screen
    # and write the text to an output queue or file
    # independently of what BASIC is doing

    def __init__(self, queues, text_screen, lpt1_file):
        """Initialise copy handler."""
        self._queues = queues
        self._text_screen = text_screen
        self._lpt1_file = lpt1_file

    def check_input(self, signal):
        """Handle input signals."""
        if signal.event_type == signals.CLIP_COPY:
            self._copy_clipboard(*signal.params)
            return True
        elif signal.event_type == signals.KEYB_DOWN:
            c, scan, mod = signal.params
            if scan == scancode.PRINT and (scancode.LSHIFT in mod or scancode.RSHIFT in mod):
                # shift+printscreen triggers a print screen
                self._print_screen(self._lpt1_file)
                return True
        return False

    def _print_screen(self, target_file):
        """Output the visible page to file in raw bytes."""
        if not target_file:
            return
        for line in self._text_screen.get_chars(as_type=bytes):
            target_file.write(b''.join(line).replace(b'\0', b' '))
        target_file.write_line()

    def _copy_clipboard(self, start_row, start_col, stop_row, stop_col):
        """Copy selected screen area to clipboard."""
        # in the signal, stop_row is inclusive but stop_col is *exclusive* ?
        text = list(self._text_screen.get_text(
            start_row=start_row, start_col=start_col, stop_row=stop_row, stop_col=stop_col-1
        ))
        clip_text = u'\n'.join(u''.join(_row) for _row in text)
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_CLIPBOARD_TEXT, (clip_text,)
        ))
