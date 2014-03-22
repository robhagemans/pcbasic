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

import fp
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
        console.sound.wait_music(wait_last=False)
    
def exec_sound(ins):
    freq = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    dur = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
        raise error.RunError(5)
    util.require(ins, util.end_statement)
    if dur.is_zero():
        console.sound.stop_all_sound()
        return
    util.range_check(37, 32767, freq) # 32767 is pause
    one_over_44 = fp.Single.from_bytes(bytearray('\x8c\x2e\x3a\x7b')) # 1/44 = 0.02272727248
    dur_sec = dur.to_value()/18.2
    if one_over_44.gt(dur):
        # play indefinitely in background
        console.sound.play_sound(freq, dur_sec, loop=True)
    else:
        console.sound.play_sound(freq, dur_sec)
        if console.sound.music_foreground:
            console.sound.wait_music(wait_last=False)
    
def exec_play(ins):
    if events.play_handler.command(util.skip_white(ins)):
        ins.read(1)
        util.require(ins, util.end_statement)
    else:    
        # retrieve Music Macro Language string
        mml = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_expression)
        draw_and_play.play_parse_mml(mml)
                    
                             
