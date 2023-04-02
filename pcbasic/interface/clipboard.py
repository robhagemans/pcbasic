"""
PC-BASIC - clipboard.py
Clipboard handling

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import subprocess
import locale

from ..basic.base import signals
from ..basic.base import scancode
from ..compat import which

ENCODING = locale.getpreferredencoding()


class Clipboard(object):
    """Clipboard handling interface."""

    def __init__(self):
        """Initialise the clipboard handler."""
        self.ok = True

    def copy(self, text):
        """Put unicode text on clipboard."""
        pass

    def paste(self):
        """Return unicode text from clipboard."""
        return u''


class MacClipboard(Clipboard):
    """Clipboard handling for OSX. Deprecated, used only by PyGame interface."""

    def paste(self):
        """Get unicode text from clipboard."""
        return (
            subprocess.check_output('pbpaste').decode(ENCODING, 'replace')
            .replace(u'\r\n', u'\r').replace(u'\n', u'\r')
        )

    def copy(self, text):
        """Put unicode text on clipboard."""
        try:
            p = subprocess.Popen('pbcopy', stdin=subprocess.PIPE)
            p.communicate(text.encode(ENCODING, 'replace'))
        except subprocess.CalledProcessError:
            pass


class XClipboard(Clipboard):
    """Clipboard handling for X Window System using xsel or xclip."""

    def __init__(self):
        """Check for presence of xsel or xclip."""
        if which('xclip'):
            self._command = 'xclip'
            self._notmouse = ['-selection', 'clipboard']
            self.ok = True
        elif which('xsel'):
            # note that xsl has a bug that makes chromium/atom hang on paste
            # https://github.com/electron/electron/issues/3116
            self._command = 'xsel'
            self._notmouse = ['-b']
            self.ok = True
        else:
            self.ok = False

    def paste(self):
        """Get unicode text from clipboard."""
        output = subprocess.check_output([self._command, '-o'] + self._notmouse)
        return (output.decode(ENCODING, 'replace').replace(u'\r\n', u'\r').replace(u'\n', u'\r'))

    def copy(self, text):
        """Put unicode text on clipboard."""
        try:
            p = subprocess.Popen([self._command, '-i'] + self._notmouse, stdin=subprocess.PIPE)
            p.communicate(text.encode(ENCODING, 'replace'))
        except subprocess.CalledProcessError:
            pass


##############################################################################

class ClipboardInterface(object):
    """Clipboard user interface."""

    def __init__(
            self, clipboard_handler, input_queue,
            width, height, font_width, font_height, size):
        """Initialise clipboard feedback handler."""
        self._input_queue = input_queue
        self._active = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        self.width = width
        self.height = height
        self.font_width = font_width
        self.font_height = font_height
        self.size = size
        self._clipboard_handler = clipboard_handler

    def active(self):
        """True if clipboard mode is active."""
        return self._active

    def start(self, r, c):
        """Enter clipboard mode (clipboard key pressed)."""
        self._active = True
        if c < 1:
            r -= 1
            c = self.width
        if c > self.width:
            r += 1
            c = 1
        if r > self.height:
            r, c = self.height, self.width
        if r < 1:
            r, c = 1, 1
        self.select_start = [r, c]
        self.select_stop = [r, c]
        self.selection_rect = []

    def stop(self):
        """Leave clipboard mode (clipboard key released)."""
        self._active = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None

    def copy(self):
        """Copy screen characters from selection into clipboard."""
        start, stop = self.select_start, self.select_stop
        if not start or not stop:
            return
        if start[0] == stop[0] and start[1] == stop[1]:
            return
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        self._input_queue.put(signals.Event(
                signals.CLIP_COPY, (start[0], start[1], stop[0], stop[1])))

    def paste(self, text):
        """Paste from clipboard into keyboard buffer."""
        self._input_queue.put(signals.Event(signals.CLIP_PASTE, (text,)))

    def move(self, r, c):
        """Move the head of the selection and update feedback."""
        self.select_stop = [r, c]
        start, stop = self.select_start, self.select_stop
        if stop[1] < 1:
            stop[0] -= 1
            stop[1] = self.width+1
        if stop[1] > self.width+1:
            stop[0] += 1
            stop[1] = 1
        if stop[0] > self.height:
            stop[:] = [self.height, self.width+1]
        if stop[0] < 1:
            stop[:] = [1, 1]
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        rect_left = (start[1] - 1) * self.font_width
        rect_top = (start[0] - 1) * self.font_height
        rect_right = (stop[1] - 1) * self.font_width
        rect_bot = stop[0] * self.font_height
        if start[0] == stop[0]:
            # single row selection
            self.selection_rect = [(rect_left, rect_top, rect_right-rect_left, rect_bot-rect_top)]
        else:
            # multi-row selection
            self.selection_rect = [
                (rect_left, rect_top, self.size[0]-rect_left, self.font_height),
                (0, rect_top+self.font_height, self.size[0], rect_bot-rect_top-2*self.font_height),
                (0, rect_bot-self.font_height, rect_right, self.font_height)
            ]

    def handle_key(self, scan, c):
        """Handle keyboard clipboard commands."""
        if not self._active:
            return
        if c.upper() == u'C':
            self.copy()
        elif c.upper() == u'V':
            text = self._clipboard_handler.paste()
            self.paste(text)
        elif c.upper() == u'A':
            # select all
            self.select_start = [1, 1]
            self.move(self.height, self.width+1)
        elif scan == scancode.LEFT:
            # move selection head left
            self.move(self.select_stop[0], self.select_stop[1]-1)
        elif scan == scancode.RIGHT:
            # move selection head right
            self.move(self.select_stop[0], self.select_stop[1]+1)
        elif scan == scancode.UP:
            # move selection head up
            self.move(self.select_stop[0]-1, self.select_stop[1])
        elif scan == scancode.DOWN:
            # move selection head down
            self.move(self.select_stop[0]+1, self.select_stop[1])
