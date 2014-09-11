#
# PC-BASIC 3.23  - reset.py
#
# General reset commands (NEW and CLEAR)
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# NOTE: RESTORE is in program.py

import var
import rnd
import iolayer
import state
import backend

# CLEAR
def clear(close_files=False, preserve_common=False, preserve_all=False, preserve_deftype=False):
    #   Resets the stack and string space
    #   Clears all COMMON and user variables
    var.clear_variables(preserve_common, preserve_all, preserve_deftype)
    # reset random number generator
    rnd.clear()
    if close_files:
        # close all files
        iolayer.close_all()
    # release all disk buffers (FIELD)?
    state.io_state.fields = {}
    # clear ERR and ERL
    state.basic_state.errn, state.basic_state.errp = 0, 0
    # disable error trapping
    state.basic_state.on_error = None
    state.basic_state.error_resume = None
    # stop all sound
    backend.stop_all_sound()
    #   Resets sound to music foreground
    backend.music_foreground = True
    #   Resets STRIG to off
    state.console_state.stick_is_on = False
    # disable all event trapping (resets PEN to OFF too)
    backend.reset_events()
    # CLEAR also dumps for_next and while_wend stacks
    state.basic_state.for_next_stack = []
    state.basic_state.while_wend_stack = []



