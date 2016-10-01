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
        # syntax error prompt and EDIT
        self.edit_prompt = False
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
        token_keyword = tk.TokenKeywordDict(syntax, option_debug)
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
                self, self.program, self.statement_parser, pcjr_term)
        # set up rest of memory model
        self.all_memory = machine.Memory(self.memory, self.devices, self.files,
                            self.screen, self.keyboard, self.screen.fonts[8],
                            self.interpreter, peek_values, syntax)
        # build function table (depends on Memory having been initialised)
        self.expression_parser.init_functions(self)
        self.statement_parser.init_statements(self)
        # set up debugger
        self.debugger = debug.get_debugger(self, option_debug)

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
            self.clear_()
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
                self.clear_()
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
            pos = self.program.bytecode.tell()-1
            self.interpreter.stop = pos
        self._write_error_message(e.message, self.program.get_line_number(pos))
        self._set_parse_mode(False)
        self.input_mode = False

    def _write_error_message(self, msg, linenum):
        """Write an error message to the console."""
        self.screen.start_line()
        self.screen.write(msg)
        if linenum is not None and linenum > -1 and linenum < 65535:
            self.screen.write(' in %i' % linenum)
        self.screen.write_line('\xFF')

    ###########################################################################
    # callbacks

    def clear_(self, close_files=False,
              preserve_common=False, preserve_all=False, preserve_deftype=False):
        """Execute a CLEAR command."""
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
        self.stick.strig_statement_(tk.OFF)
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

    def delete_(self, from_line, to_line):
        """DELETE: delete range of lines from program."""
        # throws back to direct mode
        self.program.delete(from_line, to_line)
        # clear all program stacks
        self.interpreter.clear_stacks_and_pointers()
        # clear all variables
        self.clear_()

    def edit_(self, from_line):
        """EDIT: output a program line and position cursor for editing."""
        # throws back to direct mode
        # jump to end of direct line so execution stops
        self.interpreter.set_pointer(False)
        self.screen.cursor.reset_visibility()
        # request edit prompt
        self.edit_prompt = (from_line, None)

    def auto_(self, linenum=None, increment=None):
        """AUTO: enter automatic line numbering mode."""
        # reset linenum and increment on each call of AUTO (even in AUTO mode)
        self.auto_linenum = linenum if linenum is not None else 10
        self.auto_increment = increment if increment is not None else 10
        # move program pointer to end
        self.interpreter.set_pointer(False)
        # continue input in AUTO mode
        self.auto_mode = True

    def list_(self, from_line, to_line, out=None):
        """LIST: output program lines."""
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

    def llist_(self, from_line, to_line):
        """LLIST: output program lines to LPT1: """
        for l in self.program.list_lines(from_line, to_line):
            self.devices.lpt1_file.write_line(l)
        # return to direct mode
        self.interpreter.set_pointer(False)

    def load_(self, name, comma_r=None):
        """LOAD: load program from file."""
        with self.files.open(0, name, filetype='ABP', mode='I') as f:
            self.program.load(f)
        # reset stacks
        self.interpreter.clear_stacks_and_pointers()
        # clear variables
        self.clear_()
        if comma_r:
            # in ,R mode, don't close files; run the program
            self.interpreter.jump(None)
        else:
            self.files.close_all()
        self.interpreter.tron = False

    def chain_(self, name, jumpnum=None, common_all=False, delete_lines=None, merge=False):
        """CHAIN: load program and chain execution."""
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
        self.clear_(preserve_common=True, preserve_all=common_all, preserve_deftype=merge)

    def save_(self, name, mode=None):
        """SAVE: save program to a file."""
        mode = mode or 'B'
        with self.files.open(0, name, filetype=mode, mode='O',
                            seg=self.memory.data_segment, offset=self.memory.code_start,
                            length=len(self.program.bytecode.getvalue())-1) as f:
            self.program.save(f)

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
        self.clear_()
        self.interpreter.set_pointer(False)

    def renum_(self, new=None, old=None, step=None):
        """RENUM: renumber program line numbers."""
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

    def end_(self):
        """END: end program execution and return to interpreter."""
        self.interpreter.stop = self.program.bytecode.tell()
        # jump to end of direct line so execution stops
        self.interpreter.set_pointer(False)
        # avoid NO RESUME
        self.interpreter.error_handle_mode = False
        self.interpreter.error_resume = None
        self.files.close_all()
