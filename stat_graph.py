#
# PC-BASIC 3.23 - stat_graph.py
#
# Graphics statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import error
import vartypes
import var
import util
import expressions
import fp
import graphics
import draw_and_play


def parse_coord(ins, absolute=False):
    step = not absolute and util.skip_white_read_if(ins, ('\xCF',)) # STEP
    util.require_read(ins, ('(',))
    x = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require_read(ins, (',',))
    y = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require_read(ins, (')',))
    if absolute:
        return x, y
    graphics.last_point = graphics.window_coords(x, y, step)
    return graphics.last_point

def exec_pset(ins, c=-1):
    graphics.require_graphics_mode()
    x, y = parse_coord(ins)
    graphics.last_point = x, y
    if util.skip_white_read_if(ins, (',',)):
        c = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(-1, 255, c)
    util.require(ins, util.end_statement)    
    graphics.put_point(x, y, c)

def exec_preset(ins):
    exec_pset(ins, 0)   

def exec_line_graph(ins):
    graphics.require_graphics_mode()
    if util.skip_white(ins) in ('(', '\xCF'):
        x0, y0 = parse_coord(ins)
        graphics.last_point = x0, y0
    else:
        x0, y0 = graphics.last_point
    util.require_read(ins, ('\xEA',)) # -
    x1, y1 = parse_coord(ins)
    graphics.last_point = x1, y1
    c, mode, mask = -1, '', 0xffff
    if util.skip_white_read_if(ins, (',',)):
        expr = expressions.parse_expression(ins, allow_empty=True)
        if expr:
            c = vartypes.pass_int_unpack(expr)
        if util.skip_white_read_if(ins, (',',)):
            if util.skip_white_read_if(ins, ('B',)):
                mode = 'BF' if util.skip_white_read_if(ins, ('F',)) else 'B'
            else:
                util.require(ins, (',',))
            if util.skip_white_read_if(ins, (',',)):
                mask = vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=22), maxint=0x7fff)
        elif not expr:
            raise error.RunError(22)        
    util.require(ins, util.end_statement)    
    if mode == '':
        graphics.draw_line(x0, y0, x1, y1, c, mask)
    elif mode == 'B':
        graphics.draw_box(x0, y0, x1, y1, c, mask)
    elif mode == 'BF':
        graphics.draw_box_filled(x0, y0, x1, y1, c)
            
def exec_view_graph(ins):
    graphics.require_graphics_mode()
    absolute = util.skip_white_read_if(ins, ('\xC8',)) #SCREEN
    if util.skip_white(ins) == '(':
        x0, y0 = parse_coord(ins, absolute=True)
        util.require_read(ins, ('\xEA',)) #-
        x1, y1 = parse_coord(ins, absolute=True)
        # not scaled by WINDOW
        x0, x1, y0, y1 = x0.round_to_int(), x1.round_to_int(), y0.round_to_int(), y1.round_to_int()
        fill, border = None, None
        if util.skip_white_read_if(ins, (',',)):
            fill, border = expressions.parse_int_list(ins, 2, err=2)
        if fill != None:
            graphics.draw_box_filled(x0, y0, x1, y1, fill)
        if border != None:
            graphics.draw_box(x0-1, y0-1, x1+1, y1+1, border)
        graphics.set_graph_view(x0, y0, x1, y1, absolute)
    else:
        graphics.unset_graph_view()
    util.require(ins, util.end_statement)        
    
def exec_window(ins):
    graphics.require_graphics_mode()
    cartesian = not util.skip_white_read_if(ins, ('\xC8',)) #SCREEN
    if util.skip_white(ins) == '(':
        x0, y0 = parse_coord(ins, absolute=True)
        util.require_read(ins, ('\xEA',)) #-
        x1, y1 = parse_coord(ins, absolute=True)
        graphics.set_graph_window(x0,y0, x1,y1, cartesian)
    else:
        graphics.unset_graph_window()
    util.require(ins, util.end_statement)        
        
def exec_circle(ins):
    graphics.require_graphics_mode()
    x0, y0 = parse_coord(ins)
    graphics.last_point = x0, y0
    util.require_read(ins, (',',))
    r = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    start, stop, c = None, None, -1
    aspect = graphics.pixel_aspect_ratio
    if util.skip_white_read_if(ins, (',',)):
        cval = expressions.parse_expression(ins, allow_empty=True)
        if cval:
            c = vartypes.pass_int_unpack(cval)
        if util.skip_white_read_if(ins, (',',)):
            start = expressions.parse_expression(ins, allow_empty=True)
            if util.skip_white_read_if(ins, (',',)):
                stop = expressions.parse_expression(ins, allow_empty=True)
                if util.skip_white_read_if(ins, (',',)):
                    aspect = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
                elif stop == None:
                    raise error.RunError(22) # missing operand
            elif start == None:
                raise error.RunError(22) 
        elif cval == None:
            raise error.RunError(22)                     
    util.require(ins, util.end_statement)    
    graphics.draw_circle_or_ellipse(x0, y0, r, start, stop, c, aspect)
      
# PAINT -if paint *colour* specified, border default= paint colour
# if paint *attribute* specified, border default=15      
def exec_paint(ins):
    graphics.require_graphics_mode()
    x0, y0 = parse_coord(ins)
    pattern, c, border = '', -1, -1
    if util.skip_white_read_if(ins, (',',)):
        cval = expressions.parse_expression(ins, allow_empty=True)
        if not cval:
            pass
        elif cval[0] == '$':
            # pattern given; copy
            pattern = bytearray(vartypes.pass_string_unpack(cval))
            if not pattern:
                # empty pattern "" is illegal function call
                raise error.RunError(5)
            while len(pattern) % graphics.bitsperpixel != 0:
                 # finish off the pattern with zeros
                 pattern.append(0)
            # default for border, if pattern is specified as string: foreground attr
        else:
            c = vartypes.pass_int_unpack(cval)
        border = c    
        if util.skip_white_read_if(ins, (',',)):
            bval = expressions.parse_expression(ins, allow_empty=True)
            if bval:
                border = vartypes.pass_int_unpack(bval)
            if util.skip_white_read_if(ins, (',',)):
                # background attribute - I can't find anything this does at all.
                # as far as I can see, this is ignored in GW-Basic as long as it's a string not equal to pattern, otherwise error 5
                background_pattern = vartypes.pass_string_unpack(expressions.parse_expression(ins), err=5)
                if background_pattern == pattern:
                    raise error.RunError(5)
    pattern = pattern if pattern else draw_and_play.solid_pattern(c)
    util.require(ins, util.end_statement)         
    graphics.flood_fill(x0, y0, pattern, c, border)        
                
def exec_get_graph(ins):
    graphics.require_graphics_mode()
    util.require(ins, ('(')) # don't accept STEP
    x0,y0 = parse_coord(ins)
    util.require_read(ins, ('\xEA',)) #-
    util.require(ins, ('(')) # don't accept STEP
    x1,y1 = parse_coord(ins)
    util.require_read(ins, (',',)) 
    array = util.get_var_name(ins)    
    util.require(ins, util.end_statement)
    if array not in var.arrays:
        raise error.RunError(5)
    elif array[-1] == '$':
        raise error.RunError(13) # type mismatch    
    graphics.get_area(x0, y0, x1, y1, array)
    
def exec_put_graph(ins):
    graphics.require_graphics_mode()
    util.require(ins, ('(')) # don't accept STEP
    x0,y0 = parse_coord(ins)
    util.require_read(ins, (',',)) 
    array = util.get_var_name(ins)    
    action = '\xF0' # graphics.operation_xor
    if util.skip_white_read_if(ins, (',',)):
        util.require(ins, ('\xC6', '\xC7', '\xEE', '\xEF', '\xF0')) #PSET, PRESET, AND, OR, XOR
        action = ins.read(1)
    util.require(ins, util.end_statement)
    if array not in var.arrays:
        raise error.RunError(5)
    elif array[-1] == '$':
        raise error.RunError(13) # type mismatch    
    graphics.set_area(x0, y0, array, action)
    
def exec_draw(ins):
    graphics.require_graphics_mode()
    gml = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_expression)
    draw_and_play.draw_parse_gml(gml)
    
    
