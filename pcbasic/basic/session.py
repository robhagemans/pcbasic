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
from contextlib import contextmanager
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from . import error
from . import util
from . import tokenise
from . import events
from . import program
from . import signals
from . import display
from . import editor
from . import inputs
from . import debug
from . import rnd
from . import clock
from . import shell
from . import memory
from . import machine
from . import parser
from . import files
from . import sound
from . import redirect
from . import unicodepage
from . import var


class Session(object):
    """Interpreter session."""

    ###########################################################################
    # public interface methods

    def __init__(self,
            input_queue=None, video_queue=None,
            tone_queue=None, message_queue=None,
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
        # *4 means we have multiple references to the same queue
        # which doesn't matter since we're dropping all signals anyway
        self.input_queue = input_queue or signals.NullQueue()
        self.video_queue = video_queue or signals.NullQueue()
        self.tone_queue = tone_queue or [signals.NullQueue()]*4
        self.message_queue = message_queue or signals.NullQueue()
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
        self.codepage = unicodepage.Codepage(codepage, box_protect)
        # prepare I/O redirection
        self.input_redirection, self.output_redirection = redirect.get_redirection(
                self.codepage, stdio, input_file, output_file, append)
        # prepare tokeniser
        self.tokeniser = tokenise.Tokeniser(syntax, option_debug)
        # initialise the program
        self.program = program.Program(self.tokeniser,
                max_list_line, allow_protect, allow_code_poke)
        # function key macros
        self.fkey_macros = editor.FunctionKeyMacros(12 if syntax == 'tandy' else 10)
        # set up event handlers
        self.events = events.Events(self, syntax)
        # initialise sound queue
        # needs Session for wait() and queues only
        self.sound = sound.Sound(self, syntax)
        # Sound is needed for the beeps on \a
        # Session is only for queues and wait() in Graphics (flood fill)
        self.screen = display.Screen(self, text_width,
                video_memory, video_capabilities, monitor,
                self.sound, self.output_redirection, self.fkey_macros,
                cga_low, mono_tint, screen_aspect,
                self.codepage, font, warn_fonts=option_debug)
        # prepare input methods
        self.pen = inputs.Pen(self.screen)
        self.stick = inputs.Stick()
        # Screen needed in Keyboard for print_screen()
        # Sound is needed for the beeps when the buffer fills up
        # Events needed for wait() only
        self.keyboard = inputs.Keyboard(self.events, self.screen, self.fkey_macros,
                self.codepage, self.sound,
                keystring, ignore_caps, ctrl_c_is_break)
        # set up variables and memory model state
        # initialise the data segment
        self.memory = memory.DataSegment(self.program, max_memory,
                                        reserved_memory, max_reclen, max_files)
        self.program.set_address(self.memory.code_start)
        #D
        # these should not be reassigned by DataSegment
        self.scalars = self.memory.scalars
        self.arrays = self.memory.arrays
        self.strings = self.memory.strings
        #MOVE into DataSegment?
        self.common_scalars = set()
        self.common_arrays = set()
        self.user_functions = {}
        # intialise devices and files
        # DataSegment needed for COMn and disk FIELD buffers
        # Events needed for wait()
        self.devices = files.Devices(
                self.events, self.memory.fields, self.screen, self.keyboard,
                device_params, current_device, mount_dict,
                print_trigger, temp_dir, serial_buffer_size,
                utf8, universal)
        self.files = files.Files(self.devices, max_files)
        # set LPT1 as target for print_screen()
        self.screen.set_print_screen_target(self.devices.lpt1_file)
        # set up rest of memory model
        self.all_memory = machine.Memory(self.memory, self.devices,
                            self.screen, self.keyboard, self.screen.fonts[8],
                            peek_values, syntax)
        # initialise the editor
        self.editor = editor.Editor(
                self.screen, self.keyboard, self.sound,
                self.output_redirection, self.devices.lpt1_file)
        # set up the SHELL command
        self.shell = shell.get_shell_manager(self.keyboard, self.screen, self.codepage, option_shell)
        # initialise random number generator
        self.randomiser = rnd.RandomNumberGenerator()
        # initialise system clock
        self.clock = clock.Clock()
        # initialise machine ports
        self.machine = machine.MachinePorts(self)
        # interpreter is executing a command (needs Screen)
        self._set_parse_mode(False)
        # direct line buffer
        self.direct_line = StringIO()
        # initialise the parser
        self.events.reset()
        self.parser = parser.Parser(self, syntax, pcjr_term, double)
        self.parser.set_pointer(False, 0)
        # set up debugger
        if option_debug:
            self.debugger = debug.Debugger(self)
        else:
            self.debugger = debug.BaseDebugger(self)

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, dummy_1, dummy_2, dummy_3):
        """Context guard."""
        self.close()

    def __getstate__(self):
        """Pickle the session."""
        # persist unplayed tones in sound queue
        self.tone_queue_store = [signals.save_queue(q) for q in self.tone_queue]
        pickle_dict = self.__dict__.copy()
        # remove queues from state
        pickle_dict['input_queue'] = signals.NullQueue()
        pickle_dict['video_queue'] = signals.NullQueue()
        pickle_dict['tone_queue'] = [signals.NullQueue()]*4
        pickle_dict['message_queue'] = signals.NullQueue()
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle and resume the session."""
        self.__dict__.update(pickle_dict)
        self.keyboard._input_closed = False
        # suppress double prompt
        if not self._parse_mode:
            self._prompt = False

    def attach(self, input_queue=None, video_queue=None,
                     tone_queue=None, message_queue=None):
        """Attach interface to interpreter session."""
        # use dummy queues if not provided
        self.input_queue = input_queue or signals.NullQueue()
        self.video_queue = video_queue or signals.NullQueue()
        self.tone_queue = tone_queue or [signals.NullQueue()]*4
        self.message_queue = message_queue or signals.NullQueue()
        # rebuild the screen
        self.screen.rebuild()
        # rebuild the audio queue
        for q, store in zip(self.tone_queue, self.tone_queue_store):
            signals.load_queue(q, store)
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
            with self._handle_exceptions():
                self._store_line(cmd)
                self._loop()

    def evaluate(self, expression):
        """Evaluate a BASIC expression."""
        with self._handle_exceptions():
            # attach print token so tokeniser has a whole statement to work with
            tokens = self.tokeniser.tokenise_line('?' + expression)
            # skip : and print token and parse expression
            tokens.read(2)
            return var.to_value(self.parser.parse_expression(tokens, self), self.strings)
        return None

    def set_variable(self, name, value):
        """Set a variable in memory."""
        if '(' in name:
            name = name.split('(', 1)[0]
            var.build_array(value, name, self.strings, self.arrays)
        else:
            self.memory.set_variable(name, [], var.from_value(value, name[-1], self.strings))

    def get_variable(self, name):
        """Get a variable in memory."""
        if '(' in name:
            name = name.split('(', 1)[0]
            return var.build_list(name, self.strings, self.arrays)
        else:
            return var.to_value(self.memory.get_variable(name, []), self.strings)

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

    def pause(self, message):
        """Pause the session and wait for a key."""
        self.video_queue.put(signals.Event(signals.VIDEO_SET_CAPTION, message))
        self.video_queue.put(signals.Event(signals.VIDEO_SHOW_CURSOR, False))
        while True:
            signal = self.input_queue.get()
            if signal.event_type == signals.KEYB_DOWN:
                break

    def close(self):
        """Close the session."""
        # close files if we opened any
        self.files.close_all()
        self.devices.close()
        # close interface
        self.video_queue.put(signals.Event(signals.VIDEO_QUIT))
        self.message_queue.put(signals.Event(signals.AUDIO_QUIT))

    ###########################################################################
    # implementation

    def _loop(self):
        """Run read-eval-print loop until control returns to user."""
        self.screen.cursor.reset_visibility()
        while True:
            last_parse = self._parse_mode
            if self._parse_mode:
                try:
                    # may raise Break
                    self.events.check_events()
                    # returns True if more statements to parse
                    if not self.parser.parse_statement():
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
                self.parser.set_pointer(False, 0)
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
        self.direct_line = self.tokeniser.tokenise_line(line)
        c = util.peek(self.direct_line)
        if c == '\0':
            # check for lines starting with numbers (6553 6) and empty lines
            self.program.check_number_start(self.direct_line)
            self.program.store_line(self.direct_line)
            # clear all program stacks
            self.parser.clear_stacks_and_pointers()
            self.clear()
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
        self.direct_line = self.tokeniser.tokenise_line(line)
        c = util.peek(self.direct_line)
        if c == '\0':
            # check for lines starting with numbers (6553 6) and empty lines
            empty, scanline = self.program.check_number_start(self.direct_line)
            if not empty:
                self.program.store_line(self.direct_line)
                # clear all program stacks
                self.parser.clear_stacks_and_pointers()
                self.clear()
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
            self.parser.error_num = 0
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
        if self.parser.run_mode:
            pos = self.program.bytecode.tell()-1
            self.parser.stop = pos
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

    def clear(self, close_files=False,
              preserve_common=False, preserve_all=False, preserve_deftype=False):
        """Execute a CLEAR command."""
        #   Resets the stack and string space
        #   Clears all COMMON and user variables
        if preserve_all:
            self.memory.clear_variables(self.memory.scalars.variables, self.memory.arrays.arrays)
        else:
            if not preserve_common:
                # at least I think these should be cleared by CLEAR?
                self.common_scalars = set()
                self.common_arrays = set()
            self.memory.clear_variables(self.common_scalars, self.common_arrays)
            # functions are cleared except when CHAIN ... ALL is specified
            self.user_functions = {}
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
        self.stick.switch(False)
        # reset sound and PLAY state
        self.sound.reset()
        # reset DRAW state (angle, scale) and current graphics position
        self.screen.drawing.reset()
        self.parser.clear()
