#
# PC-BASIC 3.23 - stat_sound.py
#
# Sound statements
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import vartypes
import util
import expressions
import events
import draw_and_play
import console

def exec_beep(ins):
    console.sound.beep() 
    # if a syntax error happens, we still beeped.
    util.require(ins, util.end_statement)
    if console.sound.music_foreground:
        console.sound.wait_music()
    
def exec_sound(ins):
    freq = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    dur = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=65535)
    util.require(ins, util.end_statement)
    util.range_check(37, 32767, freq) # 32767 is pause
    console.sound.play_sound(freq, float(dur)/18.2)
    if console.sound.music_foreground:
        console.sound.wait_music()
    
def exec_play(ins):
    if events.play_handler.command(util.skip_white(ins)):
        ins.read(1)
        util.require(ins, util.end_statement)
    else:    
        # retrieve Music Macro Language string
        mml = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_expression)
        draw_and_play.play_parse_mml(mml)
                    
                             
