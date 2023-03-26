"""
PC-BASIC - implementation.py
Top-level implementation and main interpreter loop

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
import io
import os
import sys
import math
import logging
from functools import partial
from contextlib import contextmanager

from ..compat import queue, text_type

from .data import NAME, VERSION, COPYRIGHT
from .base import error
from .base import tokens as tk
from .base import signals
from .base import codestream
from .devices import Files, InputTextFile
from . import converter
from . import eventcycle
from . import basicevents
from . import program
from . import display
from . import console
from . import inputs
from . import clock
from . import dos
from . import memory
from . import machine
from . import interpreter
from . import sound
from . import iostreams
from . import codepage as cp
from . import values
from . import parser
from . import extensions


GREETING = (
    b'KEY ON:PRINT "%s %s":PRINT "%s":PRINT USING "##### Bytes free"; FRE(0)'
    % tuple(s.encode('ascii') for s in (NAME, VERSION, COPYRIGHT))
)


class Implementation(object):
    """Interpreter session, implementation class."""

    def __init__(
            self, syntax=u'advanced', double=False, term=u'', shell=u'',
            output_streams=u'stdio', input_streams=u'stdio',
            codepage=None, box_protect=True, font=None, text_width=80,
            video=u'cga', monitor=u'rgb',
            devices=None, current_device=u'Z:',
            textfile_encoding=None, soft_linefeed=False,
            check_keybuffer_full=True, ctrl_c_is_break=True,
            hide_listing=None, hide_protected=False,
            peek_values=None, allow_code_poke=False, rebuild_offsets=True,
            max_memory=65534, reserved_memory=3429, video_memory=262144,
            serial_buffer_size=128, max_reclen=128, max_files=3,
            extension=()
        ):
        """Initialise the interpreter session."""
        ######################################################################
        # session-level members
        ######################################################################
        # true if a prompt is needed on next cycle
        self._prompt = True
        # AUTO mode state
        self._auto_mode = False
        self._auto_linenum = 10
        self._auto_increment = 10
        # syntax error prompt and EDIT
        self._edit_prompt = False
        # terminal program for TERM command
        self._term_program = term
        ######################################################################
        # data segment
        ######################################################################
        # set up variables and memory model state
        # initialise the data segment
        self.memory = memory.DataSegment(
            max_memory, reserved_memory, max_reclen, max_files, double
        )
        # values and variables
        self.strings = self.memory.strings
        self.values = self.memory.values
        self.scalars = self.memory.scalars
        self.arrays = self.memory.arrays
        # prepare tokeniser
        token_keyword = tk.TokenKeywordDict(syntax)
        self.tokeniser = converter.Tokeniser(self.values, token_keyword)
        self.lister = converter.Lister(self.values, token_keyword)
        # initialise the program
        bytecode = codestream.TokenisedStream(self.memory.code_start)
        self.program = program.Program(
            self.tokeniser, self.lister, hide_listing, hide_protected,
            allow_code_poke, self.memory, bytecode, rebuild_offsets
        )
        # register all data segment users
        self.memory.set_buffers(self.program)
        ######################################################################
        # console
        ######################################################################
        # prepare codepage
        self.codepage = cp.Codepage(codepage, box_protect)
        # set up input event handler
        # no interface yet; use dummy queues
        self.queues = eventcycle.EventQueues(ctrl_c_is_break, inputs=queue.Queue())
        # prepare I/O streams
        self.io_streams = iostreams.IOStreams(self.queues, self.codepage)
        self.io_streams.add_pipes(input=input_streams)
        self.io_streams.add_pipes(output=output_streams)
        # initialise sound queue
        self.sound = sound.Sound(self.queues, self.values, self.memory, syntax)
        # initialise video
        self.display = display.Display(
            self.queues, self.values, self.queues,
            self.memory, text_width, video_memory, video, monitor,
            self.codepage, font
        )
        self.text_screen = self.display.text_screen
        self.graphics = self.display.graphics
        # prepare input devices (keyboard, pen, joystick, clipboard-copier)
        # EventHandler needed for wait() only
        self.keyboard = inputs.Keyboard(
            self.queues, self.values, self.codepage, check_keybuffer_full
        )
        self.pen = inputs.Pen()
        self.stick = inputs.Stick(self.values)
        # 12 definable function keys for Tandy, 10 otherwise
        num_fn_keys = 12 if syntax == 'tandy' else 10
        # initialise the console
        # Sound is needed for the beeps on \a
        self.console = console.Console(
            self.text_screen, self.display.cursor,
            self.keyboard, self.sound, self.io_streams, num_fn_keys
        )
        # initilise floating-point error message stream
        self.values.set_handler(values.FloatErrorHandler(self.console))
        ######################################################################
        # devices
        ######################################################################
        # intialise devices and files
        # DataSegment needed for COMn and disk FIELD buffers
        # EventCycle needed for wait()
        self.files = Files(
            self.values, self.memory, self.queues, self.keyboard, self.display, self.console,
            max_files, max_reclen, serial_buffer_size,
            devices, current_device,
            self.codepage, textfile_encoding, soft_linefeed
        )
        # enable printer echo from console
        self.console.set_lpt1_file(self.files.lpt1_file)
        ######################################################################
        # other components
        ######################################################################
        # set up the SHELL command
        # Files needed for current disk device
        self.shell = dos.Shell(
            self.queues, self.keyboard, self.console, self.files, self.codepage, shell
        )
        # set up environment
        self.environment = dos.Environment(self.values, self.codepage)
        # initialise random number generator
        self.randomiser = values.Randomiser(self.values)
        # initialise system clock
        self.clock = clock.Clock(self.values)
        ######################################################################
        # register input event handlers
        ######################################################################
        # clipboard and print screen handler
        self.queues.add_handler(display.ScreenCopyHandler(
            self.queues, self.text_screen, self.files.lpt1_file
        ))
        # keyboard, pen and stick
        self.queues.add_handler(self.keyboard)
        self.queues.add_handler(self.pen)
        self.queues.add_handler(self.stick)
        # set up BASIC event handlers
        self.basic_events = basicevents.BasicEvents(
            self.sound, self.clock, self.files, self.program, num_fn_keys
        )
        ######################################################################
        # extensions
        ######################################################################
        self.extensions = extensions.Extensions(extension, self.values, self.codepage)
        ######################################################################
        # interpreter
        ######################################################################
        # initialise the parser
        self.parser = parser.Parser(self.values, self.memory, syntax)
        # initialise the interpreter
        self.interpreter = interpreter.Interpreter(
            self.queues, self.console, self.display.cursor, self.files, self.sound,
            self.values, self.memory, self.program, self.parser, self.basic_events
        )
        ######################################################################
        # callbacks
        ######################################################################
        # set up non-data segment memory
        self.all_memory = machine.Memory(
            self.values, self.memory, self.files,
            self.display, self.keyboard, self.display.memory_font,
            self.interpreter, peek_values, syntax
        )
        # initialise machine ports
        self.machine = machine.MachinePorts(
            self.queues, self.values, self.display, self.keyboard, self.stick, self.files
        )
        # build function table (depends on Memory having been initialised)
        self.parser.init_callbacks(self)

    def __getstate__(self):
        """Pickle the session."""
        return self.__dict__

    def __setstate__(self, pickle_dict):
        """Unpickle and resume the session."""
        self.__dict__.update(pickle_dict)
        # re-assign callbacks (not picklable)
        self.parser.init_callbacks(self)
        # reopen keyboard, in case we quit because it was closed
        self.keyboard._input_closed = False
        # suppress double prompt
        if not self.interpreter.parse_mode:
            self._prompt = False

    def attach_interface(self, interface=None):
        """Attach interface to interpreter session."""
        if interface:
            self.queues.set(*interface.get_queues())
            # rebuild the screen
            self.display.rebuild()
            # rebuild audio queues
            self.sound.rebuild()
        else:
            # use dummy video & audio queues if not provided
            # but an input queue should be operational for I/O streams
            self.queues.set(inputs=queue.Queue())

    def execute(self, command):
        """Execute a BASIC statement."""
        with self._handle_exceptions():
            self._store_line(command)
            self.interpreter.loop()

    def evaluate(self, expression):
        """Evaluate a BASIC expression."""
        with self._handle_exceptions():
            # prefix expression with a PRINT token
            # to avoid any number at the start to be taken as a line number
            tokens = self.tokeniser.tokenise_line(b'?' + expression)
            # skip : and ? tokens and parse expression
            tokens.read(2)
            val =  self.parser.parse_expression(tokens)
            return val.to_value()
        return None

    def set_variable(self, name, value):
        """Set a variable in memory."""
        name = name.upper()
        if isinstance(value, text_type):
            value = self.codepage.unicode_to_bytes(value)
        elif isinstance(value, bool):
            value = -1 if value else 0
        if b'(' in name:
            name = name.split(b'(', 1)[0]
            self.arrays.from_list(value, name)
        else:
            self.memory.set_variable(name, [], self.values.from_value(value, name[-1:]))

    def get_converter(self, from_type, to_type):
        """Get a converter function; raise ValueError if not allowed"""
        if to_type is None or from_type == to_type:
            return lambda _x: _x
        converter = {
            (bytes, text_type): partial(self.codepage.bytes_to_unicode, preserve=cp.CONTROL),
            (text_type, bytes): self.codepage.unicode_to_bytes,
            (int, bool): bool,
            (float, bool): bool,
            (bool, int): lambda _bool: (-1 if _bool else 0),
            (int, float): float,
            (float, int): lambda _flt: int(math.floor(_flt)),
            (bool, float): lambda _bool: (-1. if _bool else 0.),
        }
        try:
            return converter[(from_type, to_type)]
        except KeyError:
            raise ValueError("BASIC can't convert %s to %s." % (from_type, to_type))

    def get_variable(self, name, as_type=None):
        """Get a variable in memory."""
        name = name.upper()
        if b'(' in name:
            name = name.split(b'(', 1)[0]
            value = self.arrays.to_list(name)
            if not value:
                return []
            convert = self.get_converter(type(value[0]), as_type)
            return [convert(_item) for _item in value]
        else:
            value = self.memory.view_or_create_variable(name, []).to_value()
            convert = self.get_converter(type(value), as_type)
            return convert(value)

    def interact(self):
        """Interactive interpreter session."""
        while True:
            with self._handle_exceptions():
                self.interpreter.loop()
                if self._auto_mode:
                    self._auto_step()
                else:
                    self._show_prompt()
                    # input loop, checks events
                    line = self.console.read_line(is_input=False)
                    self._prompt = not self._store_line(line)

    def close(self):
        """Close the session."""
        # close files if we opened any
        self.files.close_all()
        self.files.close_devices()
        # kill the iostreams threads so windows doesn't run out
        self.io_streams.close()

    def _show_prompt(self):
        """Show the Ok or EDIT prompt, unless suppressed."""
        if self._prompt:
            self.console.start_line()
            self.console.write_line(b'Ok\xff')
        if self._edit_prompt:
            linenum, tell = self._edit_prompt
            # unset edit prompt first, in case program.edit throws
            self._edit_prompt = False
            self.program.edit(self.console, linenum, tell)

    def _store_line(self, line):
        """Store a program line or schedule a command line for execution."""
        if not line:
            return True
        self.interpreter.direct_line = self.tokeniser.tokenise_line(line)
        c = self.interpreter.direct_line.peek()
        if c == b'\0':
            # clear all program stacks
            self.interpreter.clear_stacks_and_pointers()
            # clear variables first,
            # to avoid inconsistent state in string space if out of memory
            self._clear_all()
            # check for lines starting with numbers (6553 6) and empty lines
            self.program.check_number_start(self.interpreter.direct_line)
            self.program.store_line(self.interpreter.direct_line)
            return True
        elif c != b'':
            self.interpreter.run_mode = False
            # it is a command, go and execute
            self.interpreter.set_parse_mode(True)
            return False

    def _auto_step(self):
        """Generate an AUTO line number and wait for input."""
        try:
            numstr = b'%d' % (self._auto_linenum,)
            if self._auto_linenum in self.program.line_numbers:
                prompt = numstr + b'*'
            else:
                prompt = numstr + b' '
            line = self.console.read_line(prompt, is_input=False)
            # remove *, if present
            if line[:len(numstr)+1] == b'%s*' % (numstr,):
                line = b'%s %s' % (numstr, line[len(numstr)+1:])
            # run or store it; don't clear lines or raise undefined line number
            self.interpreter.direct_line = self.tokeniser.tokenise_line(line)
            c = self.interpreter.direct_line.peek()
            if c == b'\0':
                # check for lines starting with numbers (6553 6) and empty lines
                empty, scanline = self.program.check_number_start(self.interpreter.direct_line)
                if not empty:
                    self.program.store_line(self.interpreter.direct_line)
                    # clear all program stacks
                    self.interpreter.clear_stacks_and_pointers()
                    self._clear_all()
                self._auto_linenum = scanline + self._auto_increment
            elif c != b'':
                # it is a command, go and execute
                self.interpreter.set_parse_mode(True)
        except error.Break:
            # ctrl+break, ctrl-c both stop background sound
            self.sound.stop_all_sound()
            self._auto_mode = False


    ##############################################################################
    # error handling

    @contextmanager
    def _handle_exceptions(self):
        """Context guard to handle BASIC exceptions."""
        try:
            yield
        except error.Break as e:
            # ctrl-break stops foreground and background sound
            self.sound.stop_all_sound()
            if not self.interpreter.parse_mode:
                self._prompt = False
            else:
                self.interpreter.set_pointer(False)
                # call _handle_error to write a message, etc.
                self._handle_error(e)
                # override position of syntax error
                if e.trapped_error_num == error.STX:
                    self._syntax_error_edit_prompt(e.trapped_error_pos)
        except error.BASICError as e:
            self._handle_error(e)
        except error.Exit:
            raise

    def _handle_error(self, e):
        """Handle a BASIC error through error message."""
        # not handled by ON ERROR, stop execution
        self.console.start_line()
        self.console.write(e.get_message(self.program.get_line_number(e.pos)))
        if not self.interpreter.input_mode:
            self.console.write(b'\xFF')
        self.console.write(b'\r')
        self.interpreter.set_parse_mode(False)
        self.interpreter.input_mode = False
        self._prompt = True
        # special case: syntax error
        if e.err == error.STX:
            self._syntax_error_edit_prompt(e.pos)

    def _syntax_error_edit_prompt(self, pos):
        """Show an EDIT prompt at the location of a syntax error."""
        # for some reason, err is reset to zero by GW-BASIC in this case.
        self.interpreter.error_num = 0
        if pos is not None and pos != -1:
            # line edit gadget appears
            self._edit_prompt = (self.program.get_line_number(pos), pos+1)

    ###########################################################################
    # callbacks

    def system_(self, args):
        """SYSTEM: exit interpreter."""
        list(args)
        raise error.Exit()

    def clear_(self, args):
        """CLEAR: clear memory and redefine memory limits."""
        try:
            # positive integer expression allowed but not used
            intexp = next(args)
            if intexp is not None:
                expr = values.to_int(intexp)
                error.throw_if(expr < 0)
            # set size of BASIC memory
            mem_size = next(args)
            if mem_size is not None:
                mem_size = values.to_int(mem_size, unsigned=True)
                self.memory.set_basic_memory_size(mem_size)
            # set aside stack space for GW-BASIC.
            # default is the previous stack space size.
            stack_size = next(args)
            if stack_size is not None:
                stack_size = values.to_int(stack_size, unsigned=True)
                self.memory.set_stack_size(stack_size)
            # select video memory size (Tandy/PCjr only)
            video_size = next(args)
            if video_size is not None:
                video_size = round(video_size.to_value())
                self.display.set_video_memory_size(video_size)
            # execute any remaining parsing steps
            next(args)
        except StopIteration:
            pass
        self._clear_all()

    def _clear_all(self, close_files=False,
              preserve_functions=False, preserve_base=False, preserve_deftype=False):
        """Clear everything required for the CLEAR command."""
        if close_files:
            # close all files
            self.files.close_all()
        # Resets the stack and string space
        # Clears all COMMON and user variables
        # release all disk buffers (FIELD)?
        self.memory.clear(preserve_base, preserve_deftype)
        if not preserve_functions:
            self.parser.user_functions.clear()
        # Resets STRIG to off
        self.stick.is_on = False
        # stop all sound
        self.sound.stop_all_sound()
        # reset PLAY state
        self.sound.reset_play()
        # reset DRAW state (angle, scale) and current graphics position
        self.graphics.reset()
        # reset random number generator
        self.randomiser.clear()
        # reset stacks & pointers
        self.interpreter.clear()

    def shell_(self, args):
        """SHELL: open OS shell and optionally execute command."""
        cmd = values.next_string(args)
        list(args)
        # force cursor visible
        self.display.cursor.set_override(True)
        # sound stops playing and is forgotten
        self.sound.stop_all_sound()
        # run the os-specific shell
        self.shell.launch(cmd)
        # reset cursor visibility to its previous state
        self.display.cursor.set_override(False)

    def term_(self, args):
        """TERM: terminal emulator."""
        list(args)
        self._clear_all()
        self.interpreter.tron = False
        if not self._term_program:
            # on Tandy, raises Internal Error
            # and deletes the program currently in memory
            raise error.BASICError(error.INTERNAL_ERROR)
        # terminal program for TERM command
        prog = self.files.get_device(b'@:').bind(self._term_program)
        with self.files.open(0, prog, filetype=b'ABP', mode=b'I') as progfile:
            self.program.load(progfile)
        self.interpreter.error_handle_mode = False
        self.interpreter.clear_stacks_and_pointers()
        self.interpreter.set_pointer(True, 0)

    def delete_(self, args):
        """DELETE: delete range of lines from program."""
        line_range, = args
        # throws back to direct mode
        self.program.delete(*line_range)
        # clear all program stacks
        self.interpreter.clear_stacks_and_pointers()
        # clear all variables
        self._clear_all()

    def list_(self, args):
        """LIST: output program lines."""
        line_range = next(args)
        out = values.next_string(args)
        if out is not None:
            out = self.files.open(0, out, filetype=b'A', mode=b'O')
        list(args)
        lines = self.program.list_lines(*line_range)
        if out:
            with out:
                for l in lines:
                    out.write_line(l)
        else:
            for l in lines:
                # flow of listing is visible on screen
                # and interruptible
                self.queues.wait()
                # LIST on screen is slightly different from just writing
                self.console.list_line(l, newline=True)
        # return to direct mode
        self.interpreter.set_pointer(False)

    def edit_(self, args):
        """EDIT: output a program line and position cursor for editing."""
        from_line, = args
        from_line, = self.program.explicit_lines(from_line)
        self.program.last_stored = from_line
        if from_line is None or from_line not in self.program.line_numbers:
            raise error.BASICError(error.UNDEFINED_LINE_NUMBER)
        # throws back to direct mode
        # jump to end of direct line so execution stops
        self.interpreter.set_pointer(False)
        # request edit prompt but no Ok prompt
        self._prompt = False
        self._edit_prompt = (from_line, None)

    def auto_(self, args):
        """AUTO: enter automatic line numbering mode."""
        linenum, increment = args
        from_line, = self.program.explicit_lines(linenum)
        # reset linenum and increment on each call of AUTO (even in AUTO mode)
        self._auto_linenum = linenum if linenum is not None else 10
        self._auto_increment = increment if increment is not None else 10
        # move program pointer to end
        self.interpreter.set_pointer(False)
        # continue input in AUTO mode
        self._auto_mode = True

    def load_(self, args):
        """LOAD: load program from file."""
        name = values.next_string(args)
        comma_r, = args
        # clear variables, stacks & pointers
        self._clear_all()
        with self.files.open(0, name, filetype=b'ABP', mode=b'I') as f:
            self.program.load(f)
        # reset stacks
        self.interpreter.clear_stacks_and_pointers()
        if comma_r:
            # in ,R mode, don't close files; run the program
            self.interpreter.set_pointer(True, 0)
        else:
            self.files.close_all()
        self.interpreter.tron = False

    def chain_(self, args):
        """CHAIN: load program and chain execution."""
        merge = next(args)
        name = values.next_string(args)
        jumpnum = next(args)
        if jumpnum is not None:
            jumpnum = values.to_int(jumpnum, unsigned=True)
        preserve_all, delete_lines = next(args), next(args)
        from_line, to_line = delete_lines if delete_lines else (None, None)
        if to_line is not None and to_line not in self.program.line_numbers:
            raise error.BASICError(error.IFC)
        list(args)
        if self.program.protected and merge:
            raise error.BASICError(error.IFC)
        # gather COMMON declarations
        common_scalars, common_arrays = self.interpreter.gather_commons()
        with self.memory.preserve_commons(common_scalars, common_arrays, preserve_all):
            # preserve DEFtype on MERGE
            # functions are cleared except when CHAIN ... ALL is specified
            # OPTION BASE is preserved when there are common variables
            self._clear_all(
                    preserve_functions=preserve_all,
                    preserve_base=(common_scalars or common_arrays or preserve_all),
                    preserve_deftype=merge)
            # load new program
            with self.files.open(0, name, filetype=b'ABP', mode=b'I') as f:
                if delete_lines:
                    # delete lines from existing code before merge
                    # (without MERGE, this is pointless)
                    self.program.delete(*delete_lines)
                if merge:
                    self.program.merge(f)
                else:
                    self.program.load(f)
                # clear all program stacks
                self.interpreter.clear_stacks_and_pointers()
                # don't close files!
                # RUN
                self.interpreter.jump(jumpnum, err=error.IFC)
        # ensure newly allocated strings are not considered temporary
        # e.g. code strings in the old program become allocated strings in the new
        self.strings.fix_temporaries()

    def save_(self, args):
        """SAVE: save program to a file."""
        name = values.next_string(args)
        mode = (next(args) or b'B').upper()
        list(args)
        with self.files.open(
                0, name, filetype=mode, mode=b'O',
                seg=self.memory.data_segment, offset=self.memory.code_start,
                length=len(self.program.bytecode.getvalue())-1
            ) as f:
            self.program.save(f)
        if mode == b'A':
            # return to direct mode
            self.interpreter.set_pointer(False)

    def merge_(self, args):
        """MERGE: merge lines from file into current program."""
        name = values.next_string(args)
        list(args)
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        with self.files.open(0, name, filetype=b'A', mode=b'I') as f:
            self.program.merge(f)
        # clear all program stacks
        self.interpreter.clear_stacks_and_pointers()

    def new_(self, args):
        """NEW: clear program from memory."""
        list(args)
        self.interpreter.tron = False
        # deletes the program currently in memory
        self.program.erase()
        # reset stacks
        self.interpreter.clear_stacks_and_pointers()
        # and clears all variables
        self._clear_all()
        self.interpreter.set_pointer(False)

    def run_(self, args):
        """RUN: start program execution."""
        jumpnum = next(args)
        comma_r = False
        if jumpnum is None:
            try:
                name = values.next_string(args)
                comma_r = next(args)
                with self.files.open(0, name, filetype=b'ABP', mode=b'I') as f:
                    self.program.load(f)
            except StopIteration:
                pass
        list(args)
        self.interpreter.on_error = 0
        self.interpreter.error_handle_mode = False
        self.interpreter.clear_stacks_and_pointers()
        self._clear_all(close_files=not comma_r)
        if jumpnum is None:
            self.interpreter.set_pointer(True, 0)
        else:
            if jumpnum not in self.program.line_numbers:
                raise error.BASICError(error.UNDEFINED_LINE_NUMBER)
            self.interpreter.jump(jumpnum)

    def end_(self, args):
        """END: end program execution and return to interpreter."""
        list(args)
        # enable CONT
        self.program.bytecode.skip_to(tk.END_STATEMENT)
        self.interpreter.stop_pos = self.program.bytecode.tell()
        # jump to end of direct line so execution stops
        self.interpreter.set_pointer(False)
        # avoid NO RESUME
        self.interpreter.error_handle_mode = False
        self.interpreter.error_resume = None
        self.files.close_all()

    def input_(self, args):
        """INPUT: request input from user or read from file."""
        file_number = next(args)
        if file_number is not None:
            file_number = values.to_int(file_number)
            error.range_check(0, 255, file_number)
            finp = self.files.get(file_number, mode=b'IR')
            self._input_file(finp, args)
        else:
            newline, prompt, following = next(args)
            self._input_console(newline, prompt, following, args)

    def _input_console(self, newline, prompt, following, readvar):
        """INPUT: request input from user."""
        if following == b';':
            prompt += b'? '
        with self.memory.get_stack() as stack:
            # read the input
            self.interpreter.input_mode = True
            self.parser.redo_on_break = True
            # readvar is a list of (name, indices) tuples
            # we return a list of (name, indices, values) tuples
            while True:
                line = self.console.read_line(prompt, write_endl=newline, is_input=True)
                inputstream = InputTextFile(line)
                # read the values and group them and the separators
                var, values, seps = [], [], []
                for name, indices in readvar:
                    name = self.memory.complete_name(name)
                    word, sep = inputstream.input_entry(
                        name[-1:], allow_past_end=True, suppress_unquoted_linefeed=False
                    )
                    try:
                        value = self.values.from_repr(word, allow_nonnum=False, typechar=name[-1:])
                    except error.BASICError as e:
                        # string entered into numeric field
                        value = None
                    stack.append(value)
                    var.append([name, indices])
                    values.append(value)
                    seps.append(sep)
                # last separator not empty: there were too many values or commas
                # earlier separators empty: there were too few values
                # empty values will be converted to zero by from_str
                # None means a conversion error occurred
                if (seps[-1] or b'' in seps[:-1] or None in values):
                    # good old Redo!
                    self.console.write_line(b'?Redo from start')
                    readvar = var
                else:
                    varlist = [r + [v] for r, v in zip(var, values)]
                    break
            self.parser.redo_on_break = False
            self.interpreter.input_mode = False
            for v in varlist:
                self.memory.set_variable(*v)

    def _input_file(self, finp, readvar):
        """INPUT: retrieve input from file."""
        for v in readvar:
            name, indices = v
            typechar = self.memory.complete_name(name)[-1:]
            word, _ = finp.input_entry(typechar, allow_past_end=False)
            value = self.values.from_repr(word, allow_nonnum=True, typechar=typechar)
            self.memory.set_variable(name, indices, value)

    def line_input_(self, args):
        """LINE INPUT: request line of input from user."""
        file_number = next(args)
        if file_number is None:
            # get prompt
            newline, prompt, _ = next(args)
            finp = None
        else:
            prompt, newline = None, None
            file_number = values.to_int(file_number)
            error.range_check(0, 255, file_number)
            finp = self.files.get(file_number, mode=b'IR')
        # get string variable
        readvar, indices = next(args)
        list(args)
        readvar = self.memory.complete_name(readvar)
        if readvar[-1:] != values.STR:
            raise error.BASICError(error.TYPE_MISMATCH)
        # read the input
        if finp:
            line, cr = finp.read_line()
            if not line and not cr:
                raise error.BASICError(error.INPUT_PAST_END)
        else:
            self.interpreter.input_mode = True
            self.parser.redo_on_break = True
            line = self.console.read_line(prompt, write_endl=newline, is_input=True)
            self.parser.redo_on_break = False
            self.interpreter.input_mode = False
        self.memory.set_variable(readvar, indices, self.values.from_value(line, values.STR))

    def randomize_(self, args):
        """RANDOMIZE: set random number generator seed."""
        val, = args
        if val is not None:
            # don't convert to int if provided in the code
            val = values.pass_number(val, err=error.IFC)
        else:
            # prompt for random seed if not specified
            while True:
                seed = self.console.read_line(
                    b'Random number seed (-32768 to 32767)? ', is_input=True
                )
                try:
                    val = self.values.from_repr(seed, allow_nonnum=False)
                except error.BASICError as e:
                    if e.err != error.IFC:
                        raise
                else:
                    break
            # seed entered on prompt is rounded to int
            val = values.to_integer(val)
        self.randomiser.reseed(val)

    def key_(self, args):
        """KEY: macro or event trigger definition."""
        keynum = values.to_int(next(args))
        error.range_check(1, 255, keynum)
        text = values.next_string(args)
        list(args)
        try:
            self.console.set_macro(keynum, text)
        except ValueError:
            pass
        # if out of range of number of macros (12 on Tandy, else 10), it's a trigger definition
        try:
            self.basic_events.key[keynum-1].set_trigger(text)
        except IndexError:
            # out of range key value
            raise error.BASICError(error.IFC)

    def pen_fn_(self, args):
        """PEN: poll the light pen."""
        fn, = args
        result = self.pen.poll(fn, self.basic_events.pen in self.basic_events.enabled, self.display.apage)
        return self.values.new_integer().from_int(result)
