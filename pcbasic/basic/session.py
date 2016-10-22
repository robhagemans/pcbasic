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
from . import scalars
from . import arrays
from . import values
from . import expressions
from . import statements
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
        # use dummy queues if not provided
        if iface:
            self.input_queue, self.video_queue, self.audio_queue = iface.get_queues()
        else:
            self.input_queue = Queue.Queue()
            self.video_queue = signals.NullQueue()
            self.audio_queue = signals.NullQueue()
        # true if a prompt is needed on next cycle
        self._prompt = True
        # input mode is AUTO (used by AUTO)
        self.auto_mode = False
        self.auto_linenum = 10
        self.auto_increment = 10
        # interpreter is waiting for INPUT or LINE INPUT
        self.input_mode = False
        self.redo_on_break = False
        # syntax error prompt and EDIT
        self.edit_prompt = False
        # program for TERM command
        self._term_program = pcjr_term
        ######################################################################
        # prepare codepage
        self.codepage = cp.Codepage(codepage, box_protect)
        # prepare I/O redirection
        self.input_redirection, self.output_redirection = redirect.get_redirection(
                self.codepage, stdio, input_file, output_file, append, self.input_queue)
        # set up event handlers
        self.events = events.Events(self, syntax)
        # initialise sound queue
        # needs Session for wait() and queues only
        self.sound = sound.Sound(self, syntax)
        # function key macros
        self.fkey_macros = editor.FunctionKeyMacros(12 if syntax == 'tandy' else 10)
        # Sound is needed for the beeps on \a
        # Session is only for queues
        self.screen = display.Screen(self, text_width,
                video_memory, video_capabilities, monitor,
                self.sound, self.output_redirection, self.fkey_macros,
                cga_low, mono_tint, screen_aspect,
                self.codepage, font, warn_fonts=option_debug)
        # set up variables and memory model state
        # initialise the data segment
        self.memory = memory.DataSegment(
                    max_memory, reserved_memory, max_reclen, max_files)
        #MOVE into DataSegment?
        self.common_scalars = set()
        self.common_arrays = set()
        # string space
        self.strings = values.StringSpace(self.memory)
        # prepare string and number handler
        self.values = values.Values(self.screen, self.strings, double)
        # create fields after value handler has been created (circular dependency in DataSegment)
        self.memory.values = self.values
        self.memory.reset_fields()
        # scalar space
        self.scalars = scalars.Scalars(self.memory, self.values)
        # array space
        self.arrays = arrays.Arrays(self.memory, self.values)
        # prepare tokeniser
        token_keyword = tk.TokenKeywordDict(syntax)
        self.tokeniser = tokeniser.Tokeniser(self.values, token_keyword)
        self.lister = lister.Lister(self.values, token_keyword)
        # initialise the program
        bytecode = codestream.TokenisedStream()
        self.program = program.Program(
                self.tokeniser, self.lister, max_list_line, allow_protect,
                allow_code_poke, self.memory.code_start, bytecode)
        # register all data segment users
        self.memory.set_buffers(
                self.program, self.scalars, self.arrays, self.strings, self.values)
        # prepare input methods
        self.pen = inputmethods.Pen(self.screen)
        self.stick = inputmethods.Stick()
        # Screen needed in Keyboard for print_screen()
        # Sound is needed for the beeps when the buffer fills up
        # Events needed for wait() only
        self.keyboard = inputmethods.Keyboard(self.events, self.screen, self.fkey_macros,
                self.codepage, self.sound,
                keystring, ignore_caps, ctrl_c_is_break)
        # intialise devices and files
        # DataSegment needed for COMn and disk FIELD buffers
        # Events needed for wait()
        self.devices = files.Devices(
                self.events, self.memory.fields, self.screen, self.keyboard,
                device_params, current_device, mount_dict,
                print_trigger, temp_dir, serial_buffer_size,
                utf8, universal)
        self.files = files.Files(self.devices, max_files, max_reclen)
        # set LPT1 as target for print_screen()
        self.screen.set_print_screen_target(self.devices.lpt1_file)
        # initialise the editor
        self.editor = editor.Editor(
                self.screen, self.keyboard, self.sound,
                self.output_redirection, self.devices.lpt1_file)
        # set up the SHELL command
        self.shell = dos.get_shell_manager(self.keyboard, self.screen, self.codepage, option_shell, syntax)
        # initialise random number generator
        self.randomiser = values.Randomiser(self.values)
        # initialise system clock
        self.clock = clock.Clock()
        # initialise machine ports
        self.machine = machine.MachinePorts(self)
        # interpreter is executing a command (needs Screen)
        self._set_parse_mode(False)
        # initialise the expression parser
        self.expression_parser = expressions.ExpressionParser(
                self.values, self.memory, self.program, self.files)
        self.statement_parser = statements.StatementParser(
                self.values, self.strings, self.memory, self.expression_parser,
                syntax)
        # initialise the parser
        self.events.reset()
        self.interpreter = interpreter.Interpreter(
                self, self.program, self.statement_parser)
        # set up rest of memory model
        self.all_memory = machine.Memory(self.memory, self.devices, self.files,
                            self.screen, self.keyboard, self.screen.fonts[8],
                            self.interpreter, peek_values, syntax)
        # set up debugger
        self.debugger = debug.get_debugger(self, option_debug)
        # build function table (depends on Memory having been initialised)
        self.expression_parser.init_functions(self)
        self.statement_parser.init_statements(self)

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, dummy_1, dummy_2, dummy_3):
        """Context guard."""
        self.close()

    def __getstate__(self):
        """Pickle the session."""
        pickle_dict = self.__dict__.copy()
        # remove queues from state
        pickle_dict['input_queue'] = signals.NullQueue()
        pickle_dict['video_queue'] = signals.NullQueue()
        pickle_dict['audio_queue'] = signals.NullQueue()
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle and resume the session."""
        self.__dict__.update(pickle_dict)
        # build function table (depends on Memory having been initialised)
        self.expression_parser.init_functions(self)
        self.statement_parser.init_statements(self)
        self.keyboard._input_closed = False
        # suppress double prompt
        if not self._parse_mode:
            self._prompt = False

    def attach(self, iface=None):
        """Attach interface to interpreter session."""
        if iface:
            self.input_queue, self.video_queue, self.audio_queue = iface.get_queues()
            # rebuild the screen
            self.screen.rebuild()
            # rebuild audio queues
            self.sound.rebuild()
        else:
            # use dummy video & audio queues if not provided
            # but an input queue shouls be operational for redirects
            self.input_queue = Queue.Queue
        # attach input queue to redirects
        self.input_redirection.attach(self.input_queue)
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
                self._store_line(self.codepage.str_from_unicode(cmd))
                self._loop()

    def evaluate(self, expression):
        """Evaluate a BASIC expression."""
        if isinstance(expression, unicode):
            expression = self.codepage.str_from_unicode(expression)
        with self._handle_exceptions():
            # attach print token so tokeniser has a whole statement to work with
            tokens = self.tokeniser.tokenise_line(b'?' + expression)
            # skip : and print token and parse expression
            tokens.read(2)
            return self.expression_parser.parse(tokens).to_value()
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
                    self._loop()
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

    def _loop(self):
        """Run read-eval-print loop until control returns to user."""
        self.screen.cursor.reset_visibility()
        while True:
            last_parse = self._parse_mode
            if self._parse_mode:
                try:
                    # parse until break or end
                    self.interpreter.parse()
                    self._parse_mode = False
                except error.Break as e:
                    # ctrl-break stops foreground and background sound
                    self.sound.stop_all_sound()
                    self._handle_break(e)
            elif self.auto_mode:
                try:
                    # auto step, checks events
                    self._auto_step()
                except error.Break:
                    # ctrl+break, ctrl-c both stop background sound
                    self.sound.stop_all_sound()
                    self.auto_mode = False
            # change loop modes
            if self._parse_mode != last_parse:
                # move pointer to the start of direct line (for both on and off!)
                self.interpreter.set_pointer(False, 0)
                self.screen.cursor.reset_visibility()
            # return control to user
            if ((not self.auto_mode) and (not self._parse_mode)):
                break

    def _set_parse_mode(self, on):
        """Enter or exit parse mode."""
        self._parse_mode = on
        self.screen.cursor.default_visible = not on

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
        elif c != '':
            # it is a command, go and execute
            self._set_parse_mode(True)
        return not self._parse_mode

    def _show_prompt(self):
        """Show the Ok or EDIT prompt, unless suppressed."""
        if self._parse_mode:
            return
        if self.edit_prompt:
            linenum, tell = self.edit_prompt
            self.program.edit(self.screen, linenum, tell)
            self.edit_prompt = False
        elif self._prompt:
            self.screen.start_line()
            self.screen.write_line("Ok\xff")

    def _auto_step(self):
        """Generate an AUTO line number and wait for input."""
        numstr = str(self.auto_linenum)
        self.screen.write(numstr)
        if self.auto_linenum in self.program.line_numbers:
            self.screen.write('*')
            line = bytearray(self.editor.wait_screenline(from_start=True))
            if line[:len(numstr)+1] == numstr+'*':
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
            self.auto_linenum = scanline + self.auto_increment
        elif c != '':
            # it is a command, go and execute
            self._set_parse_mode(True)


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
        self._write_error_message(e.message, self.program.get_line_number(e.pos))
        self._set_parse_mode(False)
        self.input_mode = False
        # special case: syntax error
        if e.err == error.STX:
            # for some reason, err is reset to zero by GW-BASIC in this case.
            self.interpreter.error_num = 0
            if e.pos is not None and e.pos != -1:
                # line edit gadget appears
                self.edit_prompt = (self.program.get_line_number(e.pos), e.pos+1)

    def _handle_break(self, e):
        """Handle a Break event."""
        # print ^C at current position
        if not self.input_mode and not e.stop:
            self.screen.write('^C')
        # if we're in a program, save pointer
        pos = -1
        if self.interpreter.run_mode:
            if self.redo_on_break:
                pos = self.interpreter.current_statement
            else:
                self.program.bytecode.skip_to(tk.END_STATEMENT)
                pos = self.program.bytecode.tell()
            self.interpreter.stop = pos
        self._write_error_message(e.message, self.program.get_line_number(pos))
        self._set_parse_mode(False)
        self.input_mode = False
        self.redo_on_break = False

    def _write_error_message(self, msg, linenum):
        """Write an error message to the console."""
        self.screen.start_line()
        self.screen.write(msg)
        if linenum is not None and linenum > -1 and linenum < 65535:
            self.screen.write(' in %i' % linenum)
        self.screen.write_line('\xFF')

    ###########################################################################
    # callbacks

    def clear_(self, args):
        """CLEAR: clear memory and redefine memory limits."""
        try:
            # positive integer expression allowed but not used
            intexp = next(args)
            if intexp is not None:
                expr = values.to_int(intexp)
                if expr < 0:
                    raise error.RunError(error.IFC)
            exp1 = next(args)
            if exp1 is not None:
                # this produces a *signed* int
                mem_size = values.to_int(exp1, unsigned=True)
                if mem_size == 0:
                    #  0 leads to illegal fn call
                    raise error.RunError(error.IFC)
                else:
                    if not self.memory.set_basic_memory_size(mem_size):
                        raise error.RunError(error.OUT_OF_MEMORY)
            # set aside stack space for GW-BASIC. The default is the previous stack space size.
            exp2 = next(args)
            if exp2 is not None:
                stack_size = values.to_int(exp2, unsigned=True)
                # this should be an unsigned int
                if stack_size < 0:
                    stack_size += 0x10000
                if stack_size == 0:
                    #  0 leads to illegal fn call
                    raise error.RunError(error.IFC)
                self.memory.set_stack_size(stack_size)
            exp3 = next(args)
            if exp3 is not None:
                # Tandy/PCjr: select video memory size
                video_size = values.round(exp3).to_value()
                if not self.screen.set_video_memory_size(video_size):
                    self.screen.screen(0, 0, 0, 0)
                    self.screen.init_mode()
            # execute any remaining parsing steps
            next(args)
        except StopIteration:
            pass
        self._clear_all()

    def _clear_all(self, close_files=False,
              preserve_common=False, preserve_all=False, preserve_deftype=False):
        """Clear everything required for the CLEAR command."""
        #   Resets the stack and string space
        #   Clears all COMMON and user variables
        if preserve_all:
            self.memory.clear_variables(self.scalars, self.arrays)
        else:
            if not preserve_common:
                # at least I think these should be cleared by CLEAR?
                self.common_scalars = set()
                self.common_arrays = set()
            self.memory.clear_variables(self.common_scalars, self.common_arrays)
            # functions are cleared except when CHAIN ... ALL is specified
            self.expression_parser.user_functions.clear()
        if not preserve_deftype:
            # deftype is not preserved on CHAIN with ALL, but is preserved with MERGE
            self.memory.clear_deftype()
        # reset random number generator
        self.randomiser.clear()
        if close_files:
            # close all files
            self.files.close_all()
        # release all disk buffers (FIELD)?
        self.memory.reset_fields()
        # stop all sound
        self.sound.stop_all_sound()
        # Resets STRIG to off
        self.stick.is_on = False
        # reset sound and PLAY state
        self.sound.reset()
        # reset DRAW state (angle, scale) and current graphics position
        self.screen.drawing.reset()
        self.interpreter.clear()

    def shell_(self, cmd=None):
        """SHELL: open OS shell and optionally execute command."""
        # force cursor visible in all cases
        self.screen.cursor.show(True)
        # sound stops playing and is forgotten
        self.sound.stop_all_sound()
        # no user events
        with self.events.suspend():
            # run the os-specific shell
            self.shell.launch(cmd)
        # reset cursor visibility to its previous state
        self.screen.cursor.reset_visibility()

    def term_(self):
        """TERM: terminal emulator."""
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
        from_line, to_line = next(args)
        list(args)
        # throws back to direct mode
        self.program.delete(from_line, to_line)
        # clear all program stacks
        self.interpreter.clear_stacks_and_pointers()
        # clear all variables
        self._clear_all()

    def edit_(self, args):
        """EDIT: output a program line and position cursor for editing."""
        from_line, = args
        self.program.last_stored = from_line
        if from_line is None or from_line not in self.program.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        # throws back to direct mode
        # jump to end of direct line so execution stops
        self.interpreter.set_pointer(False)
        self.screen.cursor.reset_visibility()
        # request edit prompt
        self.edit_prompt = (from_line, None)

    def auto_(self, args):
        """AUTO: enter automatic line numbering mode."""
        linenum, increment = args
        # reset linenum and increment on each call of AUTO (even in AUTO mode)
        self.auto_linenum = linenum if linenum is not None else 10
        self.auto_increment = increment if increment is not None else 10
        # move program pointer to end
        self.interpreter.set_pointer(False)
        # continue input in AUTO mode
        self.auto_mode = True

    def list_(self, args):
        """LIST: output program lines."""
        from_line, to_line = next(args)
        out, = args
        lines = self.program.list_lines(from_line, to_line)
        if out:
            with out:
                for l in lines:
                    out.write_line(l)
        else:
            for l in lines:
                # flow of listing is visible on screen
                # and interruptible
                self.events.wait()
                # LIST on screen is slightly different from just writing
                self.screen.list_line(l)
        # return to direct mode
        self.interpreter.set_pointer(False)

    def llist_(self, args):
        """LLIST: output program lines to LPT1: """
        from_line, to_line = next(args)
        list(args)
        for l in self.program.list_lines(from_line, to_line):
            self.devices.lpt1_file.write_line(l)
        # return to direct mode
        self.interpreter.set_pointer(False)

    def load_(self, args):
        """LOAD: load program from file."""
        name, comma_r = args
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
        merge, name, jumpnum = next(args), next(args), next(args)
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
        name, mode = args
        mode = (mode or 'B').upper()
        with self.files.open(0, name, filetype=mode, mode='O',
                            seg=self.memory.data_segment, offset=self.memory.code_start,
                            length=len(self.program.bytecode.getvalue())-1) as f:
            self.program.save(f)
        if mode == 'A':
            # return to direct mode
            self.interpreter.set_pointer(False)

    def merge_(self, name):
        """MERGE: merge lines from file into current program."""
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        with self.files.open(0, name, filetype='A', mode='I') as f:
            self.program.merge(f)
        # clear all program stacks
        self.interpreter.clear_stacks_and_pointers()

    def new_(self):
        """NEW: clear program from memory."""
        self.interpreter.troff_()
        # deletes the program currently in memory
        self.program.erase()
        # reset stacks
        self.interpreter.clear_stacks_and_pointers()
        # and clears all variables
        self._clear_all()
        self.interpreter.set_pointer(False)

    def renum_(self, args):
        """RENUM: renumber program line numbers."""
        new, old, step = args
        if step is not None and step < 1:
            raise error.RunError(error.IFC)
        old_to_new = self.program.renum(self.screen, new, old, step)
        # stop running if we were
        self.interpreter.set_pointer(False)
        # reset loop stacks
        self.interpreter.clear_stacks()
        # renumber error handler
        if self.interpreter.on_error:
            self.interpreter.on_error = old_to_new[self.interpreter.on_error]
        # renumber event traps
        for handler in self.events.all:
            if handler.gosub:
                handler.set_jump(old_to_new[handler.gosub])

    def run_(self, args):
        """RUN: start program execution."""
        arg0, arg1 = args
        comma_r = False
        jumpnum = None
        if isinstance(arg0, bytes):
            name, comma_r = arg0, arg1
            with self.files.open(0, name, filetype='ABP', mode='I') as f:
                self.program.load(f)
        self.interpreter.on_error = 0
        self.interpreter.error_handle_mode = False
        self.interpreter.clear_stacks_and_pointers()
        self._clear_all(close_files=not comma_r)
        if isinstance(arg0, int):
            jumpnum = arg0
            if jumpnum not in self.program.line_numbers:
                raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        if jumpnum is None:
            self.interpreter.set_pointer(True, 0)
        else:
            self.interpreter.jump(jumpnum)

    def end_(self):
        """END: end program execution and return to interpreter."""
        # jump to end of direct line so execution stops
        self.interpreter.set_pointer(False)
        # avoid NO RESUME
        self.interpreter.error_handle_mode = False
        self.interpreter.error_resume = None
        self.files.close_all()

    def common_(self, args):
        """COMMON: define variables to be preserved on CHAIN."""
        common_vars = list(args)
        common_scalars = [name for name, brackets in common_vars if not brackets]
        common_arrays = [name for name, brackets in common_vars if brackets]
        self.common_scalars |= set(common_scalars)
        self.common_arrays |= set(common_arrays)

    def input_(self, args):
        """INPUT: request input from user or read from file."""
        file_number = next(args)
        if file_number is not None:
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
        self.input_mode = True
        self.redo_on_break = True
        # readvar is a list of (name, indices) tuples
        # we return a list of (name, indices, values) tuples
        while True:
            self.editor.screen.write(prompt)
            # disconnect the wrap between line with the prompt and previous line
            if self.editor.screen.current_row > 1:
                self.editor.screen.apage.row[self.editor.screen.current_row-2].wrap = False
            line = self.editor.wait_screenline(write_endl=newline)
            inputstream = devices.InputTextFile(line)
            # read the values and group them and the separators
            var, values, seps = [], [], []
            for v in readvar:
                word, sep = inputstream.input_entry(v[0][-1], allow_past_end=True)
                try:
                    value = self.values.from_repr(word, allow_nonnum=False, typechar=v[0][-1])
                except error.RunError as e:
                    # string entered into numeric field
                    value = None
                var.append(list(v))
                values.append(value)
                seps.append(sep)
            # last separator not empty: there were too many values or commas
            # earlier separators empty: there were too few values
            # empty values will be converted to zero by from_str
            # None means a conversion error occurred
            if (seps[-1] or '' in seps[:-1] or None in values):
                # good old Redo!
                self.editor.screen.write_line('?Redo from start')
                readvar = var
            else:
                varlist = [r + [v] for r, v in zip(var, values)]
                break
        self.redo_on_break = False
        self.input_mode = False
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
            finp = self.files.get(file_number, mode='IR')
        # get string variable
        readvar, indices = next(args)
        list(args)
        if not readvar:
            raise error.RunError(error.STX)
        elif readvar[-1] != '$':
            raise error.RunError(error.TYPE_MISMATCH)
        # read the input
        if finp:
            line = finp.read_line()
            if line is None:
                raise error.RunError(error.INPUT_PAST_END)
        else:
            self.input_mode = True
            self.redo_on_break = True
            self.screen.write(prompt)
            line = self.editor.wait_screenline(write_endl=newline)
            self.redo_on_break = False
            self.input_mode = False
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
                self.screen.write("Random number seed (-32768 to 32767)? ")
                seed = self.editor.wait_screenline()
                val = self.values.from_repr(seed, allow_nonnum=False)
            # seed entered on prompt is rounded to int
            val = values.cint_(val)
        self.randomiser.reseed(val)

    def error_(self, args):
        """ERROR: simulate an error condition."""
        errn, = args
        errn = values.to_int(errn)
        error.range_check(1, 255, errn)
        raise error.RunError(errn)
