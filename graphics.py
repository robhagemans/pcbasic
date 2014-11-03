#
# PC-BASIC 3.23 - graphics.py
#
# Graphics methods (frontend)
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import error
import fp
import vartypes
import state
import util
import backend

# real state variables
state.console_state.graph_window = None
state.console_state.graph_window_bounds = None
state.console_state.last_point = (0, 0)    
state.console_state.last_attr = state.console_state.attr

def require_graphics_mode(err=5):
    if not is_graphics_mode():
        raise error.RunError(err)

def is_graphics_mode():
    return backend.video and not state.console_state.current_mode.is_text_mode

# reset graphics state    
def reset_graphics():
    if not is_graphics_mode():
        return
    x0, y0, x1, y1 = backend.video.get_graph_clip()
    if state.console_state.view_graph_absolute:
        state.console_state.last_point = x0 + (x1-x0)/2, y0 + (y1-y0)/2
    else:
        state.console_state.last_point = (x1-x0)/2, (y1-y0)/2
    state.basic_state.draw_scale = 4
    state.basic_state.draw_angle = 0

def get_colour_index(c):
    if c == -1: # foreground; graphics 'background' attrib is always 0
        c = state.console_state.attr & 0xf
    else:
        c = min(state.console_state.num_attr - 1, max(0, c))
    return c

def check_coords(x, y):
    return min(state.console_state.size[0], max(-1, x)), min(state.console_state.size[1], max(-1, y))
    
### PSET, POINT

def put_point(x, y, c):
    x, y = backend.view_coords(x,y)
    backend.video.apply_graph_clip()
    c = get_colour_index(c)
    backend.video.put_pixel(x, y, c)
    backend.video.remove_graph_clip()
    state.console_state.last_attr = c
    
def get_point(x, y):
    x, y = backend.view_coords(x, y)
    if x < 0 or x >= state.console_state.size[0]:
        return -1
    if y < 0 or y >= state.console_state.size[1]:
        return -1
    return backend.video.get_pixel(x,y)

### WINDOW coords

def set_graph_window(fx0, fy0, fx1, fy1, cartesian=True):
    if fy0.gt(fy1):
        fy0, fy1 = fy1, fy0
    if fx0.gt(fx1):
        fx0, fx1 = fx1, fx0
    if cartesian:
        fy0, fy1 = fy1, fy0
    left,top, right,bottom = backend.video.get_graph_clip()
    x0, y0 = fp.Single.zero, fp.Single.zero 
    x1, y1 = fp.Single.from_int(right-left), fp.Single.from_int(bottom-top)        
    scalex, scaley = fp.div(fp.sub(x1, x0), fp.sub(fx1,fx0)), fp.div(fp.sub(y1, y0), fp.sub(fy1,fy0)) 
    offsetx, offsety = fp.sub(x0, fp.mul(fx0,scalex)), fp.sub(y0, fp.mul(fy0,scaley))
    state.console_state.graph_window = scalex, scaley, offsetx, offsety
    state.console_state.graph_window_bounds = fx0, fy0, fx1, fy1, cartesian

def unset_graph_window():
    state.console_state.graph_window = None
    state.console_state.graph_window_bounds = None

# input logical coords, output physical coords
def window_coords(fx, fy, step=False):
    if state.console_state.graph_window:
        scalex, scaley, offsetx, offsety = state.console_state.graph_window
        fx0, fy0 = get_window_coords(*state.console_state.last_point) if step else (fp.Single.zero.copy(), fp.Single.zero.copy())    
        x = fp.add(offsetx, fp.mul(fx0.iadd(fx), scalex)).round_to_int()
        y = fp.add(offsety, fp.mul(fy0.iadd(fy), scaley)).round_to_int()
    else:
        x, y = state.console_state.last_point if step else (0, 0)
        x += fx.round_to_int()
        y += fy.round_to_int()
    # overflow check
    if x < -0x8000 or y < -0x8000 or x > 0x7fff or y > 0x7fff:
        raise error.RunError(6)    
    return x, y

# inverse function
# input physical coords, output logical coords
def get_window_coords(x, y):
    x, y = fp.Single.from_int(x), fp.Single.from_int(y)
    if state.console_state.graph_window:
        scalex, scaley, offsetx, offsety = state.console_state.graph_window
        return fp.div(fp.sub(x, offsetx), scalex), fp.div(fp.sub(y, offsety), scaley)
    else:
        return x, y

def window_scale(fx, fy):
    if state.console_state.graph_window:
        scalex, scaley, _, _ = state.console_state.graph_window
        return fp.mul(fx, scalex).round_to_int(), fp.mul(fy, scaley).round_to_int()
    else:
        return fx.round_to_int(), fy.round_to_int()

### LINE
            
def draw_box_filled(x0, y0, x1, y1, c):
    x0, y0 = backend.view_coords(x0, y0)
    x1, y1 = backend.view_coords(x1, y1)
    c = get_colour_index(c)
    if y1 < y0:
        y0, y1 = y1, y0
    if x1 < x0:
        x0, x1 = x1, x0    
    backend.video.apply_graph_clip()
    backend.video.fill_rect(x0, y0, x1, y1, c)
    backend.video.remove_graph_clip()
    state.console_state.last_attr = c
    
def draw_line(x0, y0, x1, y1, c, pattern=0xffff):
    c = get_colour_index(c)
    x0, y0 = check_coords(*backend.view_coords(x0, y0))
    x1, y1 = check_coords(*backend.view_coords(x1, y1))
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
        if pattern&mask != 0:
            if steep:
                backend.video.put_pixel(y, x, c)
            else:
                backend.video.put_pixel(x, y, c)
        mask >>= 1
        if mask == 0:
            mask = 0x8000
        line_error -= dy
        if line_error < 0:
            y += sy
            line_error += dx    
    backend.video.remove_graph_clip()
    state.console_state.last_attr = c
    
def draw_straight(x0, y0, x1, y1, c, pattern, mask):
    if x0 == x1:
        p0, p1, q, direction = y0, y1, x0, 'y' 
    else:
        p0, p1, q, direction = x0, x1, y0, 'x'
    sp = 1 if p1 > p0 else -1
    for p in range (p0, p1+sp, sp):
        if pattern & mask != 0:
            if direction == 'x':
                backend.video.put_pixel(p, q, c)
            else:
                backend.video.put_pixel(q, p, c)
        mask >>= 1
        if mask == 0:
            mask = 0x8000
    return mask
                        
def draw_box(x0, y0, x1, y1, c, pattern=0xffff):
    x0, y0 = check_coords(*backend.view_coords(x0, y0))
    x1, y1 = check_coords(*backend.view_coords(x1, y1))
    c = get_colour_index(c)
    mask = 0x8000
    backend.video.apply_graph_clip()
    mask = draw_straight(x1, y1, x0, y1, c, pattern, mask)
    mask = draw_straight(x1, y0, x0, y0, c, pattern, mask)
    # verticals always drawn top to bottom
    if y0 < y1:
        y0, y1 = y1, y0
    mask = draw_straight(x1, y1, x1, y0, c, pattern, mask)
    mask = draw_straight(x0, y1, x0, y0, c, pattern, mask)
    backend.video.remove_graph_clip()
    state.console_state.last_attr = c
    
### circle, ellipse, sectors

def draw_circle_or_ellipse(x0, y0, r, start, stop, c, aspect):
    if aspect.equals(aspect.one):
        rx, dummy = window_scale(r,fp.Single.zero)
        ry = rx
    else:
        if aspect.gt(aspect.one):
            dummy, ry = window_scale(fp.Single.zero,r)
            rx = fp.div(r, aspect).round_to_int()
        else:
            rx, dummy = window_scale(r,fp.Single.zero)
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
        draw_circle(x0, y0, rx, c, start_octant, start_coord, start_line, stop_octant, stop_coord, stop_line)
    else:
        startx, starty, stopx, stopy = -1, -1, -1, -1
        if start != None:
            startx = abs(fp.mul(fp.Single.from_int(rx), fp.cos(start)).round_to_int())
            starty = abs(fp.mul(fp.Single.from_int(ry), fp.sin(start)).round_to_int())
        if stop != None:
            stopx = abs(fp.mul(fp.Single.from_int(rx), fp.cos(stop)).round_to_int())
            stopy = abs(fp.mul(fp.Single.from_int(ry), fp.sin(stop)).round_to_int())
        draw_ellipse(x0, y0, rx, ry, c, start_octant/2, startx, starty, start_line, stop_octant/2, stopx, stopy, stop_line)

def get_octant(mbf, rx, ry):
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

# see e.g. http://en.wikipedia.org/wiki/Midpoint_circle_algorithm
def draw_circle(x0, y0, r, c, oct0=-1, coo0=-1, line0=False, oct1=-1, coo1=-1, line1=False):
    c = get_colour_index(c)
    x0, y0 = backend.view_coords(x0, y0)
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
            elif oct0 != oct1 and (octant == oct0 and octant_gt(oct0, coo0, y)):
                continue
            elif oct0 != oct1 and (octant == oct1 and octant_gt(oct1, y, coo1)):
                continue
            elif oct0 == oct1 and octant == oct0:
                # if coo1 >= coo0
                if octant_gte(oct0, coo1, coo0):
                    # if y > coo1 or y < coo0 (don't draw if y is outside coo's)
                    if octant_gt(oct0, y, coo1) or octant_gt(oct0, coo0,y):
                        continue
                else:
                    # if coo0 > y > c001 (don't draw if y is between coo's)
                    if octant_gt(oct0, y, coo1) and octant_gt(oct0, coo0, y):
                        continue
            backend.video.put_pixel(*octant_coord(octant, x0, y0, x, y), index=c) 
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
    if line0:
        draw_line(x0,y0, *octant_coord(oct0, x0, y0, coo0x, coo0), c=c)
    if line1:
        draw_line(x0,y0, *octant_coord(oct1, x0, y0, coo1x, coo1), c=c)
    backend.video.remove_graph_clip()
    state.console_state.last_attr = c
    
def octant_coord(octant, x0,y0, x,y):    
    if   octant == 7:     return x0+x, y0+y
    elif octant == 0:     return x0+x, y0-y
    elif octant == 4:     return x0-x, y0+y
    elif octant == 3:     return x0-x, y0-y
    elif octant == 6:     return x0+y, y0+x
    elif octant == 1:     return x0+y, y0-x
    elif octant == 5:     return x0-y, y0+x
    elif octant == 2:     return x0-y, y0-x
    
def octant_gt(octant, y, coord):
    if octant%2 == 1: 
        return y < coord 
    else: 
        return y > coord

def octant_gte(octant, y, coord):
    if octant%2 == 1: 
        return y <= coord 
    else: 
        return y >= coord
    
# notes on midpoint algo implementation:
#    
# x*x + y*y == r*r
# look at y'=y+1
# err(y) = y*y+x*x-r*r
# err(y') = y*y + 2y+1 + x'*x' - r*r == err(y) + x'*x' -x*x + 2y+1 
# if x the same:
#   err(y') == err(y) +2y+1
# if x -> x-1:
#   err(y') == err(y) +2y+1 -2x+1 == err(y) +2(y-x+1)

# why initialise error with 1-x == 1-r?
# we change x if the radius is more than 0.5pix out so err(y, r+0.5) == y*y + x*x - (r*r+r+0.25) == err(y,r) - r - 0.25 >0
# with err and r both integers, this just means err - r > 0 <==> err - r +1 >= 0
# above, error == err(y) -r + 1 and we change x if it's >=0.



# ellipse: 
# ry^2*x^2 + rx^2*y^2 == rx^2*ry^2
# look at y'=y+1 (quadrant between points of 45deg slope)
# err == ry^2*x^2 + rx^2*y^2 - rx^2*ry^2
# err(y') == rx^2*(y^2+2y+1) + ry^2(x'^2)- rx^2*ry^2 == err(y) + ry^2(x'^2-x^2) + rx^2*(2y+1)
# if x the same:
#   err(y') == err(y) + rx^2*(2y+1)
# if x' -> x-1:
#   err(y') == err(y) + rx^2*(2y+1) +rx^2(-2x+1)

# change x if radius more than 0.5pix out: err(y, rx+0.5, ry) == ry^2*y*y+rx^2*x*x - (ry*ry)*(rx*rx+rx+0.25) > 0
#  ==> err(y) - (rx+0.25)*(ry*ry) >0
#  ==> err(y) - (rx*ry*ry + 0.25*ry*ry ) > 0 

# break yinc loop if one step no longer suffices


    
# ellipse using midpoint algorithm
# for algorithm see http://members.chello.at/~easyfilter/bresenham.html
def draw_ellipse(cx, cy, rx, ry, c, qua0=-1, x0=-1, y0=-1, line0=False, qua1=-1, x1=-1, y1=-1, line1=False):
    c = get_colour_index(c)
    cx, cy = backend.view_coords(cx, cy)
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
            elif qua0 != qua1 and (quadrant == qua0 and quadrant_gt(qua0, x0, y0, x, y)):
                continue
            elif qua0 != qua1 and (quadrant == qua1 and quadrant_gt(qua1, x, y, x1, y1)):
                continue
            elif qua0 == qua1 and quadrant == qua0:
                if quadrant_gte(qua0, x1,y1, x0,y0):
                    if quadrant_gt(qua0, x, y, x1, y1) or quadrant_gt(qua0, x0, y0, x, y):
                        continue
                else:
                    if quadrant_gt(qua0, x, y, x1, y1) and quadrant_gt(qua0, x0, y0, x, y):
                        continue
            backend.video.put_pixel(*quadrant_coord(quadrant, cx,cy,x,y), index=c) 
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
        backend.video.put_pixel(cx, cy+y, c) 
        backend.video.put_pixel(cx, cy-y, c) 
        y += 1 
    if line0:
        draw_line(cx,cy, *quadrant_coord(qua0, cx, cy, x0, y0), c=c)
    if line1:
        draw_line(cx,cy, *quadrant_coord(qua1, cx, cy, x1, y1), c=c)
    backend.video.remove_graph_clip()     
    state.console_state.last_attr = c
    
def quadrant_coord(quadrant, x0,y0, x,y):    
    if   quadrant == 3:     return x0+x, y0+y
    elif quadrant == 0:     return x0+x, y0-y
    elif quadrant == 2:     return x0-x, y0+y
    elif quadrant == 1:     return x0-x, y0-y
    
def quadrant_gt(quadrant, x, y, x0, y0):
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
        
#####        
# 4-way scanline flood fill
# http://en.wikipedia.org/wiki/Flood_fill

# flood fill stops on border colour in all directions; it also stops on scanlines in fill_colour
# pattern tiling stops at intervals that equal the pattern to be drawn, unless this pattern is
# also equal to the background pattern.
def flood_fill (x, y, pattern, c, border, background): 
    c, border = get_colour_index(c), get_colour_index(border)
    if get_point(x, y) == border:
        return
    if pattern:    
        tile = build_tile(pattern) 
        back = build_tile(background) 
        solid = False
    else:
        tile, back = [[c]*8], None
        solid = True    
    bound_x0, bound_y0, bound_x1, bound_y1 = backend.video.get_graph_clip()  
    x, y = backend.view_coords(x, y)
    line_seed = [(x, x, y, 0)]
    # paint nothing if seed is out of bounds
    if x < bound_x0 or x > bound_x1 or y < bound_y0 or y > bound_y1:
        return
    while len(line_seed) > 0:
        # consider next interval
        x_start, x_stop, y, ydir = line_seed.pop()
        # extend interval as far as it goes to left and right
        # check left extension
        x_left = x_start
        while x_left-1 >= bound_x0 and backend.video.get_pixel(x_left-1,y) != border:
            x_left -= 1
        # check right extension
        x_right = x_stop
        while x_right+1 <= bound_x1 and backend.video.get_pixel(x_right+1,y) != border:
            x_right += 1
        # check next scanlines and add intervals to the list
        if ydir == 0:
            if y + 1 <= bound_y1:
                line_seed = check_scanline(line_seed, x_left, x_right, y+1, c, tile, back, border, 1)
            if y - 1 >= bound_y0:
                line_seed = check_scanline(line_seed, x_left, x_right, y-1, c, tile, back, border, -1)
        else:
            # check the same interval one scanline onward in the same direction
            if y+ydir <= bound_y1 and y+ydir >= bound_y0:
                line_seed = check_scanline(line_seed, x_left, x_right, y+ydir, c, tile, back, border, ydir)
            # check any bit of the interval that was extended one scanline backward 
            # this is where the flood fill goes around corners.
            if y-ydir <= bound_y1 and y-ydir >= bound_y0:
                line_seed = check_scanline(line_seed, x_left, x_start-1, y-ydir, c, tile, back, border, -ydir)
                line_seed = check_scanline(line_seed, x_stop+1, x_right, y-ydir, c, tile, back, border, -ydir)
        # draw the pixels for the current interval   
        backend.video.fill_interval(x_left, x_right, y, tile, solid)
        # show progress
        if y%4==0:
            backend.check_events()
    state.console_state.last_attr = c
    
# look at a scanline for a given interval; add all subintervals between border colours to the pile
def check_scanline(line_seed, x_start, x_stop, y, c, tile, back, border, ydir):
    if x_stop < x_start:
        return line_seed
    x_start_next = x_start
    x_stop_next = x_start_next-1
    rtile = tile[y%len(tile)]
    if back:
        rback = back[y%len(back)]
    # never match zero pattern (special case)
    has_same_pattern = (rtile != [0]*8)
    for x in range(x_start, x_stop+1):
        # scan horizontally until border colour found, then append interval & continue scanning
        xy_colour = backend.video.get_pixel(x, y)
        if xy_colour != border:
            x_stop_next = x
            has_same_pattern &= (xy_colour == rtile[x%8] and (not back or xy_colour != rback[x%8]))
        else:
            # we've reached a border colour, append our interval & start a new one
            # don't append if same fill colour/pattern, to avoid infinite loops over bits already painted (eg. 00 shape)
            if x_stop_next >= x_start_next and not has_same_pattern:
                line_seed.append([x_start_next, x_stop_next, y, ydir])
            x_start_next = x + 1
            has_same_pattern = (rtile != [0]*8)
    if x_stop_next >= x_start_next and not has_same_pattern:
        line_seed.append([x_start_next, x_stop_next, y, ydir])
    return line_seed    

def build_tile(pattern):
    """ Build a flood-fill tile of width 8 pixels and the necessary height. """
    if not pattern:
        return None
    return state.console_state.current_mode.build_tile(pattern)

### PUT and GET

def operation_set(pix0, pix1):
    return pix1

def operation_not(pix0, pix1):
#    return ~pix1
    return pix1 ^ ((1<<state.console_state.current_mode.bitsperpixel)-1)

def operation_and(pix0, pix1):
    return pix0 & pix1

def operation_or(pix0, pix1):
    return pix0 | pix1

def operation_xor(pix0, pix1):
    return pix0 ^ pix1

operations = {
    '\xC6': operation_set, #PSET
    '\xC7': operation_not, #PRESET
    '\xEE': operation_and,
    '\xEF': operation_or,
    '\xF0': operation_xor,
    }
     
def set_area(x0, y0, array, operation_char):
    # array must exist at this point (or PUT would have raised error 5)       
    if backend.video.fast_put(x0, y0, array, state.basic_state.arrays[array][2], operation_char):
        return
    try:
        _, byte_array, _ = state.basic_state.arrays[array]
    except KeyError:
        byte_array = bytearray()
    operation = operations[operation_char]
    state.console_state.current_mode.set_area(x0, y0, byte_array, operation)
        
def get_area(x0, y0, x1, y1, array):
    try:
        _, byte_array, _ = state.basic_state.arrays[array]
    except KeyError:
        raise error.RunError(5)    
    if state.console_state.current_mode.name == '640x200x4':
        # Tandy screen 6 simply GETs twice the width, it seems
        x1 = x0 + 2*(x1-x0+1)-1 
    state.console_state.current_mode.get_area(x0, y0, x1, y1, byte_array)
    # store a copy in the fast-put store
    # arrays[array] must exist at this point (or GET would have raised error 5)
    backend.video.fast_get(x0, y0, x1, y1, array, state.basic_state.arrays[array][2])
    

