"""
PC-BASIC 3.23 - graphics.py
Graphics methods (frontend)

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import error
import fp
import vartypes
import state
import util
import backend

def get_colour_index(c):
    """ Get the index of the specified attribute. """
    if c == -1: # foreground; graphics 'background' attrib is always 0
        c = state.console_state.screen.attr & 0xf
    else:
        c = min(state.console_state.screen.mode.num_attr - 1, max(0, c))
    return c


class Drawing(object):
    """ Manage graphics drawing. """
    
    def __init__(self, screen):
        self.screen = screen
        self.unset_window()      
        self.unset_view()
        self.reset()  
    
    def reset(self):
        """ Reset graphics state. """
        if self.screen.mode.is_text_mode:
            return
        self.last_point = self.get_view_mid()
        self.last_attr = self.screen.mode.attr
        self.draw_scale = 4
        self.draw_angle = 0

    ## VIEW graphics viewport

    def set_view(self, x0, y0, x1, y1, absolute, fill, border):
        """ Set the graphics viewport and optionally draw a box (VIEW). """
        # first unset the viewport so that we can draw the box
        self.unset_view()
        if fill != None:
            self.draw_box_filled(x0, y0, x1, y1, fill)
            self.last_attr = fill
        if border != None:
            self.draw_box(x0-1, y0-1, x1+1, y1+1, border)
            self.last_attr = border
        # VIEW orders the coordinates
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        self.view_absolute = absolute
        self.view = x0, y0, x1, y1
        backend.video.set_graph_clip(x0, y0, x1, y1)
        self.reset_view()

    def unset_view(self):
        """ Unset the graphics viewport. """
        self.view_absolute = False
        self.view = None
        backend.video.unset_graph_clip()
        self.reset_view()

    def view_is_set(self):
        """ Return whether the graphics viewport is set. """
        return self.view != None
        
    def reset_view(self):
        """ Update graphics state after viewport reset. """
        self.last_point = self.get_view_mid()
        if self.window_bounds != None:
            self.set_window(*self.window_bounds)
    
    def get_view(self):
        """ Return the graphics viewport or full screen dimensions if not set. """
        if self.view:
            return self.view
        else:
            return 0, 0, self.screen.mode.pixel_width-1, self.screen.mode.pixel_height-1

    def get_view_mid(self):
        """ Get the midpoint of the current graphics view. """
        x0, y0, x1, y1 = self.get_view()
        return x0 + (x1-x0)/2, y0 + (y1-y0)/2

    def view_coords(self, x, y):
        """ Retrieve absolute coordinates for viewport coordinates. """
        if (not self.view) or self.view_absolute:
            return x, y
        else:
            return x + self.view[0], y + self.view[1]

    def clear_view(self):
        """ Clear the current graphics viewport. """
        if not self.screen.mode.is_text_mode:
            backend.video.clear_graph_clip((self.screen.attr>>4) & 0x7)

    ### WINDOW logical coords

    def set_window(self, fx0, fy0, fx1, fy1, cartesian=True):
        """ Set the logical coordinate window (WINDOW). """
        if fy0.gt(fy1):
            fy0, fy1 = fy1, fy0
        if fx0.gt(fx1):
            fx0, fx1 = fx1, fx0
        if cartesian:
            fy0, fy1 = fy1, fy0
        left, top, right, bottom = self.get_view()
        x0, y0 = fp.Single.zero, fp.Single.zero 
        x1, y1 = fp.Single.from_int(right-left), fp.Single.from_int(bottom-top)        
        scalex = fp.div(fp.sub(x1, x0), fp.sub(fx1,fx0))
        scaley = fp.div(fp.sub(y1, y0), fp.sub(fy1,fy0)) 
        offsetx = fp.sub(x0, fp.mul(fx0,scalex))
        offsety = fp.sub(y0, fp.mul(fy0,scaley))
        self.window = scalex, scaley, offsetx, offsety
        self.window_bounds = fx0, fy0, fx1, fy1, cartesian

    def unset_window(self):
        """ Unset the logical coordinate window. """
        self.window = None
        self.window_bounds = None

    def window_is_set(self):
        """ Return whether the logical coordinate window is set. """
        return self.window != None

    def get_window_physical(self, fx, fy, step=False):
        """ Convert logical to physical coordinates. """
        if self.window:
            scalex, scaley, offsetx, offsety = self.window
            if step:
                fx0, fy0 = self.get_window_logical(*self.last_point)
            else:
                fx0, fy0 = fp.Single.zero.copy(), fp.Single.zero.copy()
            x = fp.add(offsetx, fp.mul(fx0.iadd(fx), scalex)).round_to_int()
            y = fp.add(offsety, fp.mul(fy0.iadd(fy), scaley)).round_to_int()
        else:
            x, y = self.last_point if step else (0, 0)
            x += fx.round_to_int()
            y += fy.round_to_int()
        # overflow check
        if x < -0x8000 or y < -0x8000 or x > 0x7fff or y > 0x7fff:
            raise error.RunError(6)    
        return x, y

    def get_window_logical(self, x, y):
        """ Convert physical to logical coordinates. """
        x, y = fp.Single.from_int(x), fp.Single.from_int(y)
        if self.window:
            scalex, scaley, offsetx, offsety = self.window
            return (fp.div(fp.sub(x, offsetx), scalex), 
                     fp.div(fp.sub(y, offsety), scaley))
        else:
            return x, y

    def get_window_scale(self, fx, fy):
        """ Get logical to physical scale factor. """
        if self.window:
            scalex, scaley, _, _ = self.window
            return (fp.mul(fx, scalex).round_to_int(), 
                     fp.mul(fy, scaley).round_to_int())
        else:
            return fx.round_to_int(), fy.round_to_int()

    ### PSET, POINT

    def pset(self, lcoord, c):
        """ Draw a pixel in the given attribute (PSET, PRESET). """
        x, y = self.view_coords(*self.get_window_physical(*lcoord))
        c = get_colour_index(c)
        backend.video.apply_graph_clip()
        self.screen.put_pixel(x, y, c)
        backend.video.remove_graph_clip()
        self.last_attr = c
        self.last_point = x, y
    
    def point(self, lcoord):
        """ Return the attribute of a pixel (POINT). """
        x, y = self.view_coords(*self.get_window_physical(*lcoord))
        if x < 0 or x >= self.screen.mode.pixel_width:
            return -1
        if y < 0 or y >= self.screen.mode.pixel_height:
            return -1
        return self.screen.get_pixel(x,y)

    ### LINE
            
    def line(self, lcoord0, lcoord1, c, pattern, shape):
        """ Draw a patterned line or box (LINE). """
        if lcoord0:
            x0, y0 = self.view_coords(*self.get_window_physical(*lcoord0))
        else:
            x0, y0 = self.last_point
        x1, y1 = self.view_coords(*self.get_window_physical(*lcoord1))
        c = get_colour_index(c)
        if shape == '':
            self.draw_line(x0, y0, x1, y1, c, pattern)
        elif shape == 'B':
            self.draw_box(x0, y0, x1, y1, c, pattern)
        elif shape == 'BF':
            self.draw_box_filled(x0, y0, x1, y1, c)
        self.last_point = x1, y1
        self.last_attr = c
        
    def draw_line(self, x0, y0, x1, y1, c, pattern=0xffff):
        """ Draw a line between the given physical points. """
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
        backend.video.apply_graph_clip()
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
        backend.video.remove_graph_clip()
    
    def draw_box_filled(self, x0, y0, x1, y1, c):
        """ Draw a filled box between the given corner points. """
        x0, y0 = self.screen.mode.cutoff_coord(x0, y0)
        x1, y1 = self.screen.mode.cutoff_coord(x1, y1)
        if y1 < y0:
            y0, y1 = y1, y0
        if x1 < x0:
            x0, x1 = x1, x0    
        backend.video.apply_graph_clip()
        self.screen.fill_rect(x0, y0, x1, y1, c)
        backend.video.remove_graph_clip()
    
    def draw_box(self, x0, y0, x1, y1, c, pattern=0xffff):
        """ Draw an empty box between the given corner points. """
        x0, y0 = self.screen.mode.cutoff_coord(x0, y0)
        x1, y1 = self.screen.mode.cutoff_coord(x1, y1)
        mask = 0x8000
        backend.video.apply_graph_clip()
        mask = self.draw_straight(x1, y1, x0, y1, c, pattern, mask)
        mask = self.draw_straight(x1, y0, x0, y0, c, pattern, mask)
        # verticals always drawn top to bottom
        if y0 < y1:
            y0, y1 = y1, y0
        mask = self.draw_straight(x1, y1, x1, y0, c, pattern, mask)
        mask = self.draw_straight(x0, y1, x0, y0, c, pattern, mask)
        backend.video.remove_graph_clip()
        
    def draw_straight(self, x0, y0, x1, y1, c, pattern, mask):
        """ Draw a horizontal or vertical line. """
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

    def circle(self, lcoord, r, start, stop, c, aspect):
        """ Draw a circle, ellipse, arc or sector (CIRCLE). """
        x0, y0 = self.view_coords(*self.get_window_physical(*lcoord))
        c = get_colour_index(c)
        if aspect == None:
            aspect = fp.div(
                fp.Single.from_int(self.screen.mode.pixel_aspect[0]), 
                fp.Single.from_int(self.screen.mode.pixel_aspect[1]))
        if aspect.equals(aspect.one):
            rx, _ = self.get_window_scale(r, fp.Single.zero)
            ry = rx
        elif aspect.gt(aspect.one):
            _, ry = self.get_window_scale(fp.Single.zero, r)
            rx = fp.div(r, aspect).round_to_int()
        else:
            rx, _ = self.get_window_scale(r, fp.Single.zero)
            ry = fp.mul(r, aspect).round_to_int()
        start_octant, start_coord, start_line = -1, -1, False
        if start:
            start = fp.unpack(vartypes.pass_single_keep(start))
            start_octant, start_coord, start_line = get_octant(start, rx, ry)
        stop_octant, stop_coord, stop_line = -1, -1, False
        if stop:
            stop = fp.unpack(vartypes.pass_single_keep(stop))
            stop_octant, stop_coord, stop_line = get_octant(stop, rx, ry)
        if aspect.equals(aspect.one):
            self.draw_circle(x0, y0, rx, c, 
                             start_octant, start_coord, start_line, 
                             stop_octant, stop_coord, stop_line)
        else:
            startx, starty, stopx, stopy = -1, -1, -1, -1
            if start != None:
                startx = abs(fp.mul(fp.Single.from_int(rx), fp.cos(start)).round_to_int())
                starty = abs(fp.mul(fp.Single.from_int(ry), fp.sin(start)).round_to_int())
            if stop != None:
                stopx = abs(fp.mul(fp.Single.from_int(rx), fp.cos(stop)).round_to_int())
                stopy = abs(fp.mul(fp.Single.from_int(ry), fp.sin(stop)).round_to_int())
            self.draw_ellipse(x0, y0, rx, ry, c, 
                              start_octant/2, startx, starty, start_line, 
                              stop_octant/2, stopx, stopy, stop_line)
        self.last_attr = c
        self.last_point = x0, y0

    def draw_circle(self, x0, y0, r, c, 
                    oct0=-1, coo0=-1, line0=False, 
                    oct1=-1, coo1=-1, line1=False):
        """ Draw a circle sector using the midpoint algorithm. """
        # see e.g. http://en.wikipedia.org/wiki/Midpoint_circle_algorithm
        # find invisible octants
        if oct0 == -1:
            hide_oct = range(0,0)
        elif oct0 < oct1 or oct0 == oct1 and octant_gte(oct0, coo1, coo0):
            hide_oct = range(0, oct0) + range(oct1+1, 8)
        else:
            hide_oct = range(oct1+1, oct0)
        # if oct1==oct0: 
        # ----|.....|--- : coo1 lt coo0 : print if y in [0,coo1] or in [coo0, r]  
        # ....|-----|... ; coo1 gte coo0: print if y in [coo0,coo1]
        backend.video.apply_graph_clip()
        x, y = r, 0
        bres_error = 1-r 
        while x >= y:
            for octant in range(0,8):
                if octant in hide_oct:
                    continue
                elif oct0 != oct1 and octant == oct0 and octant_gt(oct0, coo0, y):
                    continue
                elif oct0 != oct1 and octant == oct1 and octant_gt(oct1, y, coo1):
                    continue
                elif oct0 == oct1 and octant == oct0:
                    # if coo1 >= coo0
                    if octant_gte(oct0, coo1, coo0):
                        # if y > coo1 or y < coo0 
                        # (don't draw if y is outside coo's)
                        if octant_gt(oct0, y, coo1) or octant_gt(oct0, coo0,y):
                            continue
                    else:
                        # if coo0 > y > c001 
                        # (don't draw if y is between coo's)
                        if octant_gt(oct0, y, coo1) and octant_gt(oct0, coo0, y):
                            continue
                self.screen.put_pixel(*octant_coord(octant, x0, y0, x, y), index=c) 
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
            self.draw_line(x0, y0, *octant_coord(oct0, x0, y0, coo0x, coo0), c=c)
        if line1:
            self.draw_line(x0, y0, *octant_coord(oct1, x0, y0, coo1x, coo1), c=c)
        backend.video.remove_graph_clip()
            
    def draw_ellipse(self, cx, cy, rx, ry, c, 
                     qua0=-1, x0=-1, y0=-1, line0=False, 
                     qua1=-1, x1=-1, y1=-1, line1=False):
        """ Draw ellipse using the midpoint algorithm. """
        # for algorithm see http://members.chello.at/~easyfilter/bresenham.html
        # find invisible quadrants
        if qua0 == -1:
            hide_qua = range(0,0)
        elif qua0 < qua1 or qua0 == qua1 and quadrant_gte(qua0, x1, y1, x0, y0):
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
        backend.video.apply_graph_clip()        
        x, y = rx, 0
        while True: 
            for quadrant in range(0,4):
                # skip invisible arc sectors
                if quadrant in hide_qua:
                    continue
                elif qua0 != qua1 and quadrant == qua0 and quadrant_gt(qua0, x0, y0, x, y):
                    continue
                elif qua0 != qua1 and quadrant == qua1 and quadrant_gt(qua1, x, y, x1, y1):
                    continue
                elif qua0 == qua1 and quadrant == qua0:
                    if quadrant_gte(qua0, x1, y1, x0, y0):
                        if quadrant_gt(qua0, x, y, x1, y1) or quadrant_gt(qua0, x0, y0, x, y):
                            continue
                    else:
                        if quadrant_gt(qua0, x, y, x1, y1) and quadrant_gt(qua0, x0, y0, x, y):
                            continue
                self.screen.put_pixel(*quadrant_coord(quadrant, cx, cy, x, y), index=c) 
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
            self.draw_line(cx, cy, *quadrant_coord(qua0, cx, cy, x0, y0), c=c)
        if line1:
            self.draw_line(cx, cy, *quadrant_coord(qua1, cx, cy, x1, y1), c=c)
        backend.video.remove_graph_clip()     


    ### PAINT: Flood fill

    def paint(self, lcoord, pattern, c, border, background): 
        """ Fill an area defined by a border attribute with a tiled pattern. """
        # 4-way scanline flood fill: http://en.wikipedia.org/wiki/Flood_fill
        # flood fill stops on border colour in all directions; it also stops on scanlines in fill_colour
        # pattern tiling stops at intervals that equal the pattern to be drawn, unless this pattern is
        # also equal to the background pattern.
        c, border = get_colour_index(c), get_colour_index(border)
        solid = (pattern == None)
        if not solid:    
            tile = self.screen.mode.build_tile(pattern) if pattern else None 
            back = self.screen.mode.build_tile(background) if background else None
        else:
            tile, back = [[c]*8], None
        bound_x0, bound_y0, bound_x1, bound_y1 = backend.video.get_graph_clip()  
        x, y = self.view_coords(*self.get_window_physical(*lcoord))
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
            x_left = x_start - len(backend.video.get_until(x_start-1, bound_x0-1, y, border))    
            x_right = x_stop + len(backend.video.get_until(x_stop+1, bound_x1+1, y, border)) 
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
            self.screen.fill_interval(x_left, x_right, y, tile, solid)
            # show progress
            if y%4 == 0:
                backend.check_events()
        self.last_attr = c
        
    def check_scanline(self, line_seed, x_start, x_stop, y, 
                       c, tile, back, border, ydir):
        """ Append all subintervals between border colours to the scanning stack. """
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
            pattern = backend.video.get_until(x, x_stop+1, y, border)
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


###############################################################################
# octant logic for CIRCLE
        
def get_octant(mbf, rx, ry):
    """ Get the circle octant for a given coordinate. """
    neg = mbf.neg 
    if neg:
        mbf.negate()
    octant = 0
    comp = fp.Single.pi4.copy()
    while mbf.gt(comp):
        comp.iadd(fp.Single.pi4)
        octant += 1
        if octant >= 8:
            raise error.RunError(5) # ill fn call
    if octant in (0, 3, 4, 7):
        # running var is y
        coord = abs(fp.mul(fp.Single.from_int(ry), fp.sin(mbf)).round_to_int())
    else:
        # running var is x    
        coord = abs(fp.mul(fp.Single.from_int(rx), fp.cos(mbf)).round_to_int())
    return octant, coord, neg          

def octant_coord(octant, x0, y0, x, y):    
    """ Return symmetrically reflected coordinates for a given pair. """
    if   octant == 7:     return x0+x, y0+y
    elif octant == 0:     return x0+x, y0-y
    elif octant == 4:     return x0-x, y0+y
    elif octant == 3:     return x0-x, y0-y
    elif octant == 6:     return x0+y, y0+x
    elif octant == 1:     return x0+y, y0-x
    elif octant == 5:     return x0-y, y0+x
    elif octant == 2:     return x0-y, y0-x
    
def octant_gt(octant, y, coord):
    """ Return whether y is further along the circle than coord. """
    if octant%2 == 1: 
        return y < coord 
    else: 
        return y > coord

def octant_gte(octant, y, coord):
    """ Return whether y is further along the circle than coord, or equal. """
    if octant%2 == 1: 
        return y <= coord 
    else: 
        return y >= coord


###############################################################################
# quadrant logic for CIRCLE

def quadrant_coord(quadrant, x0,y0, x,y):    
    """ Return symmetrically reflected coordinates for a given pair. """
    if   quadrant == 3:     return x0+x, y0+y
    elif quadrant == 0:     return x0+x, y0-y
    elif quadrant == 2:     return x0-x, y0+y
    elif quadrant == 1:     return x0-x, y0-y
    
def quadrant_gt(quadrant, x, y, x0, y0):
    """ Return whether y is further along the ellipse than coord. """
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
        
def quadrant_gte(quadrant, x, y, x0, y0):
    """ Return whether y is further along the ellipse than coord, or equal. """
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

        
###############################################################################
# Sprtie operations (PUT and GET)

def operation_set(pix0, pix1):  
    """ PUT transformation: PSET """
    return pix1

def operation_not(pix0, pix1):
    """ PUT transformation: PRESET """
    return pix1 ^ ((1<<state.console_state.screen.mode.bitsperpixel)-1)

def operation_and(pix0, pix1):
    """ PUT transformation: AND """
    return pix0 & pix1

def operation_or(pix0, pix1):
    """ PUT transformation: OR """
    return pix0 | pix1

def operation_xor(pix0, pix1):
    """ PUT transformation: XOR """
    return pix0 ^ pix1

# code tokens for these operations
operations = {
    '\xC6': operation_set, # PSET
    '\xC7': operation_not, # PRESET
    '\xEE': operation_and,
    '\xEF': operation_or,
    '\xF0': operation_xor,
    }
     
def set_area(x0, y0, array, operation_char):
    """ Put a sprite on the screen (PUT). """
    # array must exist at this point (or PUT would have raised error 5)      
    x0, y0 = state.console_state.screen.drawing.view_coords(x0, y0)
    rect = backend.video.fast_put(x0, y0, array, state.basic_state.arrays[array][2], operation_char)
    if rect:
        x0, y0, x1, y1 = rect
    else:
        try:
            _, byte_array, _ = state.basic_state.arrays[array]
        except KeyError:
            byte_array = bytearray()
        operation = operations[operation_char]
        x0, y0, x1, y1 = state.console_state.screen.mode.set_area(x0, y0, byte_array, operation)
    state.console_state.screen.clear_text_area(x0, y0, x1, y1)
        
def get_area(x0, y0, x1, y1, array):
    """ Read a sprite from the screen (GET). """
    try:
        _, byte_array, _ = state.basic_state.arrays[array]
    except KeyError:
        raise error.RunError(5)    
    if state.console_state.screen.mode.name == '640x200x4':
        # Tandy screen 6 simply GETs twice the width, it seems
        x1 = x0 + 2*(x1-x0+1)-1 
    x0, y0 = state.console_state.screen.drawing.view_coords(x0, y0)
    x1, y1 = state.console_state.screen.drawing.view_coords(x1, y1)
    state.console_state.screen.mode.get_area(x0, y0, x1, y1, byte_array)
    # store a copy in the fast-put store
    # arrays[array] must exist at this point (or GET would have raised error 5)
    backend.video.fast_get(x0, y0, x1, y1, array, state.basic_state.arrays[array][2])
    

