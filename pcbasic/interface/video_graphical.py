"""
PC-BASIC - video_graphical.py
Graphical interface base class

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import platform
import os

try:
    import numpy
except ImportError:
    numpy = None

from . import base
from ..basic.base import signals
from ..basic.base import scancode


if platform.system() == 'Windows':
    # Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
    # see https://bitbucket.org/pygame/pygame/issues/245/wrong-resolution-unless-you-use-ctypes
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        # old versions of Windows don't have this in user32.dll
        pass


# percentage of the screen to leave unused for window decorations etc.
DISPLAY_SLACK = 15

# message displayed when Alt-F4 inhibited
NOKILL_MESSAGE = u'to exit type <CTRL+BREAK> <ESC> SYSTEM'


def apply_composite_artifacts(src_array, pixels=4):
    """Process the canvas to apply composite colour artifacts."""
    width, height = src_array.shape
    s = [None]*pixels
    for p in range(pixels):
        s[p] = src_array[p:width:pixels]&(4//pixels)
    for p in range(1,pixels):
        s[0] = s[0]*2 + s[p]
    return numpy.repeat(s[0], pixels, axis=0)


class VideoGraphical(base.VideoPlugin):
    """Graphical video plugin, base class."""

    def __init__(self, input_queue, video_queue, **kwargs):
        """Initialise video plugin parameters."""
        base.VideoPlugin.__init__(self, input_queue, video_queue)
        # use native pixel sizes
        self.force_native_pixel = kwargs.get('force_native_pixel', False)
        # display dimensions
        self.force_display_size = kwargs.get('force_display_size', None)
        # aspect ratio
        self.aspect = kwargs.get('aspect', (4, 3))
        # border width percentage
        self.border_width = kwargs.get('border_width', 0)
        # start in fullscreen mode
        self.fullscreen = kwargs.get('fullscreen', False)
        # the following attributes must be overridden by child classes
        # size of display
        self.physical_size = ()
        # size of canvas
        self.size = ()
        # size of window (canvas+border)
        self.window_width = None
        self.window_height = None

    def _normalise_pos(self, x, y):
        """Convert physical to logical coordinates within screen bounds."""
        if not self.size:
            # window not initialised
            return 0, 0
        border_x = int(self.size[0] * self.border_width / 200.)
        border_y = int(self.size[1] * self.border_width / 200.)
        xscale = self.window_width / float(self.size[0] + 2*border_x)
        yscale = self.window_height / float(self.size[1] + 2*border_y)
        xpos = min(self.size[0]-1, max(0, int(x//xscale - border_x)))
        ypos = min(self.size[1]-1, max(0, int(y//yscale - border_y)))
        return xpos, ypos

    def _find_display_size(self, canvas_x, canvas_y, border_width):
        """Determine the optimal size for the display."""
        # comply with requested size unless we're fullscreening
        if self.force_display_size and not self.fullscreen:
            return self.force_display_size
        if not self.force_native_pixel:
            # this assumes actual display aspect ratio is wider than 4:3
            # scale y to fit screen
            canvas_y = (1-DISPLAY_SLACK/100.) * (self.physical_size[1] // int(1+border_width/100.))
            # scale x to match aspect ratio
            canvas_x = (canvas_y * self.aspect[0]) / self.aspect[1]
            # add back border
            pixel_x = int(canvas_x * (1 + border_width/100.))
            pixel_y = int(canvas_y * (1 + border_width/100.))
            return pixel_x, pixel_y
        else:
            pixel_x = int(canvas_x * (1 + border_width/100.))
            pixel_y = int(canvas_y * (1 + border_width/100.))
            # leave part of the screen either direction unused
            # to account for task bars, window decorations, etc.
            xmult = max(1, int((100.-DISPLAY_SLACK) * self.physical_size[0] / (100.*pixel_x)))
            ymult = max(1, int((100.-DISPLAY_SLACK) * self.physical_size[1] / (100.*pixel_y)))
            # find the multipliers mx <= xmult, my <= ymult
            # such that mx * pixel_x / my * pixel_y
            # is multiplicatively closest to aspect[0] / aspect[1]
            target = self.aspect[0] / (1.0 * self.aspect[1])
            current = xmult * canvas_x / (1.0 * ymult * canvas_y)
            # find the absolute multiplicative distance (always > 1)
            best = max(current, target) / min(current, target)
            apx = xmult, ymult
            for mx in range(1, xmult+1):
                my = min(
                    ymult, int(round(mx*canvas_x*self.aspect[1] / (1.0*canvas_y*self.aspect[0]))))
                current = mx*pixel_x / (1.0*my*pixel_y)
                dist = max(current, target) / min(current, target)
                # prefer larger multipliers if distance is equal
                if dist <= best:
                    best = dist
                    apx = mx, my
            return apx[0] * pixel_x, apx[1] * pixel_y


class EnvironmentCache(object):
    """ Set environment variables for temporary use and clean up nicely."""

    def __init__(self):
        """Create the environment cache."""
        self._saved = {}

    def set(self, key, value):
        """Set an environment variable and save the original value in the cache."""
        if key in self._saved:
            self.reset(key)
        self._saved[key] = os.environ.get(key)
        os.environ[key] = value

    def reset(self, key):
        """Restore the original value for an environment variable."""
        cached = self._saved.pop(key, None)
        if cached is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = cached

    def close(self):
        """Restore all environment variables."""
        for key in self._saved.keys():
            self.reset(key)

    def __del__(self):
        """Clean up the cache."""
        self.close()


class ClipboardInterface(object):
    """Clipboard user interface."""

    def __init__(self, clipboard_handler, input_queue, width, height, font_width, font_height, size):
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

    def copy(self, mouse=False):
        """Copy screen characters from selection into clipboard."""
        start, stop = self.select_start, self.select_stop
        if not start or not stop:
            return
        if start[0] == stop[0] and start[1] == stop[1]:
            return
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        self._input_queue.put(signals.Event(
                signals.CLIP_COPY, (start[0], start[1], stop[0], stop[1], mouse)))

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
            text = self._clipboard_handler.paste(mouse=False)
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
