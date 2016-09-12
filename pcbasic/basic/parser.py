"""
PC-BASIC - parser.py
BASIC code parser

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string
import struct

from . import error
from . import tokens as tk
from . import statements
from . import functions
from . import values
from . import expressions
from . import codestream


class Parser(object):
    """Statement parser."""

    def __init__(self, session, syntax, term):
        """Initialise parser."""
        self.session = session
        # value handler
        self.values = self.session.values
        # temporary string context guard
        self.temp_string = self.session.strings
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
        self.init_error_trapping()
        self.error_num = 0
        self.error_pos = 0
        self.statements = statements.Statements(self)
        self.functions = functions.Functions(self)

    def init_error_trapping(self):
        """Initialise error trapping."""
        # True if error handling in progress
        self.error_handle_mode = False
        # statement pointer, run mode of error for RESUME
        self.error_resume = None
        # pointer to error trap
        self.on_error = None

    def parse(self):
        """Parse from the current pointer in current codestream."""
        while True:
            # may raise Break
            self.session.events.check_events()
            try:
                self.handle_basic_events()
                ins = self.get_codestream()
                self.current_statement = ins.tell()
                c = ins.skip_blank_read()
                # parse line number or : at start of statement
                if c in tk.END_LINE:
                    # line number marker, new statement
                    token = ins.read(4)
                    # end of program or truncated file
                    if token[:2] == '\0\0' or len(token) < 4:
                        if self.error_resume:
                            # unfinished error handler: no RESUME (don't trap this)
                            self.error_handle_mode = True
                            # get line number right
                            raise error.RunError(error.NO_RESUME, ins.tell()-len(token)-2)
                        # stream has ended
                        self.set_pointer(False)
                        return
                    if self.tron:
                        linenum = struct.unpack_from('<H', token, 2)
                        self.session.screen.write('[%i]' % linenum)
                    self.session.debugger.debug_step(token)
                elif c != ':':
                    # THEN clause gets us here
                    ins.seek(-len(c), 1)
                self.statements.parse_statement(ins)
            except error.RunError as e:
                self.trap_error(e)

    ###########################################################################
    # clear state

    def clear(self):
        """Clear all to be cleared for CLEAR statement."""
        # clear last error number (ERR) and line number (ERL)
        self.error_num, self.error_pos = 0, 0
        # disable error trapping
        self.init_error_trapping()
        # disable all event trapping (resets PEN to OFF too)
        self.session.events.reset()
        # CLEAR also dumps for_next and while_wend stacks
        self.clear_loop_stacks()
        # reset the DATA pointer
        self.restore()

    def clear_stacks_and_pointers(self):
        """Initialise the stacks and pointers for a new program."""
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
        """Clear loop and jump stacks."""
        self.gosub_stack = []
        self.clear_loop_stacks()

    def clear_loop_stacks(self):
        """Clear loop stacks."""
        self.for_stack = []
        self.while_stack = []

    ###########################################################################
    # event and error handling

    def handle_basic_events(self):
        """Jump to user-defined event subs if events triggered."""
        if self.session.events.suspend_all or not self.run_mode:
            return
        for event in self.session.events.enabled:
            if (event.triggered and not event.stopped and event.gosub is not None):
                # release trigger
                event.triggered = False
                # stop this event while handling it
                event.stopped = True
                # execute 'ON ... GOSUB' subroutine;
                # attach handler to allow un-stopping event on RETURN
                self.jump_gosub(event.gosub, event)

    def trap_error(self, e):
        """Handle a BASIC error through trapping."""
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
            self.session.events.suspend_all = True
        else:
            self.error_handle_mode = False
            self.set_pointer(False)
            raise e

    def erl_(self):
        """ERL: get line number of last error."""
        if self.error_pos == 0:
            return 0
        elif self.error_pos == -1:
            return 65535
        else:
            return self.session.program.get_line_number(self.error_pos)

    def err_(self):
        """ERR: get error code of last error."""
        return self.error_num

    ###########################################################################
    # jumps

    def set_pointer(self, new_runmode, pos=None):
        """Set program pointer to the given codestream and position."""
        self.run_mode = new_runmode
        # events are active in run mode
        self.session.events.set_active(new_runmode)
        # keep the sound engine on to avoid delays in run mode
        self.session.sound.persist(new_runmode)
        # suppress cassette messages in run mode
        self.session.devices.devices['CAS1:'].quiet(new_runmode)
        codestream = self.get_codestream()
        if pos is not None:
            # jump to position, if given
            codestream.seek(pos)
        else:
            # position at end - don't execute anything unless we jump
            codestream.seek(0, 2)

    def get_codestream(self):
        """Get the current codestream."""
        return self.program_code if self.run_mode else self.session.direct_line

    def jump(self, jumpnum, err=error.UNDEFINED_LINE_NUMBER):
        """Execute jump for a GOTO or RUN instruction."""
        if jumpnum is None:
            self.set_pointer(True, 0)
        else:
            try:
                # jump to target
                self.set_pointer(True, self.session.program.line_numbers[jumpnum])
            except KeyError:
                raise error.RunError(err)

    def jump_gosub(self, jumpnum, handler=None):
        """Execute jump for a GOSUB."""
        # set return position
        self.gosub_stack.append((self.get_codestream().tell(), self.run_mode, handler))
        self.jump(jumpnum)

    def jump_return(self, jumpnum):
        """Execute jump for a RETURN."""
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

    ###########################################################################
    # loops

    def loop_init(self, ins, forpos, nextpos, varname, start, stop, step):
        """Initialise a FOR loop."""
        # set start to start-step, then iterate - slower on init but allows for faster iterate
        self.session.scalars.set(varname, start.clone().isub(step))
        # obtain a view of the loop variable
        counter_view = self.session.scalars.view(varname)
        self.for_stack.append(
            (counter_view, stop, step, step.sign(), forpos, nextpos,))
        ins.seek(nextpos)

    def loop_iterate(self, ins, pos):
        """Iterate a loop (NEXT)."""
        # find the matching NEXT record
        num = len(self.for_stack)
        for depth in range(num):
            counter_view, stop, step, sgn, forpos, nextpos = self.for_stack[-depth-1]
            if pos == nextpos:
                # only drop NEXT record if we've found a matching one
                self.for_stack = self.for_stack[:len(self.for_stack)-depth]
                break
        else:
            raise error.RunError(error.NEXT_WITHOUT_FOR)
        # increment counter
        counter_view.iadd(step)
        # check condition
        loop_ends = counter_view.gt(stop) if sgn > 0 else stop.gt(counter_view)
        if loop_ends:
            self.for_stack.pop()
        else:
            ins.seek(forpos)
        return not loop_ends

    ###########################################################################
    # DATA utilities

    def restore(self, datanum=-1):
        """Reset data pointer (RESTORE) """
        try:
            self.data_pos = 0 if datanum == -1 else self.session.program.line_numbers[datanum]
        except KeyError:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)

    def read_entry(self):
        """READ a unit of DATA."""
        current = self.program_code.tell()
        self.program_code.seek(self.data_pos)
        if self.program_code.peek() in tk.END_STATEMENT:
            # initialise - find first DATA
            self.program_code.skip_to((tk.DATA,))
        if self.program_code.read(1) not in (tk.DATA, ','):
            raise error.RunError(error.OUT_OF_DATA)
        self.program_code.skip_blank()
        word = self.program_code.read_to((',', '"',) + tk.END_LINE + tk.END_STATEMENT)
        if self.program_code.peek() == '"':
            if word == '':
                word = self.program_code.read_string().strip('"')
            else:
                word += self.program_code.read_string()
            if (self.program_code.skip_blank() not in (tk.END_STATEMENT + (',',))):
                raise error.RunError(error.STX)
        else:
            word = word.strip(self.program_code.blanks)
        self.data_pos = self.program_code.tell()
        self.program_code.seek(current)
        # omit leading and trailing whitespace
        return word

    ###########################################################################
    # expression parser

    def parse_value(self, ins, sigil=None, allow_empty=False):
        """Read a value of required type and return as Python value, or None if empty."""
        expr = self.parse_expression(ins, allow_empty)
        if expr is not None:
            # this will force into the requested type; e.g. Integers may overflow
            return values.to_type(sigil, expr).to_value()
        return None

    def parse_bracket(self, ins):
        """Compute the value of the bracketed expression."""
        ins.require_read(('(',))
        # we'll get a Syntax error, not a Missing operand, if we close with )
        val = self.parse_expression(ins)
        ins.require_read((')',))
        return val

    def parse_temporary_string(self, ins, allow_empty=False):
        """Parse an expression and return as Python value. Store strings in a temporary."""
        # if allow_empty, a missing value is returned as an empty string
        with self.temp_string:
            expr = self.parse_expression(ins, allow_empty)
            if expr:
                return values.pass_string(expr).to_value()
            return self.values.new_string()

    def parse_file_number(self, ins, opt_hash):
        """Read a file number."""
        if not ins.skip_blank_read_if(('#',)) and not opt_hash:
            return None
        number = values.to_int(self.parse_expression(ins))
        error.range_check(0, 255, number)
        return number


    def parse_scalar(self, ins):
        """Get scalar part of variable name from token stream."""
        name = ins.read_name()
        # must not be empty
        error.throw_if(not name, error.STX)
        # append sigil, if missing
        return self.session.memory.complete_name(name)

    def parse_variable(self, ins):
        """Helper function: parse a scalar or array element."""
        name = ins.read_name()
        error.throw_if(not name, error.STX)
        # this is an evaluation-time determination
        # as we could have passed another DEFtype statement
        name = self.session.memory.complete_name(name)
        indices = expressions.Expression(self.values,
            self.session.memory, self.session.program, self.functions
            ).parse_indices(ins)
        return name, indices



    @staticmethod
    def parse_jumpnum(ins):
        """Parses a line number pointer as in GOTO, GOSUB, LIST, RENUM, EDIT, etc."""
        ins.require_read((tk.T_UINT,))
        token = ins.read(2)
        assert len(token) == 2, 'Bytecode truncated in line number pointer'
        return struct.unpack('<H', token)[0]

    @staticmethod
    def parse_optional_jumpnum(ins):
        """Parses a line number pointer as in GOTO, GOSUB, LIST, RENUM, EDIT, etc."""
        # no line number
        if ins.skip_blank() != tk.T_UINT:
            return -1
        return Parser.parse_jumpnum(ins)

    def parse_expression(self, ins, allow_empty=False):
        """Compute the value of the expression at the current code pointer."""
        if allow_empty and ins.skip_blank() in tk.END_EXPRESSION:
            return None
        expr = expressions.Expression(self.values,
                self.session.memory, self.session.program, self.functions).parse(ins)
        return expr.evaluate()
