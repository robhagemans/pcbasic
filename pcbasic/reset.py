"""
PC-BASIC - reset.py
CLEAR command

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import var
import rnd
import devices
import disk
import state
import flow


def clear(close_files=False, preserve_common=False, preserve_all=False, preserve_deftype=False):
    """ Execute a CLEAR command. """
    #   Resets the stack and string space
    #   Clears all COMMON and user variables
    var.clear_variables(preserve_common, preserve_all, preserve_deftype)
    # reset random number generator
    rnd.clear()
    if close_files:
        # close all files
        devices.close_files()
    # release all disk buffers (FIELD)?
    disk.reset_fields()
    # clear last error number (ERR) and line number (ERL)
    state.basic_state.errn, state.basic_state.errp = 0, 0
    # disable error trapping
    state.basic_state.on_error = None
    state.basic_state.error_resume = None
    state.basic_state.error_handle_mode = False
    # stop all sound
    state.console_state.sound.stop_all_sound()
    # Resets STRIG to off
    state.console_state.stick.switch(False)
    # disable all event trapping (resets PEN to OFF too)
    state.basic_state.events.reset()
    # CLEAR also dumps for_next and while_wend stacks
    state.basic_state.for_next_stack = []
    state.basic_state.while_wend_stack = []
    # reset sound and PLAY state
    state.console_state.sound.reset()
    # reset DRAW state (angle, scale) and current graphics position
    state.console_state.screen.drawing.reset()
    # reset the DATA pointer
    flow.restore()
