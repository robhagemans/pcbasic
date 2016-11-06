"""
PC-BASIC - video_graphical.py
Graphical interface base class

(c) 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import platform

try:
    import numpy
except ImportError:
    numpy = None

if platform.system() == 'Windows':
    # Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
    # see https://bitbucket.org/pygame/pygame/issues/245/wrong-resolution-unless-you-use-ctypes
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        # old versions of Windows don't have this in user32.dll
        pass

from . import base

from ..basic.base import signals
from ..basic.base import scancode

# percentage of the screen to leave unused for window decorations etc.
display_slack = 15




class VideoGraphical(base.VideoPlugin):
    """Graphical video plugin, base class """

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
        # request smooth scaling
        self.smooth = kwargs.get('smooth', False)
        # ignore ALT+F4 and window X button
        self.nokill = kwargs.get('nokill', False)
        # window caption/title
        self.caption = kwargs.get('caption', '')
        # if no composite palette available for this card, ignore.
        self.composite_monitor = kwargs.get('composite_monitor', False)
        # video card to emulate (only used for composite)
        self.composite_card = kwargs.get('composite_card')
        # don't try composite unless our video card supports it
        self.composite_monitor = self.composite_monitor and self.composite_card in composite_640
        # the following attributes must be overridden by child classes
        # size of display
        self.physical_size = None
        # size of canvas
        self.size = None
        # size of window (canvas+border)
        self.window_width = None
        self.window_height = None


    ###########################################################################
    # miscellaneous helper functions

    def _normalise_pos(self, x, y):
        """Convert physical to logical coordinates within screen bounds."""
        if not self.size:
            # window not initialised
            return 0, 0
        border_x = int(self.size[0] * self.border_width / 200.)
        border_y = int(self.size[1] * self.border_width / 200.)
        xscale = self.window_width / (1.*(self.size[0]+2*border_x))
        yscale = self.window_height / (1.*(self.size[1]+2*border_y))
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
            canvas_y = (1 - display_slack/100.) * (
                        self.physical_size[1] // int(1 + border_width/100.))
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
            xmult = max(1, int((100.-display_slack) *
                                        self.physical_size[0] / (100.*pixel_x)))
            ymult = max(1, int((100.-display_slack) *
                                        self.physical_size[1] / (100.*pixel_y)))
            # find the multipliers mx <= xmult, my <= ymult
            # such that mx * pixel_x / my * pixel_y
            # is multiplicatively closest to aspect[0] / aspect[1]
            target = self.aspect[0]/(1.0*self.aspect[1])
            current = xmult*canvas_x / (1.0*ymult*canvas_y)
            # find the absolute multiplicative distance (always > 1)
            best = max(current, target) / min(current, target)
            apx = xmult, ymult
            for mx in range(1, xmult+1):
                my = min(ymult,
                         int(round(mx*canvas_x*self.aspect[1] / (1.0*canvas_y*self.aspect[0]))))
                current = mx*pixel_x / (1.0*my*pixel_y)
                dist = max(current, target) / min(current, target)
                # prefer larger multipliers if distance is equal
                if dist <= best:
                    best = dist
                    apx = mx, my
            return apx[0] * pixel_x, apx[1] * pixel_y



class ClipboardInterface(object):
    """Clipboard user interface."""

    def __init__(self, videoplugin, width, height):
        """Initialise clipboard feedback handler."""
        self._active = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        self.width = width
        self.height = height
        self.font_width = videoplugin.font_width
        self.font_height = videoplugin.font_height
        self.size = videoplugin.size
        self.videoplugin = videoplugin

    def active(self):
        """True if clipboard mode is active."""
        return self._active

    def start(self, r, c):
        """Enter clipboard mode (clipboard key pressed)."""
        self._active = True
        self.select_start = [r, c]
        self.select_stop = [r, c]
        self.selection_rect = []

    def stop(self):
        """Leave clipboard mode (clipboard key released)."""
        self._active = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        self.videoplugin.screen_changed = True

    def copy(self, mouse=False):
        """Copy screen characters from selection into clipboard."""
        start, stop = self.select_start, self.select_stop
        if not start or not stop:
            return
        if start[0] == stop[0] and start[1] == stop[1]:
            return
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        self.videoplugin.input_queue.put(signals.Event(signals.CLIP_COPY,
                (start[0], start[1], stop[0], stop[1], mouse)))

    def paste(self, text):
        """Paste from clipboard into keyboard buffer."""
        self.videoplugin.input_queue.put(signals.Event(signals.CLIP_PASTE, (text,)))

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
            self.selection_rect = [(rect_left, rect_top,
                                    rect_right-rect_left, rect_bot-rect_top)]
        else:
            # multi-row selection
            self.selection_rect = [
                (rect_left, rect_top,
                      self.size[0]-rect_left, self.font_height),
                (0, rect_top + self.font_height,
                      self.size[0], rect_bot - rect_top - 2*self.font_height),
                (0, rect_bot - self.font_height,
                      rect_right, self.font_height)]
        self.videoplugin.screen_changed = True

    def handle_key(self, scan, c):
        """Handle keyboard clipboard commands."""
        if not self._active:
            return
        if c.upper() == u'C':
            self.copy()
        elif c.upper() == u'V':
            text = self.videoplugin.clipboard_handler.paste(mouse=False)
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


# composite palettes, see http://nerdlypleasures.blogspot.co.uk/2013_11_01_archive.html
composite_640 = {
    'cga_old': [
        (0x00, 0x00, 0x00),        (0x00, 0x71, 0x00),        (0x00, 0x3f, 0xff),        (0x00, 0xab, 0xff),
        (0xc3, 0x00, 0x67),        (0x73, 0x73, 0x73),        (0xe6, 0x39, 0xff),        (0x8c, 0xa8, 0xff),
        (0x53, 0x44, 0x00),        (0x00, 0xcd, 0x00),        (0x73, 0x73, 0x73),        (0x00, 0xfc, 0x7e),
        (0xff, 0x39, 0x00),        (0xe2, 0xca, 0x00),        (0xff, 0x7c, 0xf4),        (0xff, 0xff, 0xff)    ],
    'cga': [
        (0x00, 0x00, 0x00),        (0x00, 0x6a, 0x2c),        (0x00, 0x39, 0xff),        (0x00, 0x94, 0xff),
        (0xca, 0x00, 0x2c),        (0x77, 0x77, 0x77),        (0xff, 0x31, 0xff),        (0xc0, 0x98, 0xff),
        (0x1a, 0x57, 0x00),        (0x00, 0xd6, 0x00),        (0x77, 0x77, 0x77),        (0x00, 0xf4, 0xb8),
        (0xff, 0x57, 0x00),        (0xb0, 0xdd, 0x00),        (0xff, 0x7c, 0xb8),        (0xff, 0xff, 0xff)    ],
    'tandy': [
        (0x00, 0x00, 0x00),        (0x7c, 0x30, 0x00),        (0x00, 0x75, 0x00),        (0x00, 0xbe, 0x00),
        (0x00, 0x47, 0xee),        (0x77, 0x77, 0x77),        (0x00, 0xbb, 0xc4),        (0x00, 0xfb, 0x3f),
        (0xb2, 0x0f, 0x9d),        (0xff, 0x1e, 0x0f),        (0x77, 0x77, 0x77),        (0xff, 0xb8, 0x00),
        (0xb2, 0x44, 0xff),        (0xff, 0x78, 0xff),        (0x4b, 0xba, 0xff),        (0xff, 0xff, 0xff)    ],
    'pcjr': [
        (0x00, 0x00, 0x00),
        (0x98, 0x20, 0xcb),        (0x9f, 0x1c, 0x00),        (0xff, 0x11, 0x71),        (0x00, 0x76, 0x00),
        (0x77, 0x77, 0x77),        (0x5b, 0xaa, 0x00),        (0xff, 0xa5, 0x00),        (0x00, 0x4e, 0xcb),
        (0x74, 0x53, 0xff),        (0x77, 0x77, 0x77),        (0xff, 0x79, 0xff),        (0x00, 0xc8, 0x71),
        (0x00, 0xcc, 0xff),        (0x00, 0xfa, 0x00),        (0xff, 0xff, 0xff) ]        }

def apply_composite_artifacts(src_array, pixels=4):
    """Process the canvas to apply composite colour artifacts."""
    width, height = src_array.shape
    s = [None]*pixels
    for p in range(pixels):
        s[p] = src_array[p:width:pixels]&(4//pixels)
    for p in range(1,pixels):
        s[0] = s[0]*2 + s[p]
    return numpy.repeat(s[0], pixels, axis=0)
