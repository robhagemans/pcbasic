"""
PC-BASIC - graphics.py
Graphics operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    import numpy
except ImportError:
    numpy = None

import math

from ..base import error
from ..base import tokens as tk
from ..base import signals
from .. import values
from .. import mlparser


class GraphicsViewPort(object):
    """Graphics viewport (clip area) functions."""

    def __init__(self, max_width, max_height):
        """Initialise graphics viewport."""
        self._width, self._height = max_width, max_height
        self.unset()

    def unset(self):
        """Unset the graphics viewport."""
        self.absolute = False
        self.rect = None

    def set(self, x0, y0, x1, y1, absolute):
        """Set the graphics viewport."""
        # VIEW orders the coordinates
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        self.absolute = absolute
        self.rect = x0, y0, x1, y1

    def is_set(self):
        """Return whether the graphics viewport is set."""
        return self.rect is not None

    def get(self):
        """Return the graphics viewport or full screen dimensions if not set."""
        if self.rect:
            return self.rect
        else:
            return 0, 0, self._width-1, self._height-1

    def contains(self, x, y):
        """Return whether the specified point is within the graphics view (boundaries inclusive)."""
        vx0, vy0, vx1, vy1 = self.get()
        return vx0 <= x <= vx1 and vy0 <= y <= vy1

    def clip_rect(self, x0, y0, x1, y1):
        """Return rect clipped to view."""
        vx0, vy0, vx1, vy1 = self.get()
        return max(x0, vx0), max(y0, vy0), min(x1, vx1), min(y1, vy1)

    def clip_area(self, x0, y0, x1, y1, area_buffer):
        """Return area buffer in [y][x] format clipped to view."""
        vx0, vy0, vx1, vy1 = self.get()
        nx0, ny0, nx1, ny1 =  max(x0, vx0), max(y0, vy0), min(x1, vx1), min(y1, vy1)
        if numpy and type(area_buffer) == numpy.ndarray:
            nbuf = area_buffer[ny0-y0:ny1-y0+1, nx0-x0:nx1-x0+1]
        else:
            nbuf = [row[nx0-x0:nx1-x0+1] for row in area_buffer[ny0-y0:ny1-y0+1]]
        return nx0, ny0, nx1, ny1, nbuf

    def clip_interval(self, x0, x1, y):
        """Return rect clipped to view."""
        vx0, vy0, vx1, vy1 = self.get()
        if not (vy0 <= y <= vy1):
            return x0, x0-1, y
        return max(x0, vx0), min(x1, vx1), y

    def clip_list(self, x0, y0, attr_list):
        """Return rect clipped to view."""
        vx0, vy0, vx1, vy1 = self.get()
        if not (vy0 <= y0 <= vy1):
            return x0, y0, []
        nx0, nx1 = max(x0, vx0), min(x0+len(attr_list), vx1)
        return nx0, y0, attr_list[nx0-x0:nx1-x0+1]

    def get_mid(self):
        """Get the midpoint of the current graphics view."""
        x0, y0, x1, y1 = self.get()
        # +1 to match GW-BASIC
        return x0 + (x1-x0)/2 + 1, y0 + (y1-y0)/2 + 1

    def coords(self, x, y):
        """Retrieve absolute coordinates for viewport coordinates."""
        if (not self.rect) or self.absolute:
            return x, y
        else:
            return x + self.rect[0], y + self.rect[1]


class Drawing(object):
    """Graphical drawing operations."""

    def __init__(self, queues, input_methods, values, memory):
        """Initialise graphics object."""
        # for apagenum and attr
        self._queues = queues
        self._values = values
        self._memory = memory
        # for wait() in paint_
        self._input_methods = input_methods
        # memebers set on mode switch
        self._mode = None
        self._text = None
        self._pixels = None
        self.graph_view = None
        self._apagenum = None
        self.last_point = None
        self.last_attr = None
        self.draw_scale = None
        self.draw_angle = None

    def init_mode(self, mode, text, pixels):
        """Initialise for new graphics mode."""
        self._mode = mode
        self._text = text
        self._pixels = pixels
        # set graphics viewport
        self.graph_view = GraphicsViewPort(self._mode.pixel_width, self._mode.pixel_height)
        self.unset_window()
        self.reset()

    def reset(self):
        """Reset graphics state."""
        if self._mode.is_text_mode:
            return
        self.last_point = self.graph_view.get_mid()
        self.last_attr = self._mode.attr
        self.draw_scale = 4
        self.draw_angle = 0

    def set_attr(self, attr):
        """Set the current attribute."""
        self._attr = attr

    def set_page(self, apagenum):
        """Set the active page."""
        self._apagenum = apagenum

    ### attributes

    def get_attr_index(self, c):
        """Get the index of the specified attribute."""
        if c == -1:
            # foreground; graphics 'background' attrib is always 0
            c = self._attr & 0xf
        else:
            c = min(self._mode.num_attr-1, max(0, c))
        return c

    ### text/graphics interaction

    def clear_text_at(self, x, y):
        """Remove the character covering a single pixel."""
        row, col = self._mode.pixel_to_text_pos(x, y)
        # use attr = 0 ?
        if col >= 1 and row >= 1 and col <= self._mode.width and row <= self._mode.height:
            self._text.put_char_attr(self._apagenum, row, col, b' ', self._attr)
        fore, back, blink, underline = self._mode.split_attr(self._attr)
        self._queues.video.put(signals.Event(signals.VIDEO_PUT_GLYPH,
                (self._apagenum, row, col, u' ', False, fore, back, blink, underline)))

    def clear_text_area(self, x0, y0, x1, y1):
        """Remove all characters from the text buffer on a rectangle of the graphics screen."""
        row0, col0, row1, col1 = self._mode.pixel_to_text_area(x0, y0, x1, y1)
        # use attr = 0 ? pagenum parameter? are we actually sending anything to the queue?
        self._text.clear_area(self._apagenum, row0, col0, row1, col1, self._attr)

    ### graphics primitives

    def put_pixel(self, x, y, index, pagenum=None):
        """Put a pixel on the screen; empty character buffer."""
        if pagenum is None:
            pagenum = self._apagenum
        if self.graph_view.contains(x, y):
            self._pixels.pages[pagenum].put_pixel(x, y, index)
            self._queues.video.put(signals.Event(signals.VIDEO_PUT_PIXEL, (pagenum, x, y, index)))
            self.clear_text_at(x, y)

    def get_pixel(self, x, y, pagenum=None):
        """Return the attribute a pixel on the screen."""
        if pagenum is None:
            pagenum = self._apagenum
        return self._pixels.pages[pagenum].get_pixel(x, y)

    def get_interval(self, pagenum, x, y, length):
        """Read a scanline interval into a list of attributes."""
        return self._pixels.pages[pagenum].get_interval(x, y, length)

    def put_interval(self, pagenum, x, y, colours, mask=0xff):
        """Write a list of attributes to a scanline interval."""
        x, y, colours = self.graph_view.clip_list(x, y, colours)
        newcolours = self._pixels.pages[pagenum].put_interval(x, y, colours, mask)
        self._queues.video.put(signals.Event(signals.VIDEO_PUT_INTERVAL, (pagenum, x, y, newcolours)))
        self.clear_text_area(x, y, x+len(colours), y)

    def fill_interval(self, x0, x1, y, index):
        """Fill a scanline interval in a solid attribute."""
        x0, x1, y = self.graph_view.clip_interval(x0, x1, y)
        self._pixels.pages[self._apagenum].fill_interval(x0, x1, y, index)
        self._queues.video.put(signals.Event(signals.VIDEO_FILL_INTERVAL,
                        (self._apagenum, x0, x1, y, index)))
        self.clear_text_area(x0, y, x1, y)

    def get_until(self, x0, x1, y, c):
        """Get the attribute values of a scanline interval."""
        return self._pixels.pages[self._apagenum].get_until(x0, x1, y, c)

    def get_rect(self, x0, y0, x1, y1):
        """Read a screen rect into an [y][x] array of attributes."""
        return self._pixels.pages[self._apagenum].get_rect(x0, y0, x1, y1)

    def put_rect(self, x0, y0, x1, y1, sprite, operation_token):
        """Apply an [y][x] array of attributes onto a screen rect."""
        x0, y0, x1, y1, sprite = self.graph_view.clip_area(x0, y0, x1, y1, sprite)
        rect = self._pixels.pages[self._apagenum].put_rect(x0, y0, x1, y1,
                                                        sprite, operation_token)
        self._queues.video.put(signals.Event(signals.VIDEO_PUT_RECT,
                              (self._apagenum, x0, y0, x1, y1, rect)))
        self.clear_text_area(x0, y0, x1, y1)

    def fill_rect(self, x0, y0, x1, y1, index):
        """Fill a rectangle in a solid attribute."""
        x0, y0, x1, y1 = self.graph_view.clip_rect(x0, y0, x1, y1)
        self._pixels.pages[self._apagenum].fill_rect(x0, y0, x1, y1, index)
        self._queues.video.put(signals.Event(signals.VIDEO_FILL_RECT,
                                (self._apagenum, x0, y0, x1, y1, index)))
        self.clear_text_area(x0, y0, x1, y1)

    ## VIEW graphics viewport

    def view_(self, args):
        """VIEW: Set/unset the graphics viewport and optionally draw a box."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        absolute = next(args)
        try:
            x0, y0, x1, y1 = (round(values.to_single(next(args)).to_value()) for _ in range(4))
            error.range_check(0, self._mode.pixel_width-1, x0, x1)
            error.range_check(0, self._mode.pixel_height-1, y0, y1)
            fill = next(args)
            if fill is not None:
                fill = values.to_int(fill)
            border = next(args)
            if border is not None:
                border = values.to_int(border)
            list(args)
            self.set_view(x0, y0, x1, y1, absolute, fill, border)
        except StopIteration:
            self.unset_view()

    def set_view(self, x0, y0, x1, y1, absolute, fill, border):
        """Set the graphics viewport and optionally draw a box (VIEW)."""
        # first unset the viewport so that we can draw the box
        self.graph_view.unset()
        if fill is not None:
            self.draw_box_filled(x0, y0, x1, y1, fill)
            self.last_attr = fill
        if border is not None:
            self.draw_box(x0-1, y0-1, x1+1, y1+1, border)
            self.last_attr = border
        self.graph_view.set(x0, y0, x1, y1, absolute)
        self.last_point = self.graph_view.get_mid()
        if self.window_bounds is not None:
            self.set_window(*self.window_bounds)

    def unset_view(self):
        """Unset the graphics viewport."""
        self.graph_view.unset()
        self.last_point = self.graph_view.get_mid()
        if self.window_bounds is not None:
            self.set_window(*self.window_bounds)

    ### WINDOW logical coords

    def window_(self, args):
        """WINDOW: Set/unset the logical coordinate window."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        cartesian = not next(args)
        coords = list(values.to_single(next(args)).to_value() for _ in range(4))
        if not coords:
            self.unset_window()
        else:
            x0, y0, x1, y1 = coords
            if x0 == x1 or y0 == y1:
                raise error.BASICError(error.IFC)
            list(args)
            self.set_window(x0, y0, x1, y1, cartesian)

    def set_window(self, fx0, fy0, fx1, fy1, cartesian=True):
        """Set the logical coordinate window (WINDOW)."""
        if fy0 > fy1:
            fy0, fy1 = fy1, fy0
        if fx0 > fx1:
            fx0, fx1 = fx1, fx0
        if cartesian:
            fy0, fy1 = fy1, fy0
        left, top, right, bottom = self.graph_view.get()
        x0, y0 = 0., 0.
        x1, y1 = float(right-left), float(bottom-top)
        scalex = (x1-x0) / (fx1-fx0)
        scaley = (y1-y0) / (fy1-fy0)
        offsetx = x0 - fx0*scalex
        offsety = y0 - fy0*scaley
        self.window = scalex, scaley, offsetx, offsety
        self.window_bounds = fx0, fy0, fx1, fy1, cartesian

    def unset_window(self):
        """Unset the logical coordinate window."""
        self.window = None
        self.window_bounds = None

    def window_is_set(self):
        """Return whether the logical coordinate window is set."""
        return self.window is not None

    def get_window_physical(self, fx, fy, step=False):
        """Convert logical to physical coordinates."""
        if self.window:
            scalex, scaley, offsetx, offsety = self.window
            if step:
                fx0, fy0 = self.get_window_logical(*self.last_point)
            else:
                fx0, fy0 = 0., 0.
            x = int(round(offsetx + (fx0+fx) * scalex))
            y = int(round(offsety + (fy0+fy) * scaley))
        else:
            x, y = self.last_point if step else (0, 0)
            x += int(round(fx))
            y += int(round(fy))
        # overflow check
        if x < -0x8000 or y < -0x8000 or x > 0x7fff or y > 0x7fff:
            raise error.BASICError(error.OVERFLOW)
        return x, y

    def get_window_logical(self, x, y):
        """Convert physical to logical coordinates."""
        x, y = float(x), float(y)
        if self.window:
            scalex, scaley, offsetx, offsety = self.window
            return (x - offsetx) / scalex,  (y - offsety) / scaley
        else:
            return x, y

    def _get_window_scale(self, fx, fy):
        """Get logical to physical scale factor."""
        if self.window:
            scalex, scaley, _, _ = self.window
            x, y = int(round(fx * scalex)), int(round(fy * scaley))
        else:
            x, y = int(round(fx)), int(round(fy))
        error.range_check_err(-32768, 32767, x, error.OVERFLOW)
        error.range_check_err(-32768, 32767, y, error.OVERFLOW)
        return x, y

    ### PSET, POINT

    def pset_(self, args):
        """PSET: set a pixel to a given attribute, or foreground."""
        self._pset_preset(args, -1)

    def preset_(self, args):
        """PRESET: set a pixel to a given attribute, or background."""
        self._pset_preset(args, 0)

    def _pset_preset(self, args, default):
        """Set a pixel to a given attribute."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        step = next(args)
        x, y = (values.to_single(next(args)).to_value() for _ in range(2))
        c = next(args)
        if c is None:
            c = default
        else:
            c = values.to_int(c)
            error.range_check(0, 255, c)
        list(args)
        x, y = self.graph_view.coords(*self.get_window_physical(x, y, step))
        c = self.get_attr_index(c)
        self.put_pixel(x, y, c)
        self.last_attr = c
        self.last_point = x, y

    ### LINE

    def line_(self, args):
        """LINE: Draw a patterned line or box."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        step0 = next(args)
        x0, y0 = (None if arg is None else values.to_single(arg).to_value() for _, arg in zip(range(2), args))
        step1 = next(args)
        x1, y1 = (values.to_single(next(args)).to_value() for _ in range(2))
        coord0 = x0, y0, step0
        coord1 = x1, y1, step1
        c = next(args)
        if c:
            c = values.to_int(c)
            error.range_check(0, 255, c)
        shape, pattern = args
        if c is None:
            c = -1
        if pattern is None:
            pattern = 0xffff
        else:
            pattern = values.to_int(pattern)
        if coord0 != (None, None, None):
            x0, y0 = self.graph_view.coords(*self.get_window_physical(*coord0))
        else:
            x0, y0 = self.last_point
        x1, y1 = self.graph_view.coords(*self.get_window_physical(*coord1))
        c = self.get_attr_index(c)
        if not shape:
            self.draw_line(x0, y0, x1, y1, c, pattern)
        elif shape == 'B':
            self.draw_box(x0, y0, x1, y1, c, pattern)
        elif shape == 'BF':
            self.draw_box_filled(x0, y0, x1, y1, c)
        self.last_point = x1, y1
        self.last_attr = c

    def draw_line(self, x0, y0, x1, y1, c, pattern=0xffff):
        """Draw a line between the given physical points."""
        # cut off any out-of-bound coordinates
        x0, y0 = self._mode.cutoff_coord(x0, y0)
        x1, y1 = self._mode.cutoff_coord(x1, y1)
        if y1 <= y0:
            # work from top to bottom, or from x1,y1 if at the same height. this matters for mask.
            x1, y1, x0, y0 = x0, y0, x1, y1
        # Bresenham algorithm
        dx, dy = abs(x1-x0), abs(y1-y0)
        steep = dy > dx
        if steep:
            x0, y0, x1, y1 = y0, x0, y1, x1
            dx, dy = dy, dx
        sx = 1 if x1 > x0 else -1
        sy = 1 if y1 > y0 else -1
        mask = 0x8000
        line_error = dx / 2
        x, y = x0, y0
        for x in xrange(x0, x1+sx, sx):
            if pattern & mask != 0:
                if steep:
                    self.put_pixel(y, x, c)
                else:
                    self.put_pixel(x, y, c)
            mask >>= 1
            if mask == 0:
                mask = 0x8000
            line_error -= dy
            if line_error < 0:
                y += sy
                line_error += dx

    def draw_box_filled(self, x0, y0, x1, y1, c):
        """Draw a filled box between the given corner points."""
        x0, y0 = self._mode.cutoff_coord(x0, y0)
        x1, y1 = self._mode.cutoff_coord(x1, y1)
        if y1 < y0:
            y0, y1 = y1, y0
        if x1 < x0:
            x0, x1 = x1, x0
        self.fill_rect(x0, y0, x1, y1, c)

    def draw_box(self, x0, y0, x1, y1, c, pattern=0xffff):
        """Draw an empty box between the given corner points."""
        x0, y0 = self._mode.cutoff_coord(x0, y0)
        x1, y1 = self._mode.cutoff_coord(x1, y1)
        mask = 0x8000
        mask = self.draw_straight(x1, y1, x0, y1, c, pattern, mask)
        mask = self.draw_straight(x1, y0, x0, y0, c, pattern, mask)
        # verticals always drawn top to bottom
        if y0 < y1:
            y0, y1 = y1, y0
        mask = self.draw_straight(x1, y1, x1, y0, c, pattern, mask)
        mask = self.draw_straight(x0, y1, x0, y0, c, pattern, mask)

    def draw_straight(self, x0, y0, x1, y1, c, pattern, mask):
        """Draw a horizontal or vertical line."""
        if x0 == x1:
            p0, p1, q, direction = y0, y1, x0, 'y'
        else:
            p0, p1, q, direction = x0, x1, y0, 'x'
        sp = 1 if p1 > p0 else -1
        for p in range(p0, p1+sp, sp):
            if pattern & mask != 0:
                if direction == 'x':
                    self.put_pixel(p, q, c)
                else:
                    self.put_pixel(q, p, c)
            mask >>= 1
            if mask == 0:
                mask = 0x8000
        return mask

    ### CIRCLE: circle, ellipse, sectors

    # NOTES ON THE MIDPOINT ALGORITHM
    #
    # CIRCLE:
    # x*x + y*y == r*r
    # look at y'=y+1
    # err(y) = y*y+x*x-r*r
    # err(y') = y*y + 2y+1 + x'*x' - r*r == err(y) + x'*x' -x*x + 2y+1
    # if x the same:
    #   err(y') == err(y) +2y+1
    # if x -> x-1:
    #   err(y') == err(y) +2y+1 -2x+1 == err(y) +2(y-x+1)
    #
    # why initialise error with 1-x == 1-r?
    # we change x if the radius is more than 0.5pix out so
    #     err(y, r+0.5) == y*y + x*x - (r*r+r+0.25) == err(y,r) - r - 0.25 >0
    # with err and r both integers, this just means
    #     err - r > 0 <==> err - r +1 >= 0
    # above, error == err(y) -r + 1 and we change x if it's >=0.
    #
    # ELLIPSE:
    # ry^2*x^2 + rx^2*y^2 == rx^2*ry^2
    # look at y'=y+1 (quadrant between points of 45deg slope)
    # err == ry^2*x^2 + rx^2*y^2 - rx^2*ry^2
    # err(y') == rx^2*(y^2+2y+1) + ry^2(x'^2)- rx^2*ry^2
    #         == err(y) + ry^2(x'^2-x^2) + rx^2*(2y+1)
    # if x the same:
    #   err(y') == err(y) + rx^2*(2y+1)
    # if x' -> x-1:
    #   err(y') == err(y) + rx^2*(2y+1) +rx^2(-2x+1)
    #
    # change x if radius more than 0.5pix out:
    #      err(y, rx+0.5, ry) == ry^2*y*y+rx^2*x*x - (ry*ry)*(rx*rx+rx+0.25) > 0
    #  ==> err(y) - (rx+0.25)*(ry*ry) > 0
    #  ==> err(y) - (rx*ry*ry + 0.25*ry*ry ) > 0
    #
    # break yinc loop if one step no longer suffices

    def circle_(self, args):
        """CIRCLE: Draw a circle, ellipse, arc or sector."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        step = next(args)
        x, y = (values.to_single(next(args)).to_value() for _ in range(2))
        r = values.to_single(next(args)).to_value()
        error.throw_if(r < 0)
        c = next(args)
        if c is not None:
            c = values.to_int(c)
        start = next(args)
        if start is not None:
            start = values.to_single(start).to_value()
        stop = next(args)
        if stop is not None:
            stop = values.to_single(stop).to_value()
        aspect = next(args)
        if aspect is not None:
            aspect = values.to_single(aspect).to_value()
        list(args)
        x0, y0 = self.graph_view.coords(*self.get_window_physical(x, y, step))
        if c is None:
            c = -1
        else:
            error.range_check(0, 255, c)
        c = self.get_attr_index(c)
        if aspect is None:
            aspect = self._mode.pixel_aspect[0] / float(self._mode.pixel_aspect[1])
        if aspect == 1.:
            rx, _ = self._get_window_scale(r, 0.)
            ry = rx
        elif aspect > 1.:
            _, ry = self._get_window_scale(0., r)
            rx = int(round(r / aspect))
        else:
            rx, _ = self._get_window_scale(r, 0.)
            ry = int(round(r * aspect))
        start_octant, start_coord, start_line = -1, -1, False
        if start:
            start_octant, start_coord, start_line = _get_octant(start, rx, ry)
        stop_octant, stop_coord, stop_line = -1, -1, False
        if stop:
            stop_octant, stop_coord, stop_line = _get_octant(stop, rx, ry)
        if aspect == 1.:
            self.draw_circle(x0, y0, rx, c,
                             start_octant, start_coord, start_line,
                             stop_octant, stop_coord, stop_line)
        else:
            startx, starty, stopx, stopy = -1, -1, -1, -1
            if start is not None:
                startx = abs(int(round(rx * math.cos(start))))
                starty = abs(int(round(ry * math.sin(start))))
            if stop is not None:
                stopx = abs(int(round(rx * math.cos(stop))))
                stopy = abs(int(round(ry * math.sin(stop))))
            self.draw_ellipse(x0, y0, rx, ry, c,
                              start_octant/2, startx, starty, start_line,
                              stop_octant/2, stopx, stopy, stop_line)
        self.last_attr = c
        self.last_point = x0, y0

    def draw_circle(self, x0, y0, r, c,
                    oct0=-1, coo0=-1, line0=False,
                    oct1=-1, coo1=-1, line1=False):
        """Draw a circle sector using the midpoint algorithm."""
        # see e.g. http://en.wikipedia.org/wiki/Midpoint_circle_algorithm
        # find invisible octants
        if oct0 == -1:
            hide_oct = range(0,0)
        elif oct0 < oct1 or oct0 == oct1 and _octant_gte(oct0, coo1, coo0):
            hide_oct = range(0, oct0) + range(oct1+1, 8)
        else:
            hide_oct = range(oct1+1, oct0)
        # if oct1==oct0:
        # ----|.....|--- : coo1 lt coo0 : print if y in [0,coo1] or in [coo0, r]
        # ....|-----|... ; coo1 gte coo0: print if y in [coo0,coo1]
        x, y = r, 0
        bres_error = 1-r
        while x >= y:
            for octant in range(0,8):
                if octant in hide_oct:
                    continue
                elif oct0 != oct1 and octant == oct0 and _octant_gt(oct0, coo0, y):
                    continue
                elif oct0 != oct1 and octant == oct1 and _octant_gt(oct1, y, coo1):
                    continue
                elif oct0 == oct1 and octant == oct0:
                    # if coo1 >= coo0
                    if _octant_gte(oct0, coo1, coo0):
                        # if y > coo1 or y < coo0
                        # (don't draw if y is outside coo's)
                        if _octant_gt(oct0, y, coo1) or _octant_gt(oct0, coo0,y):
                            continue
                    else:
                        # if coo0 > y > c001
                        # (don't draw if y is between coo's)
                        if _octant_gt(oct0, y, coo1) and _octant_gt(oct0, coo0, y):
                            continue
                self.put_pixel(*_octant_coord(octant, x0, y0, x, y), index=c)
            # remember endpoints for pie sectors
            if y == coo0:
                coo0x = x
            if y == coo1:
                coo1x = x
            # bresenham error step
            y += 1
            if bres_error < 0:
                bres_error += 2*y+1
            else:
                x -= 1
                bres_error += 2*(y-x+1)
        # draw pie-slice lines
        if line0:
            self.draw_line(x0, y0, *_octant_coord(oct0, x0, y0, coo0x, coo0), c=c)
        if line1:
            self.draw_line(x0, y0, *_octant_coord(oct1, x0, y0, coo1x, coo1), c=c)

    def draw_ellipse(self, cx, cy, rx, ry, c,
                     qua0=-1, x0=-1, y0=-1, line0=False,
                     qua1=-1, x1=-1, y1=-1, line1=False):
        """Draw ellipse using the midpoint algorithm."""
        # for algorithm see http://members.chello.at/~easyfilter/bresenham.html
        # find invisible quadrants
        if qua0 == -1:
            hide_qua = range(0,0)
        elif qua0 < qua1 or qua0 == qua1 and _quadrant_gte(qua0, x1, y1, x0, y0):
            hide_qua = range(0, qua0) + range(qua1+1, 4)
        else:
            hide_qua = range(qua1+1,qua0)
        # error increment
        dx = 16 * (1-2*rx) * ry * ry
        dy = 16 * rx * rx
        ddy = 32 * rx * rx
        ddx = 32 * ry * ry
        # error for first step
        err = dx + dy
        x, y = rx, 0
        while True:
            for quadrant in range(0,4):
                # skip invisible arc sectors
                if quadrant in hide_qua:
                    continue
                elif qua0 != qua1 and quadrant == qua0 and _quadrant_gt(qua0, x0, y0, x, y):
                    continue
                elif qua0 != qua1 and quadrant == qua1 and _quadrant_gt(qua1, x, y, x1, y1):
                    continue
                elif qua0 == qua1 and quadrant == qua0:
                    if _quadrant_gte(qua0, x1, y1, x0, y0):
                        if _quadrant_gt(qua0, x, y, x1, y1) or _quadrant_gt(qua0, x0, y0, x, y):
                            continue
                    else:
                        if _quadrant_gt(qua0, x, y, x1, y1) and _quadrant_gt(qua0, x0, y0, x, y):
                            continue
                self.put_pixel(*_quadrant_coord(quadrant, cx, cy, x, y), index=c)
            # bresenham error step
            e2 = 2 * err
            if (e2 <= dy):
                y += 1
                dy += ddy
                err += dy
            if (e2 >= dx or e2 > dy):
                x -= 1
                dx += ddx
                err += dx
            # NOTE - err changes sign at the change from y increase to x increase
            if (x < 0):
                break
        # too early stop of flat vertical ellipses
        # finish tip of ellipse
        while (y < ry):
            self.put_pixel(cx, cy+y, c)
            self.put_pixel(cx, cy-y, c)
            y += 1
        # draw pie-slice lines
        if line0:
            self.draw_line(cx, cy, *_quadrant_coord(qua0, cx, cy, x0, y0), c=c)
        if line1:
            self.draw_line(cx, cy, *_quadrant_coord(qua1, cx, cy, x1, y1), c=c)

    ### PAINT: Flood fill

    def paint_(self, args):
        """PAINT: Fill an area defined by a border attribute with a tiled pattern."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        step = next(args)
        x, y = (values.to_single(next(args)).to_value() for _ in range(2))
        coord = x, y, step
        c, pattern = -1, None
        cval = next(args)
        if isinstance(cval, values.String):
            # pattern given; copy
            pattern = cval.to_str()
            # empty pattern "" is illegal function call
            error.throw_if(not pattern)
            # default for border, if pattern is specified as string: foreground attr
        elif cval is not None:
            c = values.to_int(cval)
            error.range_check(0, 255, c)
        border = next(args)
        if border is not None:
            border = values.to_int(border)
            error.range_check(0, 255, border)
        background = next(args)
        if background is not None:
            background = values.pass_string(background, err=error.IFC).to_str()
        list(args)
        # if paint *colour* specified, border default = paint colour
        # if paint *attribute* specified, border default = current foreground
        if border is None:
            border = c
        # only in screen 7,8,9 is this an error (use ega memory as a check)
        if (pattern and background and background[:len(pattern)] == pattern and
                self._mode.video_segment == 0xa000):
            raise error.BASICError(error.IFC)
        self.flood_fill(coord, c, pattern, border, background)

    def flood_fill(self, lcoord, c, pattern, border, background):
        """Fill an area defined by a border attribute with a tiled pattern."""
        # 4-way scanline flood fill: http://en.wikipedia.org/wiki/Flood_fill
        # flood fill stops on border colour in all directions; it also stops on scanlines in fill_colour
        # pattern tiling stops at intervals that equal the pattern to be drawn, unless this pattern is
        # also equal to the background pattern.
        c, border = self.get_attr_index(c), self.get_attr_index(border)
        solid = (pattern is None)
        if not solid:
            tile = self._mode.build_tile(bytearray(pattern)) if pattern else None
            back = self._mode.build_tile(bytearray(background)) if background else None
        else:
            tile, back = [[c]*8], None
        bound_x0, bound_y0, bound_x1, bound_y1 = self.graph_view.get()
        x, y = self.graph_view.coords(*self.get_window_physical(*lcoord))
        line_seed = [(x, x, y, 0)]
        # paint nothing if seed is out of bounds
        if x < bound_x0 or x > bound_x1 or y < bound_y0 or y > bound_y1:
            return
        self.last_point = x, y
        # paint nothing if we start on border attrib
        if self.get_pixel(x,y) == border:
            return
        while len(line_seed) > 0:
            # consider next interval
            x_start, x_stop, y, ydir = line_seed.pop()
            # extend interval as far as it goes to left and right
            x_left = x_start - len(self.get_until(x_start-1, bound_x0-1, y, border))
            x_right = x_stop + len(self.get_until(x_stop+1, bound_x1+1, y, border))
            # check next scanlines and add intervals to the list
            if ydir == 0:
                if y + 1 <= bound_y1:
                    line_seed = self.check_scanline(line_seed, x_left, x_right, y+1, c, tile, back, border, 1)
                if y - 1 >= bound_y0:
                    line_seed = self.check_scanline(line_seed, x_left, x_right, y-1, c, tile, back, border, -1)
            else:
                # check the same interval one scanline onward in the same direction
                if y+ydir <= bound_y1 and y+ydir >= bound_y0:
                    line_seed = self.check_scanline(line_seed, x_left, x_right, y+ydir, c, tile, back, border, ydir)
                # check any bit of the interval that was extended one scanline backward
                # this is where the flood fill goes around corners.
                if y-ydir <= bound_y1 and y-ydir >= bound_y0:
                    line_seed = self.check_scanline(line_seed, x_left, x_start-1, y-ydir, c, tile, back, border, -ydir)
                    line_seed = self.check_scanline(line_seed, x_stop+1, x_right, y-ydir, c, tile, back, border, -ydir)
            # draw the pixels for the current interval
            if solid:
                self.fill_interval(x_left, x_right, y, tile[0][0])
            else:
                interval = tile_to_interval(x_left, x_right, y, tile)
                self.put_interval(self._apagenum, x_left, y, interval)
            # allow interrupting the paint
            if y%4 == 0:
                self._input_methods.wait()
        self.last_attr = c

    def check_scanline(self, line_seed, x_start, x_stop, y,
                       c, tile, back, border, ydir):
        """Append all subintervals between border colours to the scanning stack."""
        if x_stop < x_start:
            return line_seed
        x_start_next = x_start
        x_stop_next = x_start_next-1
        rtile = tile[y%len(tile)]
        if back:
            rback = back[y%len(back)]
        x = x_start
        while x <= x_stop:
            # scan horizontally until border colour found, then append interval & continue scanning
            pattern = self.get_until(x, x_stop+1, y, border)
            x_stop_next = x + len(pattern) - 1
            x = x_stop_next + 1
            # never match zero pattern (special case)
            has_same_pattern = (rtile != [0]*8)
            for pat_x in range(len(pattern)):
                if not has_same_pattern:
                    break
                tile_x = (x_start_next + pat_x) % 8
                has_same_pattern &= (pattern[pat_x] == rtile[tile_x])
                has_same_pattern &= (not back or pattern[pat_x] != rback[tile_x])
            # we've reached a border colour, append our interval & start a new one
            # don't append if same fill colour/pattern, to avoid infinite loops over bits already painted (eg. 00 shape)
            if x_stop_next >= x_start_next and not has_same_pattern:
                line_seed.append([x_start_next, x_stop_next, y, ydir])
            x_start_next = x + 1
            x += 1
        return line_seed

    ### PUT and GET: Sprite operations

    def put_(self, args):
        """PUT: Put a sprite on the screen."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        x0, y0 = (values.to_single(next(args)).to_value() for _ in range(2))
        array_name, operation_token = args
        array_name = self._memory.complete_name(array_name)
        operation_token = operation_token or tk.XOR
        if array_name not in self._memory.arrays:
            raise error.BASICError(error.IFC)
        elif array_name[-1] == values.STR:
            raise error.BASICError(error.TYPE_MISMATCH)
        x0, y0 = self.graph_view.coords(*self.get_window_physical(x0, y0))
        self.last_point = x0, y0
        try:
            byte_array = self._memory.arrays.view_full_buffer(array_name)
            spriterec = self._memory.arrays.get_cache(array_name)
        except KeyError:
            byte_array = bytearray()
            spriterec = None
        if spriterec is not None:
            dx, dy, sprite = spriterec
        else:
            # we don't have it stored or it has been modified
            dx, dy = self._mode.record_to_sprite_size(byte_array)
            sprite = self._mode.array_to_sprite(byte_array, 4, dx, dy)
            # store it now that we have it!
            self._memory.arrays.set_cache(array_name, (dx, dy, sprite))
        # sprite must be fully inside *viewport* boundary
        x1, y1 = x0+dx-1, y0+dy-1
        # Tandy screen 6 sprites are twice as wide as claimed
        if self._mode.name == '640x200x4':
            x1 = x0 + 2*dx - 1
        # illegal fn call if outside viewport boundary
        vx0, vy0, vx1, vy1 = self.graph_view.get()
        error.range_check(vx0, vx1, x0, x1)
        error.range_check(vy0, vy1, y0, y1)
        # apply the sprite to the screen
        self.put_rect(x0, y0, x1, y1, sprite, operation_token)

    def get_(self, args):
        """GET: Read a sprite from the screen."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        x0, y0 = (values.to_single(next(args)).to_value() for _ in range(2))
        step = next(args)
        x, y = (values.to_single(next(args)).to_value() for _ in range(2))
        lcoord1 = x, y, step
        array_name, = args
        array_name = self._memory.complete_name(array_name)
        if array_name not in self._memory.arrays:
            raise error.BASICError(error.IFC)
        elif array_name[-1] == values.STR:
            raise error.BASICError(error.TYPE_MISMATCH)
        x0, y0 = self.graph_view.coords(*self.get_window_physical(x0, y0))
        x1, y1 = self.graph_view.coords(*self.get_window_physical(*lcoord1))
        self.last_point = x1, y1
        try:
            byte_array = self._memory.arrays.view_full_buffer(array_name)
        except KeyError:
            raise error.BASICError(error.IFC)
        y0, y1 = sorted((y0, y1))
        x0, x1 = sorted((x0, x1))
        dx, dy = x1-x0+1, y1-y0+1
        # Tandy screen 6 simply GETs twice the width, it seems
        if self._mode.name == '640x200x4':
            x1 = x0 + 2*dx - 1
        # illegal fn call if outside viewport boundary
        vx0, vy0, vx1, vy1 = self.graph_view.get()
        error.range_check(vx0, vx1, x0, x1)
        error.range_check(vy0, vy1, y0, y1)
        # set size record
        byte_array[0:4] = self._mode.sprite_size_to_record(dx, dy)
        # read from screen and convert to byte array
        sprite = self.get_rect(x0, y0, x1, y1)
        try:
            self._mode.sprite_to_array(sprite, dx, dy, byte_array, 4)
        except ValueError as e:
            raise error.BASICError(error.IFC)
        # store a copy in the sprite store
        self._memory.arrays.set_cache(array_name, (dx, dy, sprite))

    ### DRAW statement

    def draw_(self, args):
        """DRAW: Execute a Graphics Macro Language string."""
        if self._mode.is_text_mode:
            raise error.BASICError(error.IFC)
        gml = values.next_string(args)
        self.draw(gml)
        list(args)

    def draw(self, gml):
        """Execute a Graphics Macro Language string."""
        # don't convert to uppercase as VARPTR$ elements are case sensitive
        gmls = mlparser.MLParser(gml, self._memory, self._values)
        plot, goback = True, False
        while True:
            c = gmls.skip_blank_read().upper()
            if c == '':
                break
            elif c == ';':
                continue
            elif c == 'B':
                # do not draw
                plot = False
            elif c == 'N':
                # return to postiton after move
                goback = True
            elif c == 'X':
                # execute substring
                sub = gmls.parse_string()
                self.draw(sub)
            elif c == 'C':
                # set foreground colour
                # allow empty spec (default 0), but only if followed by a semicolon
                if gmls.skip_blank() == ';':
                    self.last_attr = 0
                else:
                    attr = gmls.parse_number()
                    # 100000 seems to be GW's limit
                    error.range_check(-99999, 99999, attr)
                    self.last_attr = attr
            elif c == 'S':
                # set scale
                scale = gmls.parse_number()
                error.range_check(1, 255, scale)
                self.draw_scale = scale
            elif c == 'A':
                # set angle
                # allow empty spec (default 0), but only if followed by a semicolon
                if gmls.skip_blank() == ';':
                    self.draw_angle = 0
                else:
                    angle = gmls.parse_number()
                    error.range_check(0, 3, angle)
                    self.draw_angle = 90 * angle
            elif c == 'T':
                # 'turn angle' - set (don't turn) the angle to any value
                if gmls.read(1).upper() != 'A':
                    raise error.BASICError(error.IFC)
                # allow empty spec (default 0), but only if followed by a semicolon
                if gmls.skip_blank() == ';':
                    self.draw_angle = 0
                else:
                    angle = gmls.parse_number()
                    error.range_check(-360, 360, angle)
                    self.draw_angle = angle
            # one-variable movement commands:
            elif c in ('U', 'D', 'L', 'R', 'E', 'F', 'G', 'H'):
                step = gmls.parse_number(default=1)
                # 100000 seems to be GW's limit
                error.range_check(-99999, 99999, step)
                x0, y0 = self.last_point
                x1, y1 = 0, 0
                if c in ('U', 'E', 'H'):
                    y1 -= step
                elif c in ('D', 'F', 'G'):
                    y1 += step
                if c in ('L', 'G', 'H'):
                    x1 -= step
                elif c in ('R', 'E', 'F'):
                    x1 += step
                self.draw_step(x0, y0, x1, y1, plot, goback)
                plot = True
                goback = False
            # two-variable movement command
            elif c == 'M':
                relative = gmls.skip_blank() in ('+','-')
                x = gmls.parse_number()
                error.range_check(-9999, 9999, x)
                if gmls.skip_blank() != ',':
                    raise error.BASICError(error.IFC)
                else:
                    gmls.read(1)
                y = gmls.parse_number()
                error.range_check(-9999, 9999, y)
                x0, y0 = self.last_point
                if relative:
                    self.draw_step(x0, y0, x, y, plot, goback)
                else:
                    if plot:
                        self.draw_line(x0, y0, x, y, self.last_attr)
                    self.last_point = x, y
                    if goback:
                        self.last_point = x0, y0
                plot = True
                goback = False
            elif c == 'P':
                # paint - flood fill
                colour = gmls.parse_number()
                error.range_check(0, 9999, colour)
                if gmls.skip_blank_read() != ',':
                    raise error.BASICError(error.IFC)
                bound = gmls.parse_number()
                error.range_check(0, 9999, bound)
                x, y = self.get_window_logical(*self.last_point)
                self.flood_fill((x, y, False), colour, None, bound, None)
            else:
                raise error.BASICError(error.IFC)

    def draw_step(self, x0, y0, sx, sy, plot, goback):
        """Make a DRAW step, drawing a line and returning if requested."""
        scale = self.draw_scale
        rotate = self.draw_angle
        aspect = self._mode.pixel_aspect
        yfac = aspect[1] / (1.*aspect[0])
        x1 = (scale*sx) / 4
        y1 = (scale*sy) / 4
        if rotate == 0 or rotate == 360:
            pass
        elif rotate == 90:
            x1, y1 = int(y1*yfac), -int(x1//yfac)
        elif rotate == 180:
            x1, y1 = -x1, -y1
        elif rotate == 270:
            x1, y1 = -int(y1*yfac), int(x1//yfac)
        else:
            fx, fy = float(x1), float(y1)
            # degrees to radians
            phi = rotate * math.pi / 180.
            sinr, cosr = math.sin(phi), math.cos(phi)
            fxfac = float(aspect[0]) / float(aspect[1])
            fx = cosr*fx + (sinr*fy) / fxfac
            fy = (cosr*fy) * fxfac - sinr*fx
            x1, y1 = int(round(fx)), int(round(fy))
        y1 += y0
        x1 += x0
        if plot:
            self.draw_line(x0, y0, x1, y1, self.last_attr)
        self.last_point = x1, y1
        if goback:
            self.last_point = x0, y0

    ### POINT and PMAP

    def point_(self, args):
        """POINT (1 argument): Return current coordinate (2 arguments): Return the attribute of a pixel."""
        arg0 = next(args)
        arg1 = next(args)
        if arg1 is None:
            arg0 = values.to_integer(arg0)
            fn = values.to_int(arg0)
            error.range_check(0, 3, fn)
            list(args)
            if self._mode.is_text_mode:
                return self._values.new_single()
            if fn in (0, 1):
                point = self.last_point[fn]
            elif fn in (2, 3):
                point = self.get_window_logical(*self.last_point)[fn - 2]
            return self._values.new_single().from_value(point)
        else:
            if self._mode.is_text_mode:
                raise error.BASICError(error.IFC)
            arg1 = values.pass_number(arg1)
            list(args)
            x, y = values.to_single(arg0).to_value(), values.to_single(arg1).to_value()
            x, y = self.graph_view.coords(*self.get_window_physical(x, y))
            if x < 0 or x >= self._mode.pixel_width or y < 0 or y >= self._mode.pixel_height:
                point = -1
            else:
                point = self.get_pixel(x, y)
            return self._values.new_integer().from_int(point)

    def pmap_(self, args):
        """PMAP: convert between logical and physical coordinates."""
        # create a new Single for the return value
        coord = values.to_single(next(args))
        mode = values.to_integer(next(args))
        list(args)
        mode = mode.to_int()
        error.range_check(0, 3, mode)
        if self._mode.is_text_mode:
            if mode in (2, 3):
                values.to_integer(coord)
            value = 0
        elif mode == 0:
            value, _ = self.get_window_physical(values.to_single(coord).to_value(), 0.)
        elif mode == 1:
            _, value = self.get_window_physical(0., values.to_single(coord).to_value())
        elif mode == 2:
            value, _ = self.get_window_logical(values.to_integer(coord).to_int(), 0)
        elif mode == 3:
            _, value = self.get_window_logical(0, values.to_integer(coord).to_int())
        return self._values.new_single().from_value(value)


def tile_to_interval(x0, x1, y, tile):
    """Convert a tile to a list of attributes."""
    dx = x1 - x0 + 1
    h = len(tile)
    w = len(tile[0])
    if numpy:
        # fast method using numpy instead of loop
        ntile = numpy.roll(numpy.array(tile).astype(int)[y % h], int(-x0 % 8))
        return numpy.tile(ntile, (dx+w-1) / w)[:dx]
    else:
        return [tile[y % h][x % 8] for x in xrange(x0, x1+1)]


###############################################################################
# octant logic for CIRCLE

def _get_octant(f, rx, ry):
    """Get the circle octant for a given coordinate."""
    neg = f < 0.
    f = abs(f)
    octant = 0
    comp = math.pi / 4.
    while f > comp:
        comp += math.pi / 4.
        octant += 1
        if octant >= 8:
            raise error.BASICError(error.IFC)
    if octant in (0, 3, 4, 7):
        # running var is y
        coord = abs(int(round(ry * math.sin(f))))
    else:
        # running var is x
        coord = abs(int(round(rx * math.cos(f))))
    return octant, coord, neg

def _octant_coord(octant, x0, y0, x, y):
    """Return symmetrically reflected coordinates for a given pair."""
    if   octant == 7:     return x0+x, y0+y
    elif octant == 0:     return x0+x, y0-y
    elif octant == 4:     return x0-x, y0+y
    elif octant == 3:     return x0-x, y0-y
    elif octant == 6:     return x0+y, y0+x
    elif octant == 1:     return x0+y, y0-x
    elif octant == 5:     return x0-y, y0+x
    elif octant == 2:     return x0-y, y0-x

def _octant_gt(octant, y, coord):
    """Return whether y is further along the circle than coord."""
    if octant%2 == 1:
        return y < coord
    else:
        return y > coord

def _octant_gte(octant, y, coord):
    """Return whether y is further along the circle than coord, or equal."""
    if octant%2 == 1:
        return y <= coord
    else:
        return y >= coord


###############################################################################
# quadrant logic for CIRCLE

def _quadrant_coord(quadrant, x0, y0, x, y):
    """Return symmetrically reflected coordinates for a given pair."""
    if   quadrant == 3:     return x0+x, y0+y
    elif quadrant == 0:     return x0+x, y0-y
    elif quadrant == 2:     return x0-x, y0+y
    elif quadrant == 1:     return x0-x, y0-y

def _quadrant_gt(quadrant, x, y, x0, y0):
    """Return whether y is further along the ellipse than coord."""
    if quadrant%2 == 0:
        if y != y0:
            return y > y0
        else:
            return x < x0
    else:
        if y != y0:
            return y < y0
        else:
            return x > x0

def _quadrant_gte(quadrant, x, y, x0, y0):
    """Return whether y is further along the ellipse than coord, or equal."""
    if quadrant%2 == 0:
        if y != y0:
            return y > y0
        else:
            return x <= x0
    else:
        if y != y0:
            return y < y0
        else:
            return x >= x0
