"""
PC-BASIC - window.py
Graphical interface common utilities

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys

try:
    import numpy
except ImportError:
    numpy = None

from ..compat import set_dpi_aware


# Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
set_dpi_aware()

# percentage of the screen to leave unused for window decorations etc.
DISPLAY_SLACK = 15


def apply_composite_artifacts(src_array, pixels=4):
    """Process the canvas to apply composite colour artifacts."""
    width, _ = src_array.shape
    s = [None] * pixels
    for p in range(pixels):
        s[p] = src_array[p:width:pixels] & (4//pixels)
    for p in range(1, pixels):
        s[0] = s[0]*2 + s[p]
    return numpy.repeat(s[0], pixels, axis=0)


def _most_constraining(constraining, target_aspect):
    """Find most constraining dimension to scale."""
    # we're assuming native pixels are square
    # so physical screen's aspect ratio is simply ratio of pixel numbers
    if constraining[0] / float(constraining[1]) >= target_aspect[0] / float(target_aspect[1]):
        # constraining screen has wider aspect than target screen
        # so Y is the constraining dimension
        # +------------+
        # |     +----+ |
        # |     |    | |
        # |     +----+ |
        # +------------+
        return 1
    else:
        # constraining screen has taller aspect than target screen
        # so X is the constraining dimension
        # +-----------+
        # | +-------+ |
        # | |       | |
        # | +-------+ |
        # |           |
        # +-----------+
        return 0


class WindowSizer(object):
    """Physical/logical window size operations."""

    def __init__(self, screen_width, screen_height,
            scaling=None, dimensions=None, aspect_ratio=(4, 3), border_width=0,
            **kwargs
        ):
        """Initialise size parameters."""
        # use native pixel sizes
        # i.e. logical pixel boundaries coincide with physical pixel boundaries
        self._force_native_pixel = scaling == 'native'
        # override physical pixel size of window
        self._force_display_size = dimensions
        # canvas aspect ratio
        self._aspect = aspect_ratio
        # border width as a percentage of canvas width
        self._border_width = border_width
        # the following attributes must be set separately
        # physical pixel size of screen
        self._screen_size = screen_width, screen_height
        # logical pixel size of canvas
        self.size = ()
        # physical pixel size of window (canvas+border)
        self.window_size = ()

    def normalise_pos(self, x, y):
        """Convert physical to logical coordinates within screen bounds."""
        if not self.size:
            # window not initialised
            return 0, 0
        border_x = int(self.size[0] * self._border_width / 200.)
        border_y = int(self.size[1] * self._border_width / 200.)
        xscale = self.window_size[0] / float(self.size[0] + 2*border_x)
        yscale = self.window_size[1] / float(self.size[1] + 2*border_y)
        xpos = min(self.size[0]-1, max(0, int(x//xscale - border_x)))
        ypos = min(self.size[1]-1, max(0, int(y//yscale - border_y)))
        return xpos, ypos

    def find_display_size(self, canvas_x, canvas_y):
        """Determine the optimal size for the window."""
        # comply with requested size
        if self._force_display_size:
            return self._force_display_size
        elif not self._force_native_pixel:
            return self._find_nonnative_window_size(canvas_x, canvas_y)
        else:
            return self._find_native_window_size(canvas_x, canvas_y)

    def _find_nonnative_window_size(self, canvas_x, canvas_y):
        """Determine the optimal size for a non-natively scaled window."""
        # leave part of the screen in either direction unused
        # to account for task bars, window decorations, etc.
        slack_ratio = 1. - DISPLAY_SLACK / 100.
        # border is given as a percentage of canvas size
        border_ratio = 1. + self._border_width / 100.
        # shrink the window in the most constraining dimension
        if _most_constraining(self._screen_size, self._aspect) == 1:
            # actual display aspect ratio (e.g. 16:8) is wider than target aspect ratio (e.g. 4:3)
            # scale y to fit screen height, leaving slack
            canvas_y = slack_ratio * self._screen_size[1] / border_ratio
            # scale x to match aspect ratio
            canvas_x = (canvas_y * self._aspect[0]) / float(self._aspect[1])
        else:
            # scale x to fit screen width, leaving slack
            canvas_x = slack_ratio * self._screen_size[0] / border_ratio
            # scale x to match aspect ratio
            canvas_y = (canvas_x * self._aspect[1]) / float(self._aspect[0])
        # add back border and ensure pixel sizes are integers
        window_x = int(canvas_x * border_ratio)
        window_y = int(canvas_y * border_ratio)
        return window_x, window_y

    def _find_native_window_size(self, canvas_x, canvas_y):
        """Determine the optimal size for a natively scaled window."""
        slack_ratio = 1. - DISPLAY_SLACK / 100.
        border_ratio = 1. + self._border_width / 100.
        pixel_x = int(canvas_x * border_ratio)
        pixel_y = int(canvas_y * border_ratio)
        # leave part of the screen in either direction unused
        # to account for task bars, window decorations, etc.
        target_aspect_ratio = self._aspect[0] / float(self._aspect[1])
        constraining_dim = _most_constraining(self._screen_size, self._aspect)
        if constraining_dim == 1:
            ymult = max(1, int(slack_ratio * self._screen_size[1] / float(pixel_y)))
            target_size_x = ymult * pixel_y * target_aspect_ratio
            target_xmult = target_size_x / pixel_x
            # find the multiplier that gets us closest to the target aspect ratio
            xmult = max(1, int(target_xmult))
            if xmult + 1 - target_xmult < target_xmult - xmult:
                xmult += 1
        else:
            xmult = max(1, int(slack_ratio * self._screen_size[0] / float(pixel_x)))
            target_size_y = xmult * pixel_x / target_aspect_ratio
            target_ymult = target_size_y / pixel_y
            ymult = max(1, int(target_ymult))
            if ymult + 1 - target_ymult < target_ymult - ymult:
                ymult += 1
        return xmult*pixel_x, ymult*pixel_y

    def scale(self):
        """Get scale factors from logical to window size."""
        border_x, border_y = self.border_start()
        return (
            self.window_size[0] / (self.size[0] + 2.0*border_x),
            self.window_size[1] / (self.size[1] + 2.0*border_y)
        )

    def border_start(self):
        """Top left physical coordinates of canvas."""
        return (
            int(self.size[0] * self._border_width / 200.),
            int(self.size[1] * self._border_width / 200.)
        )

    def is_maximal(self, width, height):
        """Compare dimensions to threshold for maximising."""
        return (width >= 0.95*self._screen_size[0] and height >= 0.9*self._screen_size[1])
