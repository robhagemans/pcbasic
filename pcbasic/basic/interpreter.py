"""
PC-BASIC - interpreter.py
BASIC interpreter

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from .base import error
from .base import tokens as tk
from .base.tokens import DIGITS
from .base import codestream
from . import values


class Interpreter(object):
    """BASIC interpreter."""

    def __init__(
            self, queues, console, cursor, files, sound,
            values, memory, program, parser, basic_events
        ):
        """Initialise interpreter."""
        self._queues = queues
        self._basic_events = basic_events
        self._values = values
        self._memory = memory
        self._scalars = memory.scalars
        self._console = console
        self._cursor = cursor
        self._files = files
        self._sound = sound
        # program buffer
        self._program = program
        self._program_code = program.bytecode
        # direct line buffer
        self.direct_line = codestream.TokenisedStream()
        self.current_statement = 0
        # statement syntax parser
        self.parser = parser
        # line number tracing
        self.tron = False
        # pointer position: False for direct line, True for program
        self.run_mode = False
        # clear stacks
        self.clear_stacks_and_pointers()
        self._init_error_trapping()
        self.error_num = 0
        self.error_pos = 0
        self.set_pointer(False, 0)
        # interpreter is waiting for INPUT or LINE INPUT
        self.input_mode = False
        # interpreter is executing a command (needs console)
        self.set_parse_mode(False)
        # additional operations on program step (debugging)
        self.step = lambda token: None

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # functions can't be pickled
        pickle_dict['step'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)
        self.step = lambda token: None

    def _init_error_trapping(self):
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
            # update what basic events need to be handled
            self._queues.set_basic_event_handlers(self._basic_events.enabled)
            # check input and BASIC events. may raise Break, Reset or Exit
            self._queues.check_events()
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
                    if token[:2] == b'\0\0' or len(token) < 4:
                        if c == b'\0' and self.error_resume:
                            # unfinished error handler: no RESUME (don't trap this)
                            self.error_handle_mode = True
                            # get line number right
                            raise error.BASICError(error.NO_RESUME, ins.tell()-len(token)-2)
                        # stream has ended
                        self.set_pointer(False)
                        return
                    if self.tron:
                        linenum = struct.unpack_from('<H', token, 2)
                        self._console.write(b'[%i]' % linenum)
                    self.step(token)
                elif c not in (b':', tk.THEN, tk.ELSE, tk.GOTO):
                    # new statement or branch of an IF statement allowed, nothing else
                    raise error.BASICError(error.STX)
                self.parser.parse_statement(ins)
            except error.BASICError as e:
                self.trap_error(e)

    def loop(self):
        """Run commands until control returns to user."""
        if not self.parse_mode:
            return
        try:
            # parse until break or end
            self.parse()
        except error.Break as e:
            self._sound.stop_all_sound()
            self._handle_break(e)
        # move pointer to the start of direct line (for both on and off!)
        self.set_pointer(False, 0)
        # return control to user
        self.set_parse_mode(False)

    def set_parse_mode(self, on):
        """Enter or exit parse mode."""
        self.parse_mode = on
        self._cursor.set_direct(not on)

    def _handle_break(self, e):
        """Handle a Break event."""
        # print ^C at current position
        if not self.input_mode and not e.stop:
            self._console.write(b'^C')
        # if we're in a program, save pointer
        pos = -1
        if self.run_mode:
            pos = self.current_statement
            if self.parser.redo_on_break:
                self.stop_pos = pos
            else:
                self._program.bytecode.skip_to(tk.END_STATEMENT)
                self.stop_pos = self._program.bytecode.tell()
        self.parser.redo_on_break = False
        if self.error_handle_mode:
            e.trapped_error_num = self.error_num
            # when the error is trapped, error position shifts to start of line
            line = self._program.get_line_number(self.error_pos)
            e.trapped_error_pos = self._program.line_numbers[line]
            #self.error_handle_mode = False
        # ensure we can handle the break like an error
        e.err = 0
        e.pos = pos
        raise e

    ###########################################################################
    # clear state

    def clear(self):
        """Clear all to be cleared for CLEAR statement."""
        # clear last error number (ERR) and line number (ERL)
        self.error_num, self.error_pos = 0, 0
        # disable error trapping
        self._init_error_trapping()
        # disable all event trapping (resets PEN to OFF too)
        self._basic_events.reset()
        # CLEAR also dumps for_next and while_wend stacks
        self.for_stack = []
        self.while_stack = []
        # reset stop/cont
        self.stop_pos = None
        # reset the DATA pointer
        self.data_pos = 0

    def clear_stacks_and_pointers(self):
        """Initialise the stacks and pointers for a new program."""
        # reset loop stacks
        self._clear_stacks()
        # reset program pointer
        self._program_code.seek(0)
        # reset stop/cont
        self.stop_pos = None
        # reset data reader
        self.data_pos = 0

    def _clear_stacks(self):
        """Clear loop and jump stacks."""
        # stop running if we were
        self.set_pointer(False)
        self.gosub_stack = []
        self.for_stack = []
        self.while_stack = []


    ###########################################################################
    # event and error handling

    def handle_basic_events(self):
        """Jump to user-defined event subs if events triggered."""
        if self._basic_events.suspend_all or not self.run_mode:
            return
        for event in self._basic_events.enabled:
            if (event.triggered and not event.stopped and event.gosub is not None):
                # release trigger
                event.triggered = False
                # stop this event while handling it
                event.stopped = True
                # execute 'ON ... GOSUB' subroutine;
                # attach handler to allow un-stopping event on RETURN
                self.jump_sub(event.gosub, event)

    def trap_error(self, e):
        """Handle a BASIC error through trapping."""
        if e.pos is None:
            if self.run_mode:
                e.pos = self._program_code.tell()-1
            else:
                e.pos = -1
        self.error_num = e.err
        self.error_pos = e.pos
        # don't jump if we're already busy handling an error
        if self.on_error is not None and self.on_error != 0 and not self.error_handle_mode:
            self.error_resume = self.current_statement, self.run_mode
            self.jump(self.on_error)
            self.error_handle_mode = True
            self._basic_events.suspend_all = True
        else:
            self.error_handle_mode = False
            self.set_pointer(False)
            raise e

    def erl_(self, args):
        """ERL: get line number of last error."""
        list(args)
        if self.error_pos == 0:
            pos = 0
        elif self.error_pos == -1:
            pos = 65535
        else:
            pos = self._program.get_line_number(self.error_pos)
        return self._values.new_single().from_int(pos)

    def err_(self, args):
        """ERR: get error code of last error."""
        list(args)
        return self._values.new_integer().from_int(self.error_num)

    ###########################################################################
    # jumps

    def set_pointer(self, new_runmode, pos=None):
        """Set program pointer to the given codestream and position."""
        # flush lpt1 on entering interactive mode
        if self.run_mode and not new_runmode:
            self._files.lpt1_file.do_print()
        self.run_mode = new_runmode
        # events are active in run mode
        if new_runmode:
            self._queues.set_basic_event_handlers(self._basic_events.enabled)
        else:
            self._queues.set_basic_event_handlers([])
        # keep the sound engine on to avoid delays in run mode
        self._sound.persist(new_runmode)
        # suppress cassette messages in run mode
        self._files.get_device(b'CAS1:').quiet(new_runmode)
        codestream = self.get_codestream()
        if pos is not None:
            # jump to position, if given
            codestream.seek(pos)
        else:
            # position at end - don't execute anything unless we jump
            codestream.seek(0, 2)

    def get_codestream(self):
        """Get the current codestream."""
        return self._program_code if self.run_mode else self.direct_line

    def jump(self, jumpnum, err=error.UNDEFINED_LINE_NUMBER):
        """Execute jump for a GOTO or RUN instruction."""
        if jumpnum is None:
            self.set_pointer(True, 0)
        else:
            try:
                # jump to target
                self.set_pointer(True, self._program.line_numbers[jumpnum])
            except KeyError:
                raise error.BASICError(err)

    def jump_sub(self, jumpnum, handler=None):
        """Execute jump for a GOSUB."""
        # set return position
        pos = self.get_codestream().tell()
        # record run mode before executing self.jump, as that sets the runmode to True
        run_mode = self.run_mode
        self.jump(jumpnum)
        self.gosub_stack.append((pos, run_mode, handler))

    def goto_(self, args):
        """GOTO: jump to line number."""
        self.jump(*args)

    def gosub_(self, args):
        """GOSUB: jump to subroutine."""
        self.jump_sub(*args)

    def return_(self, args):
        """Execute jump for a RETURN."""
        jumpnum, = args
        try:
            pos, orig_runmode, handler = self.gosub_stack.pop()
        except IndexError:
            raise error.BASICError(error.RETURN_WITHOUT_GOSUB)
        # returning from ON (event) GOSUB, re-enable event
        if handler:
            # if stopped explicitly using STOP, we wouldn't have got here;
            # if STOP is run inside the trap, no effect. OFF in trap: event off.
            handler.stopped = False
        if jumpnum is None:
            # go back to position of GOSUB
            self.set_pointer(orig_runmode, pos)
            # ignore rest of statement ('GOSUB 100 LAH' works just fine..)
            # but NOT if we jumped for an event, as we might have jumped from anywhere!
            if not handler:
                self.get_codestream().skip_to(tk.END_STATEMENT)
        else:
            # jump to specified line number
            self.jump(jumpnum)

    ###########################################################################
    # branches

    def if_(self, args):
        """IF: branching statement."""
        # get condition
        # avoid overflow: don't use bools.
        then_branch = not values.to_single(next(args)).is_zero()
        # cofunction only parses the branch we need
        # cofunction checks for line number
        branch = args.send(then_branch)
        # and completes
        list(args)
        # we may have a line number immediately after THEN or ELSE
        if branch is not None:
            self.jump(branch)
        # note that any :ELSE block encountered will be ignored automatically
        # since standalone ELSE is a no-op to end of line

    def on_jump_(self, args):
        """ON GOTO/GOSUB: calculated jump."""
        onvar = values.to_int(next(args))
        error.range_check(0, 255, onvar)
        jump_type = next(args)
        # only parse jumps (and errors!) up to our choice
        i = -1
        for i, jumpnum in enumerate(args):
            if i == onvar-1:
                # we counted the right number of commas, then didn't find a line number
                if jumpnum is None:
                    raise error.BASICError(error.STX)
                if jump_type == tk.GOTO:
                    self.jump(jumpnum)
                elif jump_type == tk.GOSUB:
                    self.jump_sub(jumpnum)
                return

    ###########################################################################
    # loops

    def for_(self, args):
        """Initialise a FOR loop."""
        # read variable
        varname = self._memory.complete_name(next(args))
        vartype = varname[-1:]
        start = values.to_type(vartype, next(args)).clone()
        # only raised after the TO has been parsed
        if vartype in (values.STR, values.DBL):
            raise error.BASICError(error.TYPE_MISMATCH)
        stop = values.to_type(vartype, next(args)).clone()
        step = next(args)
        if step is not None:
            step = values.to_type(vartype, step).clone()
        list(args)
        if step is None:
            # convert 1 to vartype
            step = self._values.from_value(1, varname[-1:])
        ins = self.get_codestream()
        # find NEXT
        forpos, nextpos = self._find_next(ins, varname)
        # initialise loop variable
        self._scalars.set(varname, start)
        # obtain a view of the loop variable
        self.for_stack.append((varname, stop, step, step.sign(), forpos, nextpos,))
        # empty loop: jump to NEXT without executing block
        if (start.gt(stop) if step.sign() >= 0 else stop.gt(start)):
            ins.seek(nextpos)
            self.iterate_loop()

    def _find_next(self, ins, varname):
        """Helper function for FOR: find matching NEXT."""
        endforpos = ins.tell()
        ins.skip_block(tk.FOR, tk.NEXT, allow_comma=True)
        if ins.skip_blank() not in (tk.NEXT, b','):
            # FOR without NEXT marked with FOR line number
            ins.seek(endforpos)
            raise error.BASICError(error.FOR_WITHOUT_NEXT)
        comma = (ins.read(1) == b',')
        # check var name for NEXT
        # no-var only allowed in standalone NEXT
        if ins.skip_blank() not in tk.END_STATEMENT:
            varname2 = self._memory.complete_name(self.parser.parse_name(ins))
        else:
            varname2 = None
        # get position and line number just after the matching variable in NEXT
        nextpos = ins.tell()
        if (comma or varname2) and varname2 != varname:
            # NEXT without FOR marked with NEXT line number, while we're only at FOR
            raise error.BASICError(error.NEXT_WITHOUT_FOR)
        ins.seek(endforpos)
        return endforpos, nextpos

    def next_(self, args):
        """Iterate a loop (NEXT)."""
        for varname in args:
            # increment counter, check condition
            if self.iterate_loop(varname):
                break

    def iterate_loop(self, varname=None):
        """Iterate a loop (NEXT)."""
        ins = self.get_codestream()
        # record the location after the variable
        pos = ins.tell()
        # find the matching NEXT record
        num = len(self.for_stack)
        for depth in range(num):
            varname2, stop, step, sgn, forpos, nextpos = self.for_stack[-depth-1]
            if pos == nextpos:
                if varname is not None and varname2 != self._memory.complete_name(varname):
                    # check once more for matches
                    # it has been checked at FOR, but DEFtypes may have changed.
                    raise error.BASICError(error.NEXT_WITHOUT_FOR)
                # only drop NEXT record if we've found a matching one
                self.for_stack = self.for_stack[:len(self.for_stack)-depth]
                break
        else:
            raise error.BASICError(error.NEXT_WITHOUT_FOR)
        # increment counter
        counter_view = self._scalars.view(varname2)
        counter_view.iadd(step)
        # check condition
        loop_ends = counter_view.gt(stop) if sgn > 0 else stop.gt(counter_view)
        if loop_ends:
            self.for_stack.pop()
        else:
            ins.seek(forpos)
        return not loop_ends

    def while_(self, args):
        """WHILE: enter while-loop."""
        list(args)
        ins = self.get_codestream()
        # find matching WEND
        whilepos, wendpos = self._find_wend(ins)
        self.while_stack.append((whilepos, wendpos))
        self._check_while_condition(ins, whilepos)

    def _find_wend(self, ins):
        """Helper function for WHILE: find matching WEND."""
        # just after WHILE token
        whilepos = ins.tell()
        ins.skip_block(tk.WHILE, tk.WEND)
        if ins.read(1) != tk.WEND:
            # WHILE without WEND
            ins.seek(whilepos)
            raise error.BASICError(error.WHILE_WITHOUT_WEND)
        ins.skip_to(tk.END_STATEMENT)
        wendpos = ins.tell()
        ins.seek(whilepos)
        return whilepos, wendpos

    def _check_while_condition(self, ins, whilepos):
        """Check condition of while-loop."""
        ins.seek(whilepos)
        # WHILE condition is zero?
        if not values.pass_number(self.parser.parse_expression(ins)).is_zero():
            # statement start is before WHILE token
            self.current_statement = whilepos-2
            ins.require_end()
        else:
            # ignore rest of line and jump to WEND
            _, wendpos = self.while_stack.pop()
            ins.seek(wendpos)

    def wend_(self, args):
        """WEND: iterate while-loop."""
        list(args)
        ins = self.get_codestream()
        pos = ins.tell()
        while True:
            if not self.while_stack:
                # WEND without WHILE
                raise error.BASICError(error.WEND_WITHOUT_WHILE)
            whilepos, wendpos = self.while_stack[-1]
            if pos == wendpos:
                break
            # not the expected WEND, we must have jumped out
            self.while_stack.pop()
        self._check_while_condition(ins, whilepos)

    ###########################################################################
    # DATA utilities

    def restore_(self, args):
        """Reset data pointer (RESTORE) """
        datanum = next(args)
        if datanum is None:
            self.data_pos = 0
        else:
            try:
                self.data_pos = self._program.line_numbers[datanum]
            except KeyError:
                raise error.BASICError(error.UNDEFINED_LINE_NUMBER)
        list(args)

    def read_(self, args):
        """READ: read values from DATA statement."""
        data_error = False
        for name, indices in args:
            name = self._memory.complete_name(name)
            current = self._program_code.tell()
            self._program_code.seek(self.data_pos)
            if self._program_code.peek() in tk.END_STATEMENT:
                # initialise - find first DATA
                self._program_code.skip_to_token(tk.DATA,)
            if self._program_code.read(1) not in (tk.DATA, b','):
                self._program_code.seek(current)
                raise error.BASICError(error.OUT_OF_DATA)
            self._program_code.skip_blank()
            if name[-1:] == values.STR:
                # for unquoted strings, payload starts at the first non-empty character
                address = self._program_code.tell_address()
                word = self._program_code.read_to((b',', b'"',) + tk.END_STATEMENT)
                if self._program_code.peek() == b'"':
                    if word == b'':
                        # nothing before the quotes, so this is a quoted string literal
                        # string payload starts after quote
                        address = self._program_code.tell_address() + 1
                        word = self._program_code.read_string().strip(b'"')
                    else:
                        # complete unquoted string literal
                        word += self._program_code.read_string()
                    if (self._program_code.skip_blank() not in (tk.END_STATEMENT + (b',',))):
                        raise error.BASICError(error.STX)
                else:
                    word = word.strip(self._program_code.blanks)
                value = self._values.from_str_at(word, address)
            else:
                word = self._program_code.read_number()
                value = self._values.from_repr(word, allow_nonnum=False)
                # anything after the number is a syntax error, but assignment has taken place)
                if (self._program_code.skip_blank() not in (tk.END_STATEMENT + (b',',))):
                    data_error = True
            # restore to current program location
            # to ensure any other errors in set_variable get the correct line number
            data_pos = self._program_code.tell()
            self._program_code.seek(current)
            self._memory.set_variable(name, indices, value=value)
            if data_error:
                self._program_code.seek(self.data_pos)
                raise error.BASICError(error.STX)
            else:
                self.data_pos = data_pos

    ###########################################################################
    # COMMON

    def gather_commons(self):
        """Get all COMMON declarations."""
        common_scalars = set()
        common_arrays = set()
        current = self._program_code.tell()
        self._program_code.seek(0)
        while self._program_code.skip_to_token(tk.COMMON):
            self._program_code.read(len(tk.COMMON))
            self._add_common_vars(common_scalars, common_arrays)
        self._program_code.seek(current)
        return common_scalars, common_arrays

    def _parse_common_args(self, ins):
        """Parse COMMON syntax."""
        if ins.skip_blank() in tk.END_STATEMENT:
            return
        while True:
            name = self.parser.parse_name(ins)
            bracket = ins.skip_blank_read_if((b'(', b'['))
            if bracket:
                # a literal is allowed but ignored;
                # for sqare brackets, it's a syntax error if omitted
                if (bracket == b'[') or ins.peek() in set(DIGITS) | set(tk.NUMBER):
                    x = self.parser.expression_parser.read_number_literal(ins)
                ins.require_read((b')', b']'))
            # entries with square brackets are completely ignored!
            if bracket != b'[':
                yield name, bracket
            if not ins.skip_blank_read_if((b',',)):
                break
        ins.require_end()

    def _add_common_vars(self, common_scalars, common_arrays):
        """COMMON: define variables to be preserved on CHAIN."""
        common_vars = list(self._parse_common_args(self._program_code))
        common_scalars.update(
            self._memory.complete_name(name)
            for name, brackets in common_vars if not brackets
        )
        common_arrays.update(
            self._memory.complete_name(name)
            for name, brackets in common_vars if brackets
        )

    ###########################################################################
    # callbacks

    def error_(self, args):
        """ERROR: simulate an error condition."""
        errn, = args
        errn = values.to_int(errn)
        error.range_check(1, 255, errn)
        raise error.BASICError(errn)

    def stop_(self, args):
        """STOP: break program execution and return to interpreter."""
        list(args)
        raise error.Break(stop=True)

    def cont_(self, args):
        """CONT: continue STOPped or ENDed execution."""
        list(args)
        if self.stop_pos is None:
            raise error.BASICError(error.CANT_CONTINUE)
        else:
            self.set_pointer(True, self.stop_pos)
        # IN GW-BASIC, weird things happen if you do GOSUB nn :PRINT "x"
        # and there's a STOP in the subroutine.
        # CONT then continues and the rest of the original line is executed, printing x
        # However, CONT:PRINT triggers a bug
        #  - a syntax error in a nonexistant line number is reported.
        # CONT:PRINT "y" results in neither x nor y being printed.
        # if a command is executed before CONT, x is not printed.
        # It would appear that GW-BASIC only partially overwrites the line buffer and
        # then jumps back to the original return location!
        # in this implementation, the CONT command will fully overwrite the line buffer
        # so x is not printed.

    def tron_(self, args):
        """TRON: trace on."""
        list(args)
        self.tron = True

    def troff_(self, args):
        """TROFF: trace off."""
        list(args)
        self.tron = False

    def on_error_goto_(self, args):
        """ON ERROR GOTO: define error trapping routine."""
        linenum, = args
        if linenum != 0 and linenum not in self._program.line_numbers:
            raise error.BASICError(error.UNDEFINED_LINE_NUMBER)
        self.on_error = linenum
        # pause soft-handling math errors so that we can catch them
        self._values.error_handler.suspend(linenum != 0)
        # ON ERROR GOTO 0 in error handler
        if self.on_error == 0 and self.error_handle_mode:
            # re-raise the error so that execution stops
            raise error.BASICError(self.error_num, self.error_pos)

    def resume_(self, args):
        """RESUME: resume program flow after error-trap."""
        if self.error_resume is None:
            # unset error handler
            self.on_error = 0
            raise error.BASICError(error.RESUME_WITHOUT_ERROR)
        # parse arguments
        where, = args
        start_statement, runmode = self.error_resume
        self.error_num = 0
        self.error_handle_mode = False
        self.error_resume = None
        self._basic_events.suspend_all = False
        if not where:
            # RESUME or RESUME 0
            self.set_pointer(runmode, start_statement)
        elif where == tk.NEXT:
            # RESUME NEXT
            self.set_pointer(runmode, start_statement)
            self.get_codestream().skip_to(tk.END_STATEMENT, break_on_first_char=False)
        else:
            # RESUME n
            self.jump(where)

    def def_fn_(self, args):
        """DEF FN: define a function."""
        fnname, = args
        fnname = self._memory.complete_name(fnname)
        # don't allow DEF FN in direct mode, as we point to the code in the stored program
        # this is raised before further syntax errors
        if not self.run_mode:
            raise error.BASICError(error.ILLEGAL_DIRECT)
        # arguments and expression are being read and parsed by UserFunctionManager
        self.parser.user_functions.define(fnname, self._program_code)

    def llist_(self, args):
        """LLIST: output program lines to LPT1: """
        line_range, = args
        for l in self._program.list_lines(*line_range):
            self._files.lpt1_file.write_line(l)
        # return to direct mode
        self.set_pointer(False)

    def renum_(self, args):
        """RENUM: renumber program line numbers."""
        new, old, step = args
        new, old = self._program.explicit_lines(new, old)
        if step is not None and step < 1:
            raise error.BASICError(error.IFC)
        old_to_new = self._program.renum(self._console, new, old, step)
        # stop running if we were
        # reset loop stacks
        self._clear_stacks()
        # renumber error handler
        if self.on_error:
            self.on_error = old_to_new[self.on_error]
        # renumber event traps
        for handler in self._basic_events.all:
            if handler.gosub:
                handler.set_jump(old_to_new[handler.gosub])
