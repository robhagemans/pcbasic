"""
PC-BASIC - parser.py
BASIC code parser

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
from functools import partial
import logging
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import string

import console
import debug
import disk
import error
import events
import expressions
import fp
import devices
import memory
from operators import Operators as op
import ports
import print_and_input
import program
import representation
import sound
import state
import basictoken as tk
import util
import var
import vartypes
import statements


class Parser(object):
    """ Statement parser. """

    def __init__(self, session, syntax, term):
        """ Initialise parser. """
        self.session = session
        # syntax: advanced, pcjr, tandy
        self.syntax = syntax
        # program for TERM command
        self.term = term
        # line number tracing
        self.tron = False
        # pointer position: False for direct line, True for program
        self.run_mode = False
        self.program_code = session.program.bytecode
        self.current_statement = 0
        # clear stacks
        self.clear_stacks_and_pointers()
        # set up event handlers
        self.events = events.Events(self.session, syntax)
        self.init_error_trapping()
        self.error_num = 0
        self.error_pos = 0
        self.statements = statements.Statements(self)

    def init_error_trapping(self):
        """ Initialise error trapping. """
        # True if error handling in progress
        self.error_handle_mode = False
        # statement pointer, run mode of error for RESUME
        self.error_resume = None
        # pointer to error trap
        self.on_error = None

    def parse_statement(self):
        """ Parse one statement at the current pointer in current codestream.
            Return False if stream has ended, True otherwise.
            """
        try:
            self.handle_basic_events()
            self.ins = self.get_codestream()
            self.current_statement = self.ins.tell()
            c = util.skip_white(self.ins)
            if c == '':
                # stream has ended.
                return False
            # parse line number or : at start of statement
            elif c == '\0':
                # save position for error message
                prepos = self.ins.tell()
                self.ins.read(1)
                # line number marker, new statement
                linenum = util.parse_line_number(self.ins)
                if linenum == -1:
                    if self.error_resume:
                        # unfinished error handler: no RESUME (don't trap this)
                        self.error_handle_mode = True
                        # get line number right
                        raise error.RunError(error.NO_RESUME, prepos-1)
                    # stream has ended
                    return False
                if self.tron:
                    console.write('[' + ('%i' % linenum) + ']')
                self.session.debugger.debug_step(linenum)
            elif c == ':':
                self.ins.read(1)
            c = util.skip_white(self.ins)
            # empty statement, return to parse next
            if c in tk.end_statement:
                return True
            # implicit LET
            elif c in string.ascii_letters:
                self.statements.exec_let(self.ins)
            # token
            else:
                self.ins.read(1)
                if c in tk.twobyte:
                    c += self.ins.read(1)
                # don't use try-block to avoid catching other KeyErrors in statement
                if c not in self.statements.statements:
                    raise error.RunError(error.STX)
                self.statements.statements[c](self.ins)
        except error.RunError as e:
            self.trap_error(e)
        return True

    #################################################################

    def clear(self):
        """ Clear all to be cleared for CLEAR statement. """
        # clear last error number (ERR) and line number (ERL)
        self.error_num, self.error_pos = 0, 0
        # disable error trapping
        self.init_error_trapping()
        # disable all event trapping (resets PEN to OFF too)
        self.events.reset()
        # CLEAR also dumps for_next and while_wend stacks
        self.clear_loop_stacks()
        # reset the DATA pointer
        self.restore()

    def clear_stacks_and_pointers(self):
        """ Initialise the stacks and pointers for a new program. """
        # stop running if we were
        self.set_pointer(False)
        # reset loop stacks
        self.clear_stacks()
        # reset program pointer
        self.program_code.seek(0)
        # reset stop/cont
        self.stop = None
        # reset data reader
        self.restore()

    def clear_stacks(self):
        """ Clear loop and jump stacks. """
        self.gosub_stack = []
        self.clear_loop_stacks()

    def clear_loop_stacks(self):
        """ Clear loop stacks. """
        self.for_stack = []
        self.while_stack = []

    #################################################################

    def handle_basic_events(self):
        """ Jump to user-defined event subs if events triggered. """
        if self.events.suspend_all or not self.run_mode:
            return
        for event in self.events.all:
            if (event.enabled and event.triggered
                    and not event.stopped and event.gosub is not None):
                # release trigger
                event.triggered = False
                # stop this event while handling it
                event.stopped = True
                # execute 'ON ... GOSUB' subroutine;
                # attach handler to allow un-stopping event on RETURN
                self.jump_gosub(event.gosub, event)

    def trap_error(self, e):
        """ Handle a BASIC error through trapping. """
        if e.pos is None:
            if self.run_mode:
                e.pos = self.program_code.tell()-1
            else:
                e.pos = -1
        self.error_num = e.err
        self.error_pos = e.pos
        # don't jump if we're already busy handling an error
        if self.on_error is not None and self.on_error != 0 and not self.error_handle_mode:
            self.error_resume = self.current_statement, self.run_mode
            self.jump(self.on_error)
            self.error_handle_mode = True
            self.events.suspend_all = True
        else:
            self.error_handle_mode = False
            raise e

    #################################################################

    def set_pointer(self, new_runmode, pos=None):
        """ Set program pointer to the given codestream and position. """
        self.run_mode = new_runmode
        state.console_state.sound.persist(new_runmode)
        codestream = self.get_codestream()
        if pos is not None:
            # jump to position, if given
            codestream.seek(pos)
        else:
            # position at end - don't execute anything unless we jump
            codestream.seek(0, 2)

    def get_codestream(self):
        """ Get the current codestream. """
        return self.program_code if self.run_mode else self.session.direct_line

    def jump(self, jumpnum, err=error.UNDEFINED_LINE_NUMBER):
        """ Execute jump for a GOTO or RUN instruction. """
        if jumpnum is None:
            self.set_pointer(True, 0)
        else:
            try:
                # jump to target
                self.set_pointer(True, self.session.program.line_numbers[jumpnum])
            except KeyError:
                raise error.RunError(err)

    def jump_gosub(self, jumpnum, handler=None):
        """ Execute jump for a GOSUB. """
        # set return position
        self.gosub_stack.append((self.get_codestream().tell(), self.run_mode, handler))
        self.jump(jumpnum)

    def jump_return(self, jumpnum):
        """ Execute jump for a RETURN. """
        try:
            pos, orig_runmode, handler = self.gosub_stack.pop()
        except IndexError:
            raise error.RunError(error.RETURN_WITHOUT_GOSUB)
        # returning from ON (event) GOSUB, re-enable event
        if handler:
            # if stopped explicitly using STOP, we wouldn't have got here; it STOP is run  inside the trap, no effect. OFF in trap: event off.
            handler.stopped = False
        if jumpnum is None:
            # go back to position of GOSUB
            self.set_pointer(orig_runmode, pos)
        else:
            # jump to specified line number
            self.jump(jumpnum)


    #################################################################

    def loop_init(self, ins, forpos, nextpos, varname, start, stop, step):
        """ Initialise a FOR loop. """
        # set start to start-step, then iterate - slower on init but allows for faster iterate
        self.session.scalars.set(varname, op.number_add(start, op.number_neg(step)))
        # NOTE: all access to varname must be in-place into the bytearray - no assignments!
        sgn = vartypes.integer_to_int_signed(op.number_sgn(step))
        self.for_stack.append(
            (forpos, nextpos, varname[-1],
                self.session.scalars.variables[varname],
                vartypes.number_unpack(stop), vartypes.number_unpack(step), sgn))
        ins.seek(nextpos)

    def number_inc_gt(self, typechar, loopvar, stop, step, sgn):
        """ Increase number and check if it exceeds a limit. """
        if sgn == 0:
            return False
        if typechar in ('#', '!'):
            fp_left = fp.from_bytes(loopvar).iadd(step)
            loopvar[:] = fp_left.to_bytes()
            return fp_left.gt(stop) if sgn > 0 else stop.gt(fp_left)
        else:
            int_left = vartypes.integer_to_int_signed(vartypes.bytes_to_integer(loopvar)) + step
            loopvar[:] = vartypes.integer_to_bytes(vartypes.int_to_integer_signed(int_left))
            return int_left > stop if sgn > 0 else stop > int_left

    def loop_iterate(self, ins, pos):
        """ Iterate a loop (NEXT). """
        # find the matching NEXT record
        num = len(self.for_stack)
        for depth in range(num):
            forpos, nextpos, typechar, loopvar, stop, step, sgn = self.for_stack[-depth-1]
            if pos == nextpos:
                # only drop NEXT record if we've found a matching one
                self.for_stack = self.for_stack[:len(self.for_stack)-depth]
                break
        else:
            raise error.RunError(error.NEXT_WITHOUT_FOR)
        # increment counter
        loop_ends = self.number_inc_gt(typechar, loopvar, stop, step, sgn)
        if loop_ends:
            self.for_stack.pop()
        else:
            ins.seek(forpos)
        return not loop_ends

    #################################################################
    # DATA utilities

    def restore(self, datanum=-1):
        """ Reset data pointer (RESTORE) """
        try:
            self.data_pos = 0 if datanum == -1 else self.session.program.line_numbers[datanum]
        except KeyError:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)

    def read_entry(self):
        """ READ a unit of DATA. """
        current = self.program_code.tell()
        self.program_code.seek(self.data_pos)
        if util.peek(self.program_code) in tk.end_statement:
            # initialise - find first DATA
            util.skip_to(self.program_code, ('\x84',))  # DATA
        if self.program_code.read(1) not in ('\x84', ','):
            raise error.RunError(error.OUT_OF_DATA)
        vals, word, literal = '', '', False
        while True:
            # read next char; omit leading whitespace
            if not literal and vals == '':
                c = util.skip_white(self.program_code)
            else:
                c = util.peek(self.program_code)
            # parse char
            if c == '' or (not literal and c == ',') or (c in tk.end_line or (not literal and c in tk.end_statement)):
                break
            elif c == '"':
                self.program_code.read(1)
                literal = not literal
                if not literal:
                    util.require(self.program_code, tk.end_statement + (',',))
            else:
                self.program_code.read(1)
                if literal:
                    vals += c
                else:
                    word += c
                # omit trailing whitespace
                if c not in tk.whitespace:
                    vals += word
                    word = ''
        self.data_pos = self.program_code.tell()
        self.program_code.seek(current)
        return vals
