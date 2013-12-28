#
# PC-BASIC 3.23 - stat_sound.py
#
# Sound statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import error
import vartypes
import util
import expressions
import events
import sound
import draw_and_play


def exec_beep(ins):
    util.require(ins, util.end_statement)
    sound.beep() 
    if sound.music_foreground:
        sound.wait_music()
    
    
def exec_sound(ins):
    freq = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require_read(ins, ',')
    dur = vartypes.pass_int_keep(expressions.parse_expression(ins), maxint=65535)[1]
    util.require(ins, util.end_statement)
    if freq == 32767:
        sound.play_pause(float(dur)/18.2)
    elif freq>=37 and freq<32767:    
        sound.play_sound(freq, float(dur)/18.2)
    else:
        raise error.RunError(5)
    
    if sound.music_foreground:
        sound.wait_music()

    
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
        draw_and_play.play_parse_mml(mml)
    
    util.require(ins, util.end_statement)                
                    
                             
