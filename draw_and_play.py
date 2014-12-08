"""
PC-BASIC 3.23 - draw_and_play.py
DRAW and PLAY macro languages

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
    
import error
import fp
import vartypes
import representation
import util
import var
import state

# generic for both macro languages
ml_whitepace = (' ')


def prepare():
    """ Initialise the draw and play module. """
    pass

def get_value_for_varptrstr(varptrstr):
    """ Get a value given a VARPTR$ representation. """
    if len(varptrstr) < 3:    
        raise error.RunError(5)
    varptrstr = bytearray(varptrstr)
    varptr = vartypes.uint_to_value(bytearray(varptrstr[1:3]))
    found_name = ''
    for name in state.basic_state.var_memory:
        _, var_ptr = state.basic_state.var_memory[name]
        if var_ptr == varptr:
            found_name = name
            break
    if found_name == '':
        raise error.RunError(5)
    return var.get_var(found_name)
        
def ml_parse_value(gmls, default=None):
    """ Parse a value in a macro-language string. """
    c = util.skip(gmls, ml_whitepace)
    sgn = -1 if c == '-' else 1   
    if c in ('+', '-'):
        gmls.read(1)
        c = util.peek(gmls)
        # don't allow default if sign is given
        default = None
    if c == '=':
        gmls.read(1)
        c = util.peek(gmls)
        if len(c) == 0:
            raise error.RunError(5)
        elif ord(c) > 8:
            name = util.get_var_name(gmls)
            indices = ml_parse_indices(gmls)
            step = var.get_var_or_array(name, indices)
            util.require_read(gmls, (';',), err=5)
        else:
            # varptr$
            step = get_value_for_varptrstr(gmls.read(3))
    elif c in representation.ascii_digits:     
        step = ml_parse_const(gmls)
    elif default != None:
        step = default
    else:
        raise error.RunError(5)
    if sgn == -1:
        step = vartypes.number_neg(step)
    return step

def ml_parse_number(gmls, default=None):
    """ Parse and return a number value in a macro-language string. """
    return vartypes.pass_int_unpack(ml_parse_value(gmls, default), err=5)

def ml_parse_const(gmls):
    """ Parse and return a constant value in a macro-language string. """
    c = util.skip(gmls, ml_whitepace)
    if c in representation.ascii_digits:     
        numstr = ''
        while c in representation.ascii_digits:
            gmls.read(1)
            numstr += c 
            c = util.skip(gmls, ml_whitepace) 
        return representation.str_to_value_keep(('$', numstr))
    else:
        raise error.RunError(5)

def ml_parse_const_int(gmls):
    """ Parse a constant value in a macro-language string, return Python int. """
    return vartypes.pass_int_unpack(ml_parse_const(gmls), err=5)    

def ml_parse_string(gmls):
    """ Parse a string value in a macro-language string. """
    c = util.skip(gmls, ml_whitepace)
    if len(c) == 0:
        raise error.RunError(5)
    elif ord(c) > 8:
        name = util.get_var_name(gmls)
        indices = ml_parse_indices(gmls)
        sub = var.get_var_or_array(name, indices)
        util.require_read(gmls, (';',), err=5)
        return vartypes.pass_string_unpack(sub, err=5)
    else:
        # varptr$
        return vartypes.pass_string_unpack(get_value_for_varptrstr(gmls.read(3)))

def ml_parse_indices(gmls):
    """ Parse constant array indices. """
    indices = []
    c = util.skip(gmls, ml_whitepace)
    if c in ('[', '('):
        gmls.read(1)
        while True:
            indices.append(ml_parse_const_int(gmls))
            c = util.skip(gmls, ml_whitepace)
            if c == ',':
                gmls.read(1)
            else:
                break
        util.require_read(gmls, (']', ')'))
    return indices
        
# DRAW statement

deg_to_rad = fp.div(fp.Single.twopi, fp.Single.from_int(360))

def draw_step(x0, y0, sx, sy, plot, goback):
    """ Make a DRAW step, drawing a line and reurning if requested. """
    scale = state.console_state.screen.drawing.draw_scale
    rotate = state.console_state.screen.drawing.draw_angle
    aspect = state.console_state.screen.mode.pixel_aspect
    yfac = aspect[1] / (1.*aspect[0])
    x1 = (scale*sx)/4  
    y1 = (scale*sy)/4
    if rotate == 0 or rotate == 360:
        pass
    elif rotate == 90:
        x1, y1 = int(y1*yfac), -int(x1//yfac)
    elif rotate == 180:
        x1, y1 = -x1, -y1
    elif rotate == 270:
        x1, y1 = -int(y1*yfac), int(x1//yfac)
    else:
        fx, fy = fp.Single.from_int(x1), fp.Single.from_int(y1)
        phi = fp.mul(fp.Single.from_int(rotate), deg_to_rad)
        sinr, cosr = fp.sin(phi), fp.cos(phi)
        fxfac = fp.div(fp.Single.from_int(aspect[0]), fp.Single.from_int(aspect[1]))
        fx, fy = fp.add(fp.mul(cosr,fx), fp.div(fp.mul(sinr,fy), fxfac)), fp.mul(fp.sub(fp.mul(cosr,fy), fxfac), fp.mul(sinr,fx))
        x1, y1 = fx.round_to_int(), fy.round_to_int()
    y1 += y0
    x1 += x0
    if plot:
        state.console_state.screen.drawing.draw_line(x0, y0, x1, y1, state.console_state.screen.drawing.last_attr)    
    state.console_state.screen.drawing.last_point = (x1, y1)
    if goback:
        state.console_state.screen.drawing.last_point = (x0, y0)
            
def draw_parse_gml(gml):
    """ Parse a Graphics Macro Language string. """
    gmls = StringIO(gml.upper())
    plot, goback = True, False
    while True:
        c = util.skip_read(gmls, ml_whitepace).upper()
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
            sub = ml_parse_string(gmls)
            draw_parse_gml(str(sub))            
        elif c == 'C':
            # set foreground colour
            # allow empty spec (default 0), but only if followed by a semicolon
            if util.skip(gmls, ml_whitepace) == ';':
                state.console_state.screen.drawing.last_attr = 0
            else:
                state.console_state.screen.drawing.last_attr = ml_parse_number(gmls) 
        elif c == 'S':
            # set scale
            state.console_state.screen.drawing.draw_scale = ml_parse_number(gmls)
        elif c == 'A':
            # set angle
            # allow empty spec (default 0), but only if followed by a semicolon
            if util.skip(gmls, ml_whitepace) == ';':
                state.console_state.screen.drawing.draw_angle = 0
            else:
                state.console_state.screen.drawing.draw_angle = 90 * ml_parse_number(gmls)   
        elif c == 'T':
            # 'turn angle' - set (don't turn) the angle to any value
            if gmls.read(1).upper() != 'A':
                raise error.RunError(5)
            # allow empty spec (default 0), but only if followed by a semicolon
            if util.skip(gmls, ml_whitepace) == ';':
                state.console_state.screen.drawing.draw_angle = 0
            else:    
                state.console_state.screen.drawing.draw_angle = ml_parse_number(gmls)
        # one-variable movement commands:     
        elif c in ('U', 'D', 'L', 'R', 'E', 'F', 'G', 'H'):
            step = ml_parse_number(gmls, default=vartypes.pack_int(1))
            x0, y0 = state.console_state.screen.drawing.last_point
            x1, y1 = 0, 0
            if c in ('U', 'E', 'H'):
                y1 -= step
            elif c in ('D', 'F', 'G'):
                y1 += step
            if c in ('L', 'G', 'H'):
                x1 -= step
            elif c in ('R', 'E', 'F'):
                x1 += step
            draw_step(x0, y0, x1, y1, plot, goback)
            plot = True
            goback = False
        # two-variable movement command
        elif c == 'M':
            relative =  util.skip(gmls,ml_whitepace) in ('+','-')
            x = ml_parse_number(gmls)
            if util.skip(gmls, ml_whitepace) != ',':
                raise error.RunError(5)
            else:
                gmls.read(1)
            y = ml_parse_number(gmls)
            x0, y0 = state.console_state.screen.drawing.last_point
            if relative:
                draw_step(x0, y0, x, y,  plot, goback)
            else:
                if plot:
                    state.console_state.screen.drawing.draw_line(x0, y0, x, y, state.console_state.screen.drawing.last_attr)    
                state.console_state.screen.drawing.last_point = (x, y)
                state.console_state.screen.drawing.last_attr = c
                if goback:
                    state.console_state.screen.drawing.last_point = (x0, y0)
            plot = True
            goback = False
        elif c =='P':
            # paint - flood fill
            x, y = state.console_state.screen.drawing.get_window_logical(*state.console_state.screen.drawing.last_point)
            colour = ml_parse_number(gmls)
            if util.skip_read(gmls, ml_whitepace) != ',':
                raise error.RunError(5)
            bound = ml_parse_number(gmls)
            state.console_state.screen.drawing.paint((x, y, False), None, colour, bound, None)    


    
# PLAY statement

import backend

# 12-tone equal temperament
# C, C#, D, D#, E, F, F#, G, G#, A, A#, B
note_freq = [ 440.*2**((i-33.)/12.) for i in range(84) ]
notes = {   'C':0, 'C#':1, 'D-':1, 'D':2, 'D#':3, 'E-':3, 'E':4, 'F':5, 'F#':6, 
            'G-':6, 'G':7, 'G#':8, 'A-':8, 'A':9, 'A#':10, 'B-':10, 'B':11 }

class PlayState(object):
    """ State variables of the PLAY command. """
    
    def __init__(self):
        """ Initialise play state. """
        self.octave = 4
        self.speed = 7./8.
        self.tempo = 2. # 2*0.25 =0 .5 seconds per quarter note
        self.length = 0.25
        self.volume = 15

state.basic_state.play_state = [ PlayState(), PlayState(), PlayState() ]

def play_parse_mml(mml_list):
    """ Parse a Music Macro Language string. """
    gmls_list = []
    for mml in mml_list:
        gmls = StringIO()
        gmls.write(str(mml).upper())
        gmls.seek(0)
        gmls_list.append(gmls)
    next_oct = 0
    voices = range(3)
    while True:
        if not voices:
            break
        for voice in voices:
            gmls = gmls_list[voice]
            c = util.skip_read(gmls, ml_whitepace).upper()
            if c == '':
                voices.remove(voice)
                continue
            elif c == ';':
                continue
            elif c == 'X':
                # execute substring
                sub = ml_parse_string(gmls)
                pos = gmls.tell()
                rest = gmls.read()
                gmls.truncate(pos)
                gmls.write(str(sub))
                gmls.write(rest)
                gmls.seek(pos)
            elif c == 'N':
                note = ml_parse_number(gmls)
                dur = state.basic_state.play_state[voice].length
                c = util.skip(gmls, ml_whitepace).upper()
                if c == '.':
                    gmls.read(1)
                    dur *= 1.5
                if note > 0 and note <= 84:
                    state.console_state.sound.play_sound(note_freq[note-1], dur*state.basic_state.play_state[voice].tempo, 
                                     state.basic_state.play_state[voice].speed, volume=state.basic_state.play_state[voice].volume,
                                     voice=voice)
                elif note == 0:
                    state.console_state.sound.play_sound(0, dur*state.basic_state.play_state[voice].tempo, 
                                    state.basic_state.play_state[voice].speed,
                                    volume=0, voice=voice)
            elif c == 'L':
                state.basic_state.play_state[voice].length = 1./ml_parse_number(gmls)    
            elif c == 'T':
                state.basic_state.play_state[voice].tempo = 240./ml_parse_number(gmls)    
            elif c == 'O':
                state.basic_state.play_state[voice].octave = min(6, max(0, ml_parse_number(gmls)))
            elif c == '>':
                state.basic_state.play_state[voice].octave += 1
                if state.basic_state.play_state[voice].octave > 6:
                    state.basic_state.play_state[voice].octave = 6
            elif c == '<':
                state.basic_state.play_state[voice].octave -= 1
                if state.basic_state.play_state[voice].octave < 0:
                    state.basic_state.play_state[voice].octave = 0
            elif c in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'P'):
                note = c
                dur = state.basic_state.play_state[voice].length
                while True:    
                    c = util.skip(gmls, ml_whitepace).upper()
                    if c == '.':
                        gmls.read(1)
                        dur *= 1.5
                    elif c in representation.ascii_digits:
                        numstr = ''
                        while c in representation.ascii_digits:
                            gmls.read(1)
                            numstr+=c 
                            c = util.skip(gmls, ml_whitepace) 
                        length = vartypes.pass_int_unpack(representation.str_to_value_keep(('$', numstr)))
                        dur = 1./float(length)
                    elif c in ('#', '+'):
                        gmls.read(1)
                        note += '#'
                    elif c == '-':
                        gmls.read(1)
                        note += '-'
                    else:
                        break                    
                if note == 'P':
                    state.console_state.sound.play_sound(0, dur*state.basic_state.play_state[voice].tempo, 
                                state.basic_state.play_state[voice].speed,
                                volume=state.basic_state.play_state[voice].volume, voice=voice)
                else:
                    state.console_state.sound.play_sound(note_freq[(state.basic_state.play_state[voice].octave+next_oct)*12+notes[note]], 
                            dur*state.basic_state.play_state[voice].tempo, state.basic_state.play_state[voice].speed, 
                            volume=state.basic_state.play_state[voice].volume, voice=voice)
                next_oct = 0
            elif c == 'M':
                c = util.skip_read(gmls, ml_whitepace).upper()
                if c == 'N':        state.basic_state.play_state[voice].speed = 7./8.
                elif c == 'L':      state.basic_state.play_state[voice].speed = 1.
                elif c == 'S':      state.basic_state.play_state[voice].speed = 3./4.        
                elif c == 'F':      state.console_state.sound.foreground = True
                elif c == 'B':      state.console_state.sound.foreground = False
                else:
                    raise error.RunError(5)    
            elif c == 'V' and ( backend.pcjr_sound == 'tandy' or 
                                (backend.pcjr_sound == 'pcjr' and state.console_state.sound.sound_on)): 
                state.basic_state.play_state[voice].volume = min(15, max(0, ml_parse_number(gmls)))
            else:
                raise error.RunError(5)    
    if state.console_state.sound.foreground:
        state.console_state.sound.wait_music()
 
prepare()

