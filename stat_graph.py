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

import StringIO

import glob
import error
import vartypes
import var
import util
import tokenise
import expressions
import fp
import events
import graphics




def parse_coord(ins):
    util.require_read(ins, '(')
    x = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require_read(ins, ',')
    y = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require_read(ins, ')')
    return x,y    


def exec_pset(ins, default_colour=-1):
    graphics.require_graphics_mode()
    
    relative = util.skip_white_read_if(ins, '\xCF') # STEP
    x,y = parse_coord(ins)
    
    c = default_colour
    if util.skip_white_read_if(ins, ','):
        c = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require(ins, util.end_statement)    
    
    x,y, = graphics.window_coords(x,y)
    
    if relative:
        x += graphics.last_point[0]
        y += graphics.last_point[1]        
    
    graphics.put_point(x,y,c)
        
def exec_preset(ins):
    exec_pset(ins, -2)   
    
    

def exec_line_graph(ins):
    graphics.require_graphics_mode()
    
    if util.skip_white(ins)=='(':
        coord = parse_coord(ins)
        x0,y0=graphics.window_coords(*coord)
    else:
        x0,y0=graphics.last_point
        
    util.require_read(ins, '\xEA') # -
        
    x1,y1 = graphics.window_coords(*parse_coord(ins))
    
    c = -1    
    mode='L'
    mask=0xffff
    if util.skip_white_read_if(ins, ','):
        expr = expressions.parse_expression(ins, allow_empty=True)
        if expr != None and expr != ('',''):
            c = vartypes.pass_int_keep(expr)[1]
    
        if util.skip_white_read_if(ins, ','):
            if util.skip_white_read_if(ins, 'B'):
                mode='B'
                if util.skip_white_read_if(ins, 'F'):         
                    mode='BF'
            if util.skip_white_read_if(ins, ','):
                mask = vartypes.pass_int_keep(expressions.parse_expression(ins, allow_empty=True), maxint=0xffff)[1]
                    
    util.require(ins, util.end_statement)    
    
    if mode=='L':
        graphics.draw_line(x0,y0,x1,y1,c,mask)
    elif mode=='B':
        # TODO: we don't exactly match GW's way of applying the pattern, haven't found the logic of it
        graphics.draw_box(x0,y0,x1,y1,c,mask)
    elif mode=='BF':
        graphics.draw_box_filled(x0,y0,x1,y1,c)
            
            
def exec_view_graph(ins):
    graphics.require_graphics_mode()
    absolute = util.skip_white_read_if(ins, '\xC8') #SCREEN
    
    if util.skip_white(ins)=='(':
        x0,y0 = parse_coord(ins)
        util.require_read(ins, '\xEA') #-
        x1,y1 = parse_coord(ins)
        
        # not scaled by WINDOW
        x0 = fp.round_to_int(x0)
        x1 = fp.round_to_int(x1)
        y0 = fp.round_to_int(y0)
        y1 = fp.round_to_int(y1)        
        
        fill, border = None, None
        if util.skip_white_read_if(ins, ','):
            [fill, border] = expressions.parse_int_list(ins, 2, err=2)
            
        
        if fill != None:
            graphics.draw_box_filled(x0,y0,x1,y1, fill)
        if border!= None:
            graphics.draw_box(x0-1,y0-1,x1+1,y1+1, border)
        graphics.set_graph_view(x0,y0, x1,y1, absolute)
        
    else:
        graphics.unset_graph_view()
                
    util.require(ins, util.end_expression)        
    
    
def exec_window(ins):
    graphics.require_graphics_mode()
    cartesian = not util.skip_white_read_if(ins, '\xC8') #SCREEN
    
    if util.skip_white(ins)=='(':
        x0,y0 = parse_coord(ins)
        util.require_read(ins, '\xEA') #-
        x1,y1 = parse_coord(ins)
        
        graphics.set_graph_window(x0,y0, x1,y1, cartesian)
        
    else:
        graphics.unset_graph_window()
                
    util.require(ins, util.end_expression)        
    
        
def exec_circle(ins):
    graphics.require_graphics_mode()
    x0,y0 = graphics.window_coords(*parse_coord(ins))
    util.require_read(ins, ',')
    r = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    
    c = -1
    start, stop = ('',''), ('','')
    aspect = graphics.get_aspect_ratio()
    if util.skip_white_read_if(ins, ','):
        cval = expressions.parse_expression(ins, allow_empty=True)
        if cval != ('',''):
            c = vartypes.pass_int_keep(cval)[1]
        if util.skip_white_read_if(ins, ','):
            start = expressions.parse_expression(ins, allow_empty=True)
            util.require_read(ins, ',')
            stop = expressions.parse_expression(ins, allow_empty=True)
            if util.skip_white_read_if(ins, ','):
                aspect = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require(ins, util.end_expression)        

    if fp.equals(aspect, aspect.one):
        # rx=r
        rx, dummy = graphics.window_scale(r,fp.MBF_class.zero)
        ry = rx
    else:
        if fp.gt(aspect, aspect.one):
            #ry = r
            dummy, ry = graphics.window_scale(fp.MBF_class.zero,r)
            rx = fp.round_to_int(fp.div(r, aspect))
        else:
            #rx = r
            rx, dummy = graphics.window_scale(r,fp.MBF_class.zero)
            ry = fp.round_to_int(fp.mul(r, aspect))

    start_octant, start_coord, start_line = -1, -1, False
    if start != ('',''):
        start = fp.unpack(vartypes.pass_single_keep(start))
        start_octant, start_coord, start_line = get_octant(start, rx, ry)
    stop_octant, stop_coord, stop_line = -1, -1, False
    if stop != ('',''):
        stop = fp.unpack(vartypes.pass_single_keep(stop))
        stop_octant, stop_coord, stop_line = get_octant(stop, rx, ry)
        
    
    if fp.equals(aspect, aspect.one):
        graphics.draw_circle(x0,y0,rx,c, start_octant, start_coord, start_line, stop_octant, stop_coord, stop_line)
    else:
        # TODO - make this all more sensible, calculate only once
        startx, starty, stopx, stopy = -1,-1,-1,-1
        if start!=('',''):
            #start = fp.unpack(vartypes.pass_single_keep(start))
            startx = abs(fp.round_to_int(fp.mul(fp.from_int(fp.MBF_class, rx), fp.mbf_cos(start))))
            starty = abs(fp.round_to_int(fp.mul(fp.from_int(fp.MBF_class, ry), fp.mbf_sin(start))))
        if stop!=('',''):
            #stop = fp.unpack(vartypes.pass_single_keep(stop))
            stopx = abs(fp.round_to_int(fp.mul(fp.from_int(fp.MBF_class, rx), fp.mbf_cos(stop))))
            stopy = abs(fp.round_to_int(fp.mul(fp.from_int(fp.MBF_class, ry), fp.mbf_sin(stop))))
        
        graphics.draw_ellipse(x0,y0,rx,ry,c, start_octant/2, startx, starty, start_line, stop_octant/2, stopx, stopy, stop_line)
         
        #graphics.draw_ellipse1(x0-rx,y0-ry,x0+rx,y0+ry,c)
            

def get_octant(mbf, rx, ry):
    
    neg = fp.sign(mbf) == -1
    if neg:
        mbf = fp.neg(mbf)

    octant=0
    comp = fp.mbf_pi4
    while fp.gt(mbf,comp):
        comp = fp.add(comp, fp.mbf_pi4)
        octant += 1
        if octant >= 8:
            raise error.RunError(5) # ill fn call
    
    if octant in (0,3,4,7):
        # running var is y
        coord = abs(fp.round_to_int(fp.mul(fp.from_int(fp.MBF_class, ry), fp.mbf_sin(mbf))))
    else:
        # running var is x    
        coord = abs(fp.round_to_int(fp.mul(fp.from_int(fp.MBF_class, rx), fp.mbf_cos(mbf))))
    return octant, coord, neg                 



def solid_pattern(c):
    pattern=[0]*graphics.bitsperpixel
    for b in range(graphics.bitsperpixel):
        if (c&(1<<b)!=0):
            pattern[b]=0xff
    return pattern
      
      
# PAINT -if paint *colour* specified, border default= paint colour
# if border *attribute* specified, border default=15      
def exec_paint(ins):
    graphics.require_graphics_mode()
    
    x0,y0 = graphics.window_coords(*parse_coord(ins))
    pattern = ''
    c = graphics.get_colour_index(-1) 
    border= c
    
    if util.skip_white_read_if(ins, ','):
        cval = expressions.parse_expression(ins, allow_empty=True)
        
        
        if cval[0]=='$':
            # pattern given
            pattern = vartypes.pass_string_keep(cval)[1]
            pattern = map(ord, list(pattern))
            if len(pattern)==0:
                # empty pattern "" is illegal function call
                raise error.RunError(5)
            while len(pattern)%graphics.bitsperpixel !=0:
                 # finish off the pattern with zeros
                 pattern.append(0)
            # default for border,  if pattern is specified as string
            # foreground attr
            c=-1
            
        elif cval == ('',''):
            # default
            pass
        else:
            c = vartypes.pass_int_keep(cval)[1]
        
        border = c    
        if util.skip_white_read_if(ins, ','):
            bval = expressions.parse_expression(ins, allow_empty=True)
            if bval == ('',''):
                pass
            else:
                border = vartypes.pass_int_keep(bval)[1]
        
            if util.skip_white_read_if(ins, ','):
                background_pattern = vartypes.pass_string_keep(expressions.parse_expression(ins), err=5)[1]
                # background attribute - I can't find anything this does at all.
                # as far as I can see, this is ignored in GW-Basic as long as it's a string, otherwise error 5
    
    if pattern=='':
        pattern = solid_pattern(c)
    
    util.require(ins, util.end_statement)         
    graphics.flood_fill(x0,y0, pattern, c, border)        
            
    
    
    
                
def exec_get_graph(ins):
    graphics.require_graphics_mode()
    x0,y0 = graphics.window_coords(*parse_coord(ins))
    util.require_read(ins, '\xEA') #-
    x1,y1 = graphics.window_coords(*parse_coord(ins))
    util.require_read(ins, ',') 
    array = var.get_var_name(ins)    
    util.require(ins, util.end_statement)
        
    byte_array = graphics.get_area(x0,y0,x1,y1, array)
    

    
def exec_put_graph(ins):
    graphics.require_graphics_mode()
    x0,y0 = graphics.window_coords(*parse_coord(ins))
    util.require_read(ins, ',') 
    array = var.get_var_name(ins)    
    action = graphics.operation_xor
    if util.skip_white_read_if(ins, ','):
        c =util.skip_white_read(ins) 
        if c == '\xC6': #PSET
            action = graphics.operation_set
        elif c == '\xC7': #PRESET
            action = graphics.operation_not
        elif c == '\xEE': #AND
            action = graphics.operation_and
        elif c == '\xEF': #OR
            action = graphics.operation_or
        elif c == '\xF0': #XOR
            action = graphics.operation_xor
    util.require(ins, util.end_statement)
    
    graphics.set_area(x0,y0, array, action)
    
    
    
# GRAPHICS MACRO LANGUAGE
    
gml_whitespace = (' ')
deg_to_rad = fp.div( fp.mbf_twopi, fp.from_int(fp.MBF_class, 360))

draw_scale=4
draw_angle=0
    
    
def draw_parse_value(gmls):
    c = util.skip(gmls, gml_whitespace)
    
    if c=='=':
        gmls.read(1)    
        step = var.getvar(var.get_var_name(gmls))
        util.require_read(gmls,';', err=5)
    else:
        sgn=1
        if c=='+':
            gmls.read(1)
            c = util.peek(gmls)
        elif c=='-':
            gmls.read(1)
            c = util.peek(gmls)
            sgn=-1   
        
        if c in tokenise.ascii_digits:     
            numstr=''
            while c in tokenise.ascii_digits:
                gmls.read(1)
                numstr+=c 
                c = util.skip(gmls, gml_whitespace) 
            step = tokenise.str_to_value_keep(('$', numstr))
            if sgn==-1:
                step = vartypes.vneg(step)
        else:
            raise error.RunError(5)
    return step



def draw_parse_number(gmls):
    return vartypes.pass_int_keep(draw_parse_value(gmls), err=5)[1]
    

def draw_parse_string(gmls):
    util.skip(gmls, gml_whitespace)
    sub = var.getvar(var.get_var_name(gmls))
    util.require_read(gmls,';', err=5)
    return vartypes.pass_string_keep(sub, err=5)[1]





def draw_step(x0,y0, sx,sy, plot, goback):
    global draw_scale, draw_angle
    scale = draw_scale
    rotate = draw_angle
    
    x1 = (scale*sx)/4  
    y1 = (scale*sy)/4
    
    if rotate==0:
        pass
    elif rotate==90:
        x1,y1 = y1,-x1
    elif rotate==180:
        x1,y1 = -x1,-y1
    elif rotate==270:
        x1,y1 = -y1,x1
    else:
        fx,fy = fp.from_int(fp.MBF_class, x1), fp.from_int(fp.MBF_class, y1)
        phi = fp.mul(fp.from_int(fp.MBF_class, rotate), deg_to_rad)
        sinr, cosr = fp.mbf_sin(phi), fp.mbf_cos(phi)
        fx,fy = fp.add(fp.mul(cosr,fx), fp.mul(sinr,fy)), fp.sub(fp.mul(cosr,fy), fp.mul(sinr,fx)) 
        x1,y1 = fp.round_to_int(fx), fp.round_to_int(fy)
        
    y1 += y0
    x1 += x0
    
    if plot:
        graphics.draw_line(x0,y0,x1,y1,-1)    
    else:
        graphics.last_point=(x1,y1)
        
    if goback:
        graphics.last_point=(x0,y0)
        
    
            

def draw_parse_gml(gml):
    global draw_scale, draw_angle
    
    gmls = StringIO.StringIO(gml)
    plot=True
    goback=False
    
    while True:
        c = util.skip_read(gmls, gml_whitespace).upper()
        
        if c=='':
            break
        elif c==';':
            continue
        elif c=='B':
            # do not draw
            plot=False
        elif c=='N':
            # return to postiton after move
            goback=True            
        elif c=='X':
            # execute substring
            sub = draw_parse_string(gmls)
            draw_parse_gml(sub)            
            
        elif c=='C':
            # set foreground colour
            colour = draw_parse_number(gmls)
            glob.scrn.set_attr(colour,0)
        elif c=='S':
            # set scale
            draw_scale = draw_parse_number(gmls)
        elif c=='A':
            # set angle
            draw_angle = 90*draw_parse_number(gmls)   
        elif c=='T':
            # 'turn angle' - set (don't turn) the angle to any value
            if gmls.read(1).upper() != 'A':
                raise error.RunError(5)
            draw_angle = draw_parse_number(gmls)
                
        # one-variable movement commands:     
        elif c in ('U', 'D', 'L', 'R', 'E', 'F', 'G', 'H'):
            step = draw_parse_number(gmls)
            x0,y0 = graphics.last_point
            #x1,y1=x0,y0
            x1,y1 = 0,0
            if c in ('U', 'E', 'H'):
                y1 -= step
            elif c in ('D', 'F', 'G'):
                y1 += step
            if c in ('L', 'G', 'H'):
                x1 -= step
            elif c in ('R', 'E', 'F'):
                x1 += step
            
            draw_step(x0,y0,x1,y1, plot, goback)
            plot = True
            goback = False
                
        # two-variable movement command
        elif c =='M':
            relative =  util.skip(gmls,gml_whitespace) in ('+','-')
            x = draw_parse_number(gmls)
            
            if util.skip(gmls, gml_whitespace) !=',':
                raise error.RunError(5)
            else:
                gmls.read(1)
            
            y = draw_parse_number(gmls)
            
            
            x0,y0 = graphics.last_point
            if relative:
                draw_step(x0,y0,x,y,  plot, goback)
                
            else:
                if plot:
                    graphics.draw_line(x0,y0,x,y,-1)    
                else:
                    graphics.last_point=(x,y)
                if goback:
                    graphics.last_point=(x0,y0)
            
            plot = True
            goback = False
            
            
        elif c =='P':
            # paint - flood fill
            
            x0,y0 = graphics.last_point
            
            colour = draw_parse_number(gmls)
            if util.skip(gmls, gml_whitespace) !=',':
                raise error.RunError(5)
            bound = draw_parse_number(gmls)
            
            graphics.flood_fill(x0,y0,solid_pattern(colour), colour, bound)    
        
    
def exec_draw(ins):
    graphics.require_graphics_mode()
    
    # retrieve Graphics Macro Language string
    gml = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
    util.require(ins, util.end_expression)
    
    draw_parse_gml(gml)
    
    
    

def exec_beep(ins):
    util.require(ins, util.end_statement)
    glob.sound.beep() 
    if music_foreground:
        glob.sound.wait_music()
    
def exec_sound(ins):
    freq = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require_read(ins, ',')
    dur = vartypes.pass_int_keep(expressions.parse_expression(ins), maxint=65535)[1]
    util.require(ins, util.end_statement)
    if freq == 32767:
        glob.sound.play_pause(float(dur)/18.2)
    elif freq>=37 and freq<32767:    
        glob.sound.play_sound(freq, float(dur)/18.2)
    else:
        raise error.RunError(5)
    
    if music_foreground:
        glob.sound.wait_music()
    
def exec_play(ins):
    
    d = util.skip_white(ins)
    if d == '\x95': # ON
        ins.read(1)
        events.play_enabled = True
    elif d == '\xdd': # OFF
        ins.read(1)
        events.play_enabled = False
    elif d== '\x90': #STOP
        ins.read(1)
        events.play_stopped = True
    
    else:
        # retrieve Music Macro Language string
        mml = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
        util.require(ins, util.end_expression)
        
        play_parse_mml(mml)
    
    util.require(ins, util.end_statement)                
                    
# 12-tone equal temperament
# C, C#, D, D#, E, F, F#, G, G#, A, A#, B
note_freq = [ 440.*2**((i-33.)/12.) for i in range(84) ]
play_octave=4
play_speed=7./8.
play_tempo= 2. # 2*0.25 =0.5 seconds per quarter note
play_length=0.25

notes = { 'C':0, 'C#':1, 'D-':1, 'D':2, 'D#':3, 'E-':3, 'E':4, 'F':5, 'F#':6, 'G-':6, 'G':7, 'G#':8, 'A-':8, 'A':9, 'A#':10, 'B-':10, 'B':11 }

music_foreground=True

def play_parse_mml(mml):
    global play_octave, play_speed, play_length, play_tempo, music_foreground
    gmls = StringIO.StringIO(mml)
    next_oct=0
    while True:
        c = util.skip_read(gmls, gml_whitespace).upper()
        
        if c=='':
            break
        elif c==';':
            continue
        elif c=='X':
            # execute substring
            sub = draw_parse_string(gmls)
            play_parse_mml(sub)
            
        elif c=='N':
            note = draw_parse_number(gmls)
            if note>0 and note<=84:
                glob.sound.play_sound(note_freq[note-1], play_length*play_speed*play_tempo)
        
            if note==0:
                glob.sound.play_pause(play_length*play_speed*play_tempo)

        elif c=='L':
            play_length = 1./draw_parse_number(gmls)    
        elif c=='T':
            play_tempo = 240./draw_parse_number(gmls)    
        
        
        elif c=='O':
            play_octave = draw_parse_number(gmls)
            if play_octave<0:
                play_octave=0
            if play_octave>6:
                play_octave=6        
        elif c=='>':
            #next_oct=1
            play_octave += 1
            if play_octave>6:
                play_octave=6
        elif c=='<':
            #next_oct=-1
            play_octave -=1
            if play_octave<0:
                play_octave=0
                        
        elif c in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'P'):
            note=c
            dur=play_length
            while True:    
                c = util.skip(gmls, gml_whitespace).upper()
                if c=='.':
                    gmls.read(1)
                    dur *= 1.5
                elif c in tokenise.ascii_digits:
                    numstr=''
                    
                    while c in tokenise.ascii_digits:
                        gmls.read(1)
                        numstr+=c 
                        c = util.skip(gmls, gml_whitespace) 
                    length = vartypes.pass_int_keep(tokenise.str_to_value_keep(('$', numstr)))[1]
                    dur = 2./float(length)
                elif c in ('#', '+'):
                    gmls.read(1)
                    note+='#'
                elif c == '-':
                    gmls.read(1)
                    note+='-'
                else:
                    break                    
            if note=='P':
                glob.sound.play_pause(dur*play_speed*play_tempo)
            
            else:        
                glob.sound.play_sound(note_freq[(play_octave+next_oct)*12+notes[note]], dur*play_speed*play_tempo)
            next_oct=0
        
        elif c=='M':
            c = util.skip_read(gmls, gml_whitespace).upper()
            if c=='N':
                play_speed=7./8.
            elif c=='L':
                play_speed==1.
            elif c=='S':
                play_speed=3./4.        
            elif c=='F':
                # foreground
                music_foreground=True
            elif c=='B':
                # background
                music_foreground=False
                            
            
            else:
                raise error.RunError(5)    
        else:
            raise error.RunError(5)    
    
    if music_foreground:
        glob.sound.wait_music()
                             
