"""
PC-BASIC - graphics.py
Graphics operations

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    import numpy
except ImportError:
    numpy = None

import math
import io

from . import error
from . import values
from . import mlparser
from . import tokens as tk

# degree-to-radian conversion factor
deg_to_rad = math.pi / 180.


class GraphicsViewPort(object):
    """Graphics viewport (clip area) functions."""

    def __init__(self, screen):
        """Initialise graphics viewport."""
        self.screen = screen
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
            return 0, 0, self.screen.mode.pixel_width-1, self.screen.mode.pixel_height-1

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

    def clear(self):
        """Clear the current graphics viewport."""
        if not self.screen.mode.is_text_mode:
            self.screen.fill_rect(*self.get(), index=(self.screen.attr>>4) & 0x7)


class Drawing(object):
    """Manage graphics drawing."""

    def __init__(self, screen, input_methods, values, memory):
        """Initialise graphics object."""
        self.screen = screen
        self._values = values
        self._memory = memory
        # for wait() in paint_
        self.input_methods = input_methods
        self.init_mode()

    def init_mode(self):
        """Initialise for new graphics mode."""
        self.unset_window()
        self.reset()

    def reset(self):
        """Reset graphics state."""
        if self.screen.mode.is_text_mode:
            return
        self.last_point = self.screen.graph_view.get_mid()
        self.last_attr = self.screen.mode.attr
        self.draw_scale = 4
        self.draw_angle = 0

    ### attributes

    def get_attr_index(self, c):
        """Get the index of the specified attribute."""
        if c == -1:
            # foreground; graphics 'background' attrib is always 0
            c = self.screen.attr & 0xf
        else:
            c = min(self.screen.mode.num_attr-1, max(0, c))
        return c

    ## VIEW graphics viewport

    def view_(self, args):
        """VIEW: Set/unset the graphics viewport and optionally draw a box."""
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        absolute = next(args)
        try:
            x0, y0, x1, y1 = (round(values.to_single(next(args)).to_value()) for _ in range(4))
            error.range_check(0, self.screen.mode.pixel_width-1, x0, x1)
            error.range_check(0, self.screen.mode.pixel_height-1, y0, y1)
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
        self.screen.graph_view.unset()
        if fill is not None:
            self.draw_box_filled(x0, y0, x1, y1, fill)
            self.last_attr = fill
        if border is not None:
            self.draw_box(x0-1, y0-1, x1+1, y1+1, border)
            self.last_attr = border
        self.screen.graph_view.set(x0, y0, x1, y1, absolute)
        self.last_point = self.screen.graph_view.get_mid()
        if self.window_bounds is not None:
            self.set_window(*self.window_bounds)

    def unset_view(self):
        """Unset the graphics viewport."""
        self.screen.graph_view.unset()
        self.last_point = self.screen.graph_view.get_mid()
        if self.window_bounds is not None:
            self.set_window(*self.window_bounds)

    ### WINDOW logical coords

    def window_(self, args):
        """WINDOW: Set/unset the logical coordinate window."""
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        cartesian = not next(args)
        coords = list(values.to_single(next(args)).to_value() for _ in range(4))
        if not coords:
            self.unset_window()
        else:
            x0, y0, x1, y1 = coords
            if x0 == x1 or y0 == y1:
                raise error.RunError(error.IFC)
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
        left, top, right, bottom = self.screen.graph_view.get()
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
            raise error.RunError(error.OVERFLOW)
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
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        step = next(args)
        x, y = (values.to_single(next(args)).to_value() for _ in range(2))
        c = next(args)
        if c is None:
            c = default
        else:
            c = values.to_int(c)
            error.range_check(0, 255, c)
        list(args)
        x, y = self.screen.graph_view.coords(*self.get_window_physical(x, y, step))
        c = self.get_attr_index(c)
        self.screen.put_pixel(x, y, c)
        self.last_attr = c
        self.last_point = x, y

    ### LINE

    def line_(self, args):
        """LINE: Draw a patterned line or box."""
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        coord0 = next(args)
        coord1 = next(args)
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
        if coord0:
            x0, y0 = self.screen.graph_view.coords(*self.get_window_physical(*coord0))
        else:
            x0, y0 = self.last_point
        x1, y1 = self.screen.graph_view.coords(*self.get_window_physical(*coord1))
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
        x0, y0 = self.screen.mode.cutoff_coord(x0, y0)
        x1, y1 = self.screen.mode.cutoff_coord(x1, y1)
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
                    self.screen.put_pixel(y, x, c)
                else:
                    self.screen.put_pixel(x, y, c)
            mask >>= 1
            if mask == 0:
                mask = 0x8000
            line_error -= dy
            if line_error < 0:
                y += sy
                line_error += dx

    def draw_box_filled(self, x0, y0, x1, y1, c):
        """Draw a filled box between the given corner points."""
        x0, y0 = self.screen.mode.cutoff_coord(x0, y0)
        x1, y1 = self.screen.mode.cutoff_coord(x1, y1)
        if y1 < y0:
            y0, y1 = y1, y0
        if x1 < x0:
            x0, x1 = x1, x0
        self.screen.fill_rect(x0, y0, x1, y1, c)

    def draw_box(self, x0, y0, x1, y1, c, pattern=0xffff):
        """Draw an empty box between the given corner points."""
        x0, y0 = self.screen.mode.cutoff_coord(x0, y0)
        x1, y1 = self.screen.mode.cutoff_coord(x1, y1)
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
                    self.screen.put_pixel(p, q, c)
                else:
                    self.screen.put_pixel(q, p, c)
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
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
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
        x0, y0 = self.screen.graph_view.coords(*self.get_window_physical(x, y, step))
        if c is None:
            c = -1
        else:
            error.range_check(0, 255, c)
        c = self.get_attr_index(c)
        if aspect is None:
            aspect = self.screen.mode.pixel_aspect[0] / float(self.screen.mode.pixel_aspect[1])
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
                self.screen.put_pixel(*_octant_coord(octant, x0, y0, x, y), index=c)
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
                self.screen.put_pixel(*_quadrant_coord(quadrant, cx, cy, x, y), index=c)
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
            self.screen.put_pixel(cx, cy+y, c)
            self.screen.put_pixel(cx, cy-y, c)
            y += 1
        # draw pie-slice lines
        if line0:
            self.draw_line(cx, cy, *_quadrant_coord(qua0, cx, cy, x0, y0), c=c)
        if line1:
            self.draw_line(cx, cy, *_quadrant_coord(qua1, cx, cy, x1, y1), c=c)

    ### PAINT: Flood fill

    def paint_(self, args):
        """PAINT: Fill an area defined by a border attribute with a tiled pattern."""
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        step = next(args)
        x, y = (values.to_single(next(args)).to_value() for _ in range(2))
        coord = x, y, step
        pattern = None
        cval = next(args)
        c, pattern = -1, None
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
                self.screen.mode.video_segment == 0xa000):
            raise error.RunError(error.IFC)
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
            tile = self.screen.mode.build_tile(bytearray(pattern)) if pattern else None
            back = self.screen.mode.build_tile(bytearray(background)) if background else None
        else:
            tile, back = [[c]*8], None
        bound_x0, bound_y0, bound_x1, bound_y1 = self.screen.graph_view.get()
        x, y = self.screen.graph_view.coords(*self.get_window_physical(*lcoord))
        line_seed = [(x, x, y, 0)]
        # paint nothing if seed is out of bounds
        if x < bound_x0 or x > bound_x1 or y < bound_y0 or y > bound_y1:
            return
        self.last_point = x, y
        # paint nothing if we start on border attrib
        if self.screen.get_pixel(x,y) == border:
            return
        while len(line_seed) > 0:
            # consider next interval
            x_start, x_stop, y, ydir = line_seed.pop()
            # extend interval as far as it goes to left and right
            x_left = x_start - len(self.screen.get_until(x_start-1, bound_x0-1, y, border))
            x_right = x_stop + len(self.screen.get_until(x_stop+1, bound_x1+1, y, border))
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
                self.screen.fill_interval(x_left, x_right, y, tile[0][0])
            else:
                interval = tile_to_interval(x_left, x_right, y, tile)
                self.screen.put_interval(self.screen.apagenum, x_left, y, interval)
            # allow interrupting the paint
            if y%4 == 0:
                self.input_methods.wait()
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
            pattern = self.screen.get_until(x, x_stop+1, y, border)
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
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        x0, y0 = (values.to_single(next(args)).to_value() for _ in range(2))
        array_name, operation_token = args
        array_name = self._memory.complete_name(array_name)
        operation_token = operation_token or tk.XOR
        if array_name not in self._memory.arrays:
            raise error.RunError(error.IFC)
        elif array_name[-1] == values.STR:
            raise error.RunError(error.TYPE_MISMATCH)
        x0, y0 = self.screen.graph_view.coords(*self.get_window_physical(x0, y0))
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
            dx, dy = self.screen.mode.record_to_sprite_size(byte_array)
            sprite = self.screen.mode.array_to_sprite(byte_array, 4, dx, dy)
            # store it now that we have it!
            self._memory.arrays.set_cache(array_name, (dx, dy, sprite))
        # sprite must be fully inside *viewport* boundary
        x1, y1 = x0+dx-1, y0+dy-1
        # Tandy screen 6 sprites are twice as wide as claimed
        if self.screen.mode.name == '640x200x4':
            x1 = x0 + 2*dx - 1
        # illegal fn call if outside viewport boundary
        vx0, vy0, vx1, vy1 = self.screen.graph_view.get()
        error.range_check(vx0, vx1, x0, x1)
        error.range_check(vy0, vy1, y0, y1)
        # apply the sprite to the screen
        self.screen.put_rect(x0, y0, x1, y1, sprite, operation_token)

    def get_(self, args):
        """GET: Read a sprite from the screen."""
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        x0, y0 = (values.to_single(next(args)).to_value() for _ in range(2))
        step = next(args)
        x, y = (values.to_single(next(args)).to_value() for _ in range(2))
        lcoord1 = x, y, step
        array_name, = args
        array_name = self._memory.complete_name(array_name)
        if array_name not in self._memory.arrays:
            raise error.RunError(error.IFC)
        elif array_name[-1] == values.STR:
            raise error.RunError(error.TYPE_MISMATCH)
        x0, y0 = self.screen.graph_view.coords(*self.get_window_physical(x0, y0))
        x1, y1 = self.screen.graph_view.coords(*self.get_window_physical(*lcoord1))
        self.last_point = x1, y1
        try:
            byte_array = self._memory.arrays.view_full_buffer(array_name)
        except KeyError:
            raise error.RunError(error.IFC)
        y0, y1 = sorted((y0, y1))
        x0, x1 = sorted((x0, x1))
        dx, dy = x1-x0+1, y1-y0+1
        # Tandy screen 6 simply GETs twice the width, it seems
        if self.screen.mode.name == '640x200x4':
            x1 = x0 + 2*dx - 1
        # illegal fn call if outside viewport boundary
        vx0, vy0, vx1, vy1 = self.screen.graph_view.get()
        error.range_check(vx0, vx1, x0, x1)
        error.range_check(vy0, vy1, y0, y1)
        # set size record
        byte_array[0:4] = self.screen.mode.sprite_size_to_record(dx, dy)
        # read from screen and convert to byte array
        sprite = self.screen.get_rect(x0, y0, x1, y1)
        try:
            self.screen.mode.sprite_to_array(sprite, dx, dy, byte_array, 4)
        except ValueError as e:
            raise error.RunError(error.IFC)
        # store a copy in the sprite store
        self._memory.arrays.set_cache(array_name, (dx, dy, sprite))

    ### DRAW statement

    def draw_(self, args):
        """DRAW: Execute a Graphics Macro Language string."""
        if self.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        gml = next(args)
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
                self.draw_(iter([sub]))
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
                    raise error.RunError(error.IFC)
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
                    raise error.RunError(error.IFC)
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
                    raise error.RunError(error.IFC)
                bound = gmls.parse_number()
                error.range_check(0, 9999, bound)
                x, y = self.get_window_logical(*self.last_point)
                self.flood_fill((x, y, False), colour, None, bound, None)
            else:
                raise error.RunError(error.IFC)
        list(args)

    def draw_step(self, x0, y0, sx, sy, plot, goback):
        """Make a DRAW step, drawing a line and returning if requested."""
        scale = self.draw_scale
        rotate = self.draw_angle
        aspect = self.screen.mode.pixel_aspect
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
            phi = rotate * deg_to_rad
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
            raise error.RunError(error.IFC)
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
