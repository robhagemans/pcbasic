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
    for p in range(1,pixels):
        s[0] = s[0]*2 + s[p]
    return numpy.repeat(s[0], pixels, axis=0)


class WindowSizer(object):
    """Graphical video plugin, base class."""

    def __init__(self, screen_width, screen_height,
            scaling=None, dimensions=None, aspect_ratio=(4, 3),
            border_width=0, fullscreen=False, **kwargs):
        """Initialise size parameters."""
        # use native pixel sizes
        self._force_native_pixel = scaling == 'native'
        # display dimensions
        self._force_display_size = dimensions
        # aspect ratio
        self._aspect = aspect_ratio
        # border width percentage
        self._border_width = border_width
        # start in fullscreen mode
        self._fullscreen = fullscreen
        # the following attributes must be set separately
        # physical size of screen
        self._screen_size = screen_width, screen_height
        # logical size of canvas
        self.size = ()
        # physical size of window (canvas+border)
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
        # comply with requested size unless we're fullscreening
        if self._force_display_size and not self._fullscreen:
            return self._force_display_size
        if not self._force_native_pixel:
            # this assumes actual display aspect ratio is wider than 4:3
            # scale y to fit screen
            canvas_y = (1-DISPLAY_SLACK/100.) * (
                    self._screen_size[1] // int(1+self._border_width/100.))
            # scale x to match aspect ratio
            canvas_x = (canvas_y * self._aspect[0]) / self._aspect[1]
            # add back border
            pixel_x = int(canvas_x * (1 + self._border_width/100.))
            pixel_y = int(canvas_y * (1 + self._border_width/100.))
            return pixel_x, pixel_y
        else:
            pixel_x = int(canvas_x * (1 + self._border_width/100.))
            pixel_y = int(canvas_y * (1 + self._border_width/100.))
            # leave part of the screen either direction unused
            # to account for task bars, window decorations, etc.
            xmult = max(1, int((100.-DISPLAY_SLACK) * self._screen_size[0] / (100.*pixel_x)))
            ymult = max(1, int((100.-DISPLAY_SLACK) * self._screen_size[1] / (100.*pixel_y)))
            # find the multipliers mx <= xmult, my <= ymult
            # such that mx * pixel_x / my * pixel_y
            # is multiplicatively closest to aspect[0] / aspect[1]
            target = self._aspect[0] / (1.0 * self._aspect[1])
            current = xmult * canvas_x / (1.0 * ymult * canvas_y)
            # find the absolute multiplicative distance (always > 1)
            best = max(current, target) / min(current, target)
            apx = xmult, ymult
            for mx in range(1, xmult+1):
                my = min(
                    ymult, int(round(mx*canvas_x*self._aspect[1] / (1.0*canvas_y*self._aspect[0]))))
                current = mx*pixel_x / (1.0*my*pixel_y)
                dist = max(current, target) / min(current, target)
                # prefer larger multipliers if distance is equal
                if dist <= best:
                    best = dist
                    apx = mx, my
            return apx[0] * pixel_x, apx[1] * pixel_y

    def scale(self):
        """Get scale factors from logical to window size."""
        border_x, border_y = self.border_start()
        return (
            self.window_size[0] / (self.size[0] + 2.0*border_x),
            self.window_size[1] / (self.size[1] + 2.0*border_y))

    def border_start(self):
        """Top left physical coordinates of canvas."""
        return (
            int(self.size[0] * self._border_width / 200.),
            int(self.size[1] * self._border_width / 200.))

    def is_maximal(self, width, height):
        """Compare dimensions to threshold for maximising."""
        return (width >= 0.95*self._screen_size[0] and height >= 0.9*self._screen_size[1])
