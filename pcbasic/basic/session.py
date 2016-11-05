"""
PC-BASIC - session.py
Session class and main interpreter loop

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
import os
import sys
import logging
import platform
import io
import Queue
from contextlib import contextmanager

from . import error
from . import tokens as tk
from . import tokeniser
from . import lister
from . import codestream
from . import events
from . import program
from . import signals
from . import display
from . import editor
from . import inputmethods
from . import debug
from . import clock
from . import dos
from . import memory
from . import machine
from . import interpreter
from . import files
from . import sound
from . import redirect
from . import codepage as cp
from . import values
from . import parser
from . import devices


class Session(object):
    """Interpreter session."""

    ###########################################################################
    # public interface methods

    def __init__(self, iface=None,
            syntax=u'advanced', option_debug=False, pcjr_term=u'', option_shell=u'',
            output_file=None, append=False, input_file=None,
            codepage=u'437', box_protect=True,
            video_capabilities=u'vga', font=u'freedos',
            monitor=u'rgb', mono_tint=(0, 255, 0), screen_aspect=(4, 3),
            text_width=80, video_memory=262144, cga_low=False,
            keystring=u'', double=False,
            peek_values=None, device_params=None,
            current_device='Z', mount_dict=None,
            print_trigger='close', serial_buffer_size=128,
            utf8=False, universal=True, stdio=False,
            ignore_caps=True, ctrl_c_is_break=True,
            max_list_line=65535, allow_protect=False,
            allow_code_poke=False, max_memory=65534,
            max_reclen=128, max_files=3, reserved_memory=3429,
            temp_dir=u''):
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
        self._term_program = pcjr_term
        ######################################################################
        # data segment
        ######################################################################
        # set up variables and memory model state
        # initialise the data segment
        self.memory = memory.DataSegment(
                    max_memory, reserved_memory, max_reclen, max_files, double)
        # values and variables
        self.strings = self.memory.strings
        self.values = self.memory.values
        self.scalars = self.memory.scalars
        self.arrays = self.memory.arrays
        # prepare tokeniser
        token_keyword = tk.TokenKeywordDict(syntax)
        self.tokeniser = tokeniser.Tokeniser(self.values, token_keyword)
        self.lister = lister.Lister(self.values, token_keyword)
        # initialise the program
        bytecode = codestream.TokenisedStream(self.memory.code_start)
        self.program = program.Program(
                self.tokeniser, self.lister, max_list_line, allow_protect,
                allow_code_poke, self.memory.code_start, bytecode)
        # register all data segment users
        self.memory.set_buffers(self.program)
        ######################################################################
        # console
        ######################################################################
        if iface:
            # connect to interface queues
            self.queues = signals.InterfaceQueues(*iface.get_queues())
        else:
            # no interface; use dummy queues
            self.queues = signals.InterfaceQueues(inputs=Queue.Queue())
        # prepare codepage
        self.codepage = cp.Codepage(codepage, box_protect)
        # prepare I/O redirection
        self.input_redirection, self.output_redirection = redirect.get_redirection(
                self.codepage, stdio, input_file, output_file, append, self.queues.inputs)
        # prepare input methods
        self.input_methods = inputmethods.InputMethods(self.queues, self.values)
        # initialise sound queue
        self.sound = sound.Sound(self.queues, self.values, self.input_methods, syntax)
        # Sound is needed for the beeps on \a
        self.screen = display.Screen(
                self.queues, self.values, self.input_methods, self.memory,
                text_width, video_memory, video_capabilities, monitor,
                self.sound, self.output_redirection,
                cga_low, mono_tint, screen_aspect,
                self.codepage, font, warn_fonts=option_debug)
        # initialise input methods
        # screen is needed for print_screen, clipboard copy and pen poll
        self.input_methods.init(self.screen, self.codepage, keystring, ignore_caps, ctrl_c_is_break)
        # initilise floating-point error message stream
        self.values.set_screen(self.screen)
        ######################################################################
        # devices
        ######################################################################
        # intialise devices and files
        # DataSegment needed for COMn and disk FIELD buffers
        # InputMethods needed for wait()
        self.devices = files.Devices(
                self.values, self.memory, self.input_methods, self.memory.fields,
                self.screen, self.input_methods.keyboard,
                device_params, current_device, mount_dict,
                print_trigger, temp_dir, serial_buffer_size,
                utf8, universal)
        self.files = files.Files(self.values, self.devices, self.memory, max_files, max_reclen)
        # set LPT1 as target for print_screen()
        self.screen.set_print_screen_target(self.devices.lpt1_file)
        # set up the SHELL command
        self.shell = dos.get_shell_manager(self.input_methods.keyboard, self.screen, self.codepage, option_shell, syntax)
        # set up environment
        self.environment = dos.Environment(self.values, self.strings)
        # initialise random number generator
        self.randomiser = values.Randomiser(self.values)
        # initialise system clock
        self.clock = clock.Clock(self.memory, self.values)
        ######################################################################
        # editor
        ######################################################################
        # initialise the editor
        self.editor = editor.Editor(
                self.screen, self.input_methods.keyboard, self.sound,
                self.output_redirection, self.devices.lpt1_file)
        ######################################################################
        # interpreter
        ######################################################################
        # initialise the parser
        self.parser = parser.Parser(self.values, self.memory, syntax)
        # set up debugger
        self.debugger = debug.get_debugger(self, option_debug)
        # set up BASIC event handlers
        self.basic_events = events.BasicEvents(
                self.values, self.input_methods, self.sound, self.clock,
                self.devices, self.screen, self.program, syntax)
        # initialise the interpreter
        self.interpreter = interpreter.Interpreter(
                self.debugger, self.input_methods, self.screen, self.devices, self.sound,
                self.values, self.memory, self.scalars, self.program, self.parser, self.basic_events)
        # PLAY parser
        self.play_parser = sound.PlayParser(self.sound, self.memory, self.values)
        ######################################################################
        # callbacks
        ######################################################################
        # set up non-data segment memory
        self.all_memory = machine.Memory(
                self.values, self.memory, self.devices, self.files,
                self.screen, self.input_methods.keyboard, self.screen.fonts[8],
                self.interpreter, peek_values, syntax)
        # initialise machine ports
        self.machine = machine.MachinePorts(self)
        # build function table (depends on Memory having been initialised)
        self.parser.init_callbacks(self)

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, dummy_1, dummy_2, dummy_3):
        """Context guard."""
        self.close()

    def __getstate__(self):
        """Pickle the session."""
        pickle_dict = self.__dict__.copy()
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle and resume the session."""
        self.__dict__.update(pickle_dict)
        # re-assign callbacks (not picklable)
        self.parser.init_callbacks(self)
        # reopen keyboard, in case we quit because it was closed
        self.input_methods.keyboard._input_closed = False
        # suppress double prompt
        if not self.interpreter._parse_mode:
            self._prompt = False

    def attach(self, iface=None):
        """Attach interface to interpreter session."""
        if iface:
            self.queues.set()
            # rebuild the screen
            self.screen.rebuild()
            # rebuild audio queues
            self.sound.rebuild()
        else:
            # use dummy video & audio queues if not provided
            # but an input queue shouls be operational for redirects
            self.queues.set(inputs=Queue.Queue())
        # attach input queue to redirects
        self.input_redirection.attach(self.queues.inputs)
        return self

    def load_program(self, prog, rebuild_dict=True):
        """Load a program from native or BASIC file."""
        with self._handle_exceptions():
            with self.files.open_native_or_basic(
                        prog, filetype='ABP',
                        mode='I') as progfile:
                self.program.load(progfile, rebuild_dict=rebuild_dict)

    def save_program(self, prog, filetype):
        """Save a program to native or BASIC file."""
        with self._handle_exceptions():
            with self.files.open_native_or_basic(
                        prog, filetype=filetype,
                        mode='O') as progfile:
                self.program.save(progfile)

    def execute(self, command):
        """Execute a BASIC statement."""
        for cmd in command.splitlines():
            if isinstance(cmd, unicode):
                cmd = self.codepage.str_from_unicode(cmd)
            with self._handle_exceptions():
                self._store_line(cmd)
                self.interpreter.loop()

    def evaluate(self, expression):
        """Evaluate a BASIC expression."""
        if isinstance(expression, unicode):
            expression = self.codepage.str_from_unicode(expression)
        with self._handle_exceptions():
            # attach print token so tokeniser has a whole statement to work with
            tokens = self.tokeniser.tokenise_line(b'?' + expression)
            # skip : and print token and parse expression
            tokens.read(2)
            return self.parser.parse_expression(tokens).to_value()
        return None

    def set_variable(self, name, value):
        """Set a variable in memory."""
        if isinstance(name, unicode):
            name = name.encode('ascii')
        if isinstance(value, unicode):
            value = self.codepage.str_from_unicode(value)
        if '(' in name:
            name = name.split('(', 1)[0]
            self.arrays.from_list(value, name)
        else:
            self.memory.set_variable(name, [], self.values.from_value(value, name[-1]))

    def get_variable(self, name):
        """Get a variable in memory."""
        if isinstance(name, unicode):
            name = name.encode('ascii')
        if '(' in name:
            name = name.split('(', 1)[0]
            return self.arrays.to_list(name)
        else:
            return self.memory.get_variable(name, []).to_value()

    def interact(self):
        """Interactive interpreter session."""
        while True:
            try:
                with self._handle_exceptions():
                    self.interpreter.loop()
                    if self._auto_mode:
                        self._auto_step()
                    else:
                        self._show_prompt()
                        # input loop, checks events
                        line = self.editor.wait_screenline(from_start=True)
                        self._prompt = not self._store_line(line)
            except error.Exit:
                break

    def close(self):
        """Close the session."""
        # close files if we opened any
        self.files.close_all()
        self.devices.close()

    ###########################################################################
    # implementation

    def _show_prompt(self):
        """Show the Ok or EDIT prompt, unless suppressed."""
        if self._edit_prompt:
            linenum, tell = self._edit_prompt
            self.program.edit(self.screen, linenum, tell)
            self._edit_prompt = False
        elif self._prompt:
            self.screen.start_line()
            self.screen.write_line('Ok\xff')

    def _store_line(self, line):
        """Store a program line or schedule a command line for execution."""
        if not line:
            return True
        self.interpreter.direct_line = self.tokeniser.tokenise_line(line)
        c = self.interpreter.direct_line.peek()
        if c == '\0':
            # check for lines starting with numbers (6553 6) and empty lines
            self.program.check_number_start(self.interpreter.direct_line)
            self.program.store_line(self.interpreter.direct_line)
            # clear all program stacks
            self.interpreter.clear_stacks_and_pointers()
            self._clear_all()
            return True
        elif c != '':
            # it is a command, go and execute
            self.interpreter.set_parse_mode(True)
            return False

    def _auto_step(self):
        """Generate an AUTO line number and wait for input."""
        try:
            numstr = str(self._auto_linenum)
            self.screen.write(numstr)
            if self._auto_linenum in self.program.line_numbers:
                self.screen.write('*')
                line = bytearray(self.editor.wait_screenline(from_start=True))
                if line[:len(numstr)+1] == numstr + '*':
                    line[len(numstr)] = ' '
            else:
                self.screen.write(' ')
                line = bytearray(self.editor.wait_screenline(from_start=True))
            # run or store it; don't clear lines or raise undefined line number
            self.interpreter.direct_line = self.tokeniser.tokenise_line(line)
            c = self.interpreter.direct_line.peek()
            if c == '\0':
                # check for lines starting with numbers (6553 6) and empty lines
                empty, scanline = self.program.check_number_start(self.interpreter.direct_line)
                if not empty:
                    self.program.store_line(self.interpreter.direct_line)
                    # clear all program stacks
                    self.interpreter.clear_stacks_and_pointers()
                    self._clear_all()
                self._auto_linenum = scanline + self._auto_increment
            elif c != '':
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
        except error.Break:
            self.sound.stop_all_sound()
            self._prompt = False
        except error.RunError as e:
            self._handle_error(e)
            self._prompt = True
        except error.Exit:
            raise
        except Exception as e:
            self.debugger.bluescreen(e)

    def _handle_error(self, e):
        """Handle a BASIC error through error message."""
        # not handled by ON ERROR, stop execution
        self.screen.write_error_message(e.message, self.program.get_line_number(e.pos))
        self.interpreter.set_parse_mode(False)
        self.interpreter.input_mode = False
        # special case: syntax error
        if e.err == error.STX:
            # for some reason, err is reset to zero by GW-BASIC in this case.
            self.interpreter.error_num = 0
            if e.pos is not None and e.pos != -1:
                # line edit gadget appears
                self._edit_prompt = (self.program.get_line_number(e.pos), e.pos+1)

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
                video_size = values.round(video_size).to_value()
                self.screen.set_video_memory_size(video_size)
            # execute any remaining parsing steps
            next(args)
        except StopIteration:
            pass
        self._clear_all()

    def _clear_all(self, close_files=False,
              preserve_common=False, preserve_all=False, preserve_deftype=False):
        """Clear everything required for the CLEAR command."""
        if close_files:
            # close all files
            self.files.close_all()
        # Resets the stack and string space
        # Clears all COMMON and user variables
        # release all disk buffers (FIELD)?
        self.memory.clear(preserve_common, preserve_all, preserve_deftype)
        if not preserve_all:
            # functions are cleared except when CHAIN ... ALL is specified
            self.parser.user_functions.clear()
        # Resets STRIG to off
        self.input_methods.stick.is_on = False
        # stop all sound
        self.sound.stop_all_sound()
        # reset PLAY state
        self.play_parser.reset()
        # reset DRAW state (angle, scale) and current graphics position
        self.screen.drawing.reset()
        # reset random number generator
        self.randomiser.clear()
        # reset stacks & pointers
        self.interpreter.clear()

    def shell_(self, args):
        """SHELL: open OS shell and optionally execute command."""
        cmd = self.strings.next_temporary(args)
        list(args)
        # force cursor visible in all cases
        self.screen.cursor.show(True)
        # sound stops playing and is forgotten
        self.sound.stop_all_sound()
        # run the os-specific shell
        self.shell.launch(cmd)
        # reset cursor visibility to its previous state
        self.screen.cursor.reset_visibility()

    def term_(self, args):
        """TERM: terminal emulator."""
        list(args)
        self._clear_all()
        self.interpreter.tron = False
        if not self._term_program:
            # on Tandy, raises Internal Error
            # and deletes the program currently in memory
            raise error.RunError(error.INTERNAL_ERROR)
        with self.files.open_native_or_basic(self._term_program,
                    filetype='ABP', mode='I') as progfile:
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
        out = self.strings.next_temporary(args)
        if out is not None:
            out = self.files.open(0, out, filetype='A', mode='O')
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
                self.input_methods.wait()
                # LIST on screen is slightly different from just writing
                self.screen.list_line(l)
        # return to direct mode
        self.interpreter.set_pointer(False)

    def edit_(self, args):
        """EDIT: output a program line and position cursor for editing."""
        from_line, = args
        from_line, = self.program.explicit_lines(from_line)
        self.program.last_stored = from_line
        if from_line is None or from_line not in self.program.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        # throws back to direct mode
        # jump to end of direct line so execution stops
        self.interpreter.set_pointer(False)
        self.screen.cursor.reset_visibility()
        # request edit prompt
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
        name = self.strings.next_temporary(args)
        comma_r, = args
        with self.files.open(0, name, filetype='ABP', mode='I') as f:
            self.program.load(f)
        # reset stacks
        self.interpreter.clear_stacks_and_pointers()
        # clear variables
        self._clear_all()
        if comma_r:
            # in ,R mode, don't close files; run the program
            self.interpreter.set_pointer(True, 0)
        else:
            self.files.close_all()
        self.interpreter.tron = False

    def chain_(self, args):
        """CHAIN: load program and chain execution."""
        merge = next(args)
        name = self.strings.next_temporary(args)
        jumpnum = next(args)
        if jumpnum is not None:
            jumpnum = values.to_int(jumpnum, unsigned=True)
        common_all, delete_lines = next(args), next(args)
        from_line, to_line = delete_lines if delete_lines else None, None
        if to_line is not None and to_line not in self.program.line_numbers:
            raise error.RunError(error.IFC)
        list(args)
        if self.program.protected and merge:
            raise error.RunError(error.IFC)
        with self.files.open(0, name, filetype='ABP', mode='I') as f:
            if delete_lines:
                # delete lines from existing code before merge (without MERGE, this is pointless)
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
        # preserve DEFtype on MERGE
        self._clear_all(preserve_common=True, preserve_all=common_all, preserve_deftype=merge)

    def save_(self, args):
        """SAVE: save program to a file."""
        name = self.strings.next_temporary(args)
        mode = (next(args) or 'B').upper()
        list(args)
        with self.files.open(0, name, filetype=mode, mode='O',
                            seg=self.memory.data_segment, offset=self.memory.code_start,
                            length=len(self.program.bytecode.getvalue())-1) as f:
            self.program.save(f)
        if mode == 'A':
            # return to direct mode
            self.interpreter.set_pointer(False)

    def merge_(self, args):
        """MERGE: merge lines from file into current program."""
        name = self.strings.next_temporary(args)
        list(args)
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        with self.files.open(0, name, filetype='A', mode='I') as f:
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
                name = self.strings.next_temporary(args)
                comma_r = next(args)
                with self.files.open(0, name, filetype='ABP', mode='I') as f:
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
                raise error.RunError(error.UNDEFINED_LINE_NUMBER)
            self.interpreter.jump(jumpnum)

    def end_(self, args):
        """END: end program execution and return to interpreter."""
        list(args)
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
            finp = self.files.get(file_number, mode='IR')
            self._input_file(finp, args)
        else:
            newline, prompt, following = next(args)
            self._input_console(newline, prompt, following, args)

    def _input_console(self, newline, prompt, following, readvar):
        """INPUT: request input from user."""
        if following == ';':
            prompt += '? '
        # read the input
        self.interpreter.input_mode = True
        self.parser.redo_on_break = True
        # readvar is a list of (name, indices) tuples
        # we return a list of (name, indices, values) tuples
        while True:
            self.screen.write(prompt)
            # disconnect the wrap between line with the prompt and previous line
            if self.screen.current_row > 1:
                self.screen.apage.row[self.screen.current_row-2].wrap = False
            line = self.editor.wait_screenline(write_endl=newline)
            inputstream = devices.InputTextFile(line)
            # read the values and group them and the separators
            var, values, seps = [], [], []
            for name, indices in readvar:
                name = self.memory.complete_name(name)
                word, sep = inputstream.input_entry(name[-1], allow_past_end=True)
                try:
                    value = self.values.from_repr(word, allow_nonnum=False, typechar=name[-1])
                except error.RunError as e:
                    # string entered into numeric field
                    value = None
                var.append([name, indices])
                values.append(value)
                seps.append(sep)
            # last separator not empty: there were too many values or commas
            # earlier separators empty: there were too few values
            # empty values will be converted to zero by from_str
            # None means a conversion error occurred
            if (seps[-1] or '' in seps[:-1] or None in values):
                # good old Redo!
                self.screen.write_line('?Redo from start')
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
            word, _ = finp.input_entry(name[-1], allow_past_end=False)
            value = self.values.from_repr(word, allow_nonnum=False, typechar=name[-1])
            if value is None:
                value = self.values.new(name[-1])
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
            finp = self.files.get(file_number, mode='IR')
        # get string variable
        readvar, indices = next(args)
        list(args)
        if not readvar:
            raise error.RunError(error.STX)
        readvar = self.memory.complete_name(readvar)
        if readvar[-1] != '$':
            raise error.RunError(error.TYPE_MISMATCH)
        # read the input
        if finp:
            line = finp.read_line()
            if line is None:
                raise error.RunError(error.INPUT_PAST_END)
        else:
            self.interpreter.input_mode = True
            self.parser.redo_on_break = True
            self.screen.write(prompt)
            line = self.editor.wait_screenline(write_endl=newline)
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
            while val is None:
                self.screen.write('Random number seed (-32768 to 32767)? ')
                seed = self.editor.wait_screenline()
                val = self.values.from_repr(seed, allow_nonnum=False)
            # seed entered on prompt is rounded to int
            val = values.to_integer(val)
        self.randomiser.reseed(val)

    def key_(self, args):
        """KEY: macro or event handler definition."""
        keynum = values.to_int(next(args))
        error.range_check(1, 255, keynum)
        text = self.strings.next_temporary(args)
        list(args)
        if keynum <= self.basic_events.num_fn_keys:
            self.screen.fkey_macros.set(keynum, text)
        else:
            # only length-2 expressions can be assigned to KEYs over 10
            # in which case it's a key scancode definition
            if len(text) != 2:
                raise error.RunError(error.IFC)
            self.basic_events.key[keynum-1].set_trigger(str(text))
