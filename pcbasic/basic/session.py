"""
PC-BASIC - interpreter.py
Main interpreter loop

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
import os
import sys
import logging
import time
import threading
import Queue
import platform
from contextlib import contextmanager
try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from . import error
from . import util
from . import tokenise

from . import program
from . import signals
from . import display
from . import console
from . import state
from . import inputs
from . import debug
from . import rnd
from . import timedate
from . import shell
from . import memory
from . import machine
from . import parser
from . import files
from . import sound
from . import redirect
from . import unicodepage


###############################################################################
# launcher

@contextmanager
def launch_session(session_params, state_file,
             commands, wait, prog, resume):
    """Launch a BASIC session in a separate thread."""
    # input queue
    input_queue = Queue.Queue()
    # video queue
    video_queue = Queue.Queue()
    # audio queues
    tone_queue = [Queue.Queue(), Queue.Queue(), Queue.Queue(), Queue.Queue()]
    message_queue = Queue.Queue()
    if resume:
        session = Session.resume(state_file,
                    input_queue, video_queue,
                    tone_queue, message_queue,
                    **session_params)
    else:
        session = Session(state_file,
                    input_queue, video_queue,
                    tone_queue, message_queue,
                    **session_params)
    thread = threading.Thread(target=run_thread, args=(session, prog, commands, wait))
    thread.start()
    yield session
    thread.join()

def run_thread(session, prog, commands, wait):
    """Thread runner for BASIC session."""
    try:
        run_session(session, prog, commands)
    finally:
        if wait:
            session.video_queue.put(signals.Event(signals.VIDEO_SET_CAPTION, 'Press a key to close window'))
            session.video_queue.put(signals.Event(signals.VIDEO_SHOW_CURSOR, False))
            while True:
                signal = session.input_queue.get()
                if signal.event_type == signals.KEYB_DOWN:
                    break
        # close interface
        session.video_queue.put(signals.Event(signals.VIDEO_QUIT))
        session.message_queue.put(signals.Event(signals.AUDIO_QUIT))

def run_session(session, prog, commands):
    """Manage BASIC session."""
    try:
        # load initial program, allowing native-os filenames or BASIC specs
        if prog:
            session.load_program(prog)
        for cmd in commands:
            session.execute(cmd)
        session.interact()
    except error.Exit:
        # SYSTEM called during launch
        pass
    except error.RunError as e:
        # only runtime errors that occur on interpreter launch are caught here
        # e.g. "File not Found" for --load parameter
        logging.error(e.message)
    finally:
        session.close()


###############################################################################
# interpreter session

tick_s = 0.0001
longtick_s = 0.006 - tick_s

class ResumeFailed(Exception):
    """Failed to resume session."""
    def __str__(self):
        return self.__doc__

class Session(object):
    """Interpreter session."""

    def __init__(self, state_file=u'',
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
            utf8=False, universal=True, echo_to_stdout=False,
            ignore_caps=True, ctrl_c_is_break=True,
            max_list_line=65535, allow_protect=False,
            allow_code_poke=False, max_memory=65534,
            max_reclen=128, max_files=3, reserved_memory=3429,
            temp_dir=u''):
        """Initialise the interpreter session."""
        # name of file to store and resume state
        self.state_file = state_file
        # input, video and audio queues
        # use dummy queues if not provided
        self.input_queue = input_queue or signals.NullQueue()
        self.video_queue = video_queue or signals.NullQueue()
        self.tone_queue = tone_queue or signals.NullQueue()
        self.message_queue = message_queue or signals.NullQueue()
        # true if a prompt is needed on next cycle
        self.prompt = True
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
        if echo_to_stdout:
            filter_stream = unicodepage.CodecStream(
                    sys.stdout, self.codepage, sys.stdout.encoding or b'utf-8')
        else:
            filter_stream = None
        # prepare output redirection
        self.output_redirection = redirect.OutputRedirection(
                output_file, append, filter_stream)
        # prepare tokeniser
        self.tokeniser = tokenise.Tokeniser(syntax, option_debug)
        # initialise the program
        self.program = program.Program(self.tokeniser,
                max_list_line, allow_protect, allow_code_poke)
        # function key macros
        self.fkey_macros = console.FunctionKeyMacros(12 if syntax == 'tandy' else 10)
        # initialise sound queue
        # needs Session for wait() and queues only
        self.sound = sound.Sound(self, syntax)
        # Sound is needed for the beeps on \a
        # Session is only for queues and check_events() in Graphics (flood fill)
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
        # Session needed for wait() only
        self.keyboard = inputs.Keyboard(self, self.screen, self.fkey_macros,
                self.codepage, self.sound,
                keystring, input_file, ignore_caps, ctrl_c_is_break)
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
        # Session needed for wait()
        self.devices = files.Devices(
                self, self.memory.fields, self.screen, self.keyboard,
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
        # initialise the console
        self.console = console.Console(
                self.screen, self.keyboard, self.sound,
                self.output_redirection, self.devices.lpt1_file)
        # set up the SHELL command
        self.shell = shell.ShellBase(self.keyboard, self.screen)
        if option_shell != 'none':
            if option_shell == 'native':
                shell_command = None
            else:
                shell_command = option_shell
            if platform.system() == 'Windows':
                self.shell = shell.WindowsShell(self.keyboard, self.screen, self.codepage, shell_command)
            else:
                try:
                    self.shell = shell.Shell(self.keyboard, self.screen, self.codepage, shell_command)
                except shell.InitFailed:
                    logging.warning('Pexpect module not found. SHELL statement disabled.')
        # initialise random number generator
        self.randomiser = rnd.RandomNumberGenerator()
        # initialise timer
        self.timer = timedate.Timer()
        # initialise machine ports
        self.machine = machine.MachinePorts(self)
        # interpreter is executing a command (needs Screen)
        self._set_parse_mode(False)
        # direct line buffer
        self.direct_line = StringIO()
        # initialise the parser
        self.parser = parser.Parser(self, syntax, pcjr_term, double)
        # set up debugger
        if option_debug:
            self.debugger = debug.Debugger(self)
        else:
            self.debugger = debug.BaseDebugger(self)

    def close(self):
        """Close and save the session."""
        self.store()
        # close files if we opened any
        self.files.close_all()
        self.devices.close()

    def store(self):
        """Save the session."""
        # persist unplayed tones in sound queue
        self.tone_queue_store = [signals.save_queue(q) for q in self.tone_queue]
        if self.state_file:
            # pickle and compress
            try:
                with open(self.state_file, 'wb') as f:
                    state.zpickle(self, f)
            except EnvironmentError:
                logging.warning("Could not write to state file %s. Emulator state not saved.", self.state_file)

    @classmethod
    def resume(cls, state_file,
                input_queue=None, video_queue=None,
                tone_queue=None, message_queue=None,
                override_cas1=None, override_mount=None,
                override_current_device='Z'):
        """Resume a saved interpreter session."""
        if not state_file:
            raise ResumeFailed()
        try:
            with open(state_file, 'rb') as f:
                self = state.zunpickle(f)
        except EnvironmentError:
            logging.warning("Could not read state file %s. Emulator state not loaded.", state_file)
            raise ResumeFailed()
        if not isinstance(self, cls):
            raise ResumeFailed()
        self.state_file = state_file
        self.input_queue = input_queue
        self.video_queue = video_queue
        self.tone_queue = tone_queue
        self.message_queue = message_queue
        # reload the screen in resumed state
        if not self.screen.resume():
            raise ResumeFailed()
        # rebuild the audio queue
        for q, store in zip(self.tone_queue, self.tone_queue_store):
            signals.load_queue(q, store)
        # override selected settings from command line
        self.devices.resume(override_cas1, override_mount, override_current_device)
        # suppress double prompt
        if not self.parse_mode:
            self.prompt = False
        return self

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

    ###########################################################################

    def load_program(self, prog, rebuild_dict=True):
        """Load a program from native or BASIC file."""
        with self.files.open_native_or_basic(
                    prog, filetype='ABP',
                    mode='I') as progfile:
            self.program.load(progfile, rebuild_dict=rebuild_dict)

    def save_program(self, prog, filetype):
        """Save a program to native or BASIC file."""
        with self.files.open_native_or_basic(
                    prog, filetype=filetype,
                    mode='O') as progfile:
            self.program.save(progfile)

    def execute(self, command):
        """Execute a BASIC statement."""
        for cmd in command.splitlines():
            self._store_line(cmd)
            self._loop()

    def interact(self):
        """Interactive interpreter session."""
        try:
            while True:
                self._loop()
                self._show_prompt()
                try:
                    # input loop, checks events
                    line = self.console.wait_screenline(from_start=True)
                    self.prompt = not self._store_line(line)
                except error.Break:
                    self.sound.stop_all_sound()
                    self.prompt = False
        except error.Exit:
            pass

    def _loop(self):
        """Run read-eval-print loop until control returns to user."""
        try:
            self.parser.set_pointer(False, 0)
            self.screen.cursor.reset_visibility()
            while True:
                last_parse = self.parse_mode
                if self.parse_mode:
                    try:
                        # may raise Break
                        self.check_events()
                        # returns True if more statements to parse
                        if not self.parser.parse_statement():
                            self.parse_mode = False
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
                if self.parse_mode != last_parse:
                    # move pointer to the start of direct line (for both on and off!)
                    self.parser.set_pointer(False, 0)
                    self.screen.cursor.reset_visibility()
                # return control to user
                if ((not self.auto_mode) and (not self.parse_mode)):
                    break
        except error.RunError as e:
            self._handle_error(e)
            self.prompt = True
        except error.Exit:
            raise
        except Exception as e:
            self.debugger.bluescreen(e)

    def _set_parse_mode(self, on):
        """Enter or exit parse mode."""
        self.parse_mode = on
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
        return not self.parse_mode

    def _show_prompt(self):
        """Show the Ok or EDIT prompt, unless suppressed."""
        if self.parse_mode:
            return
        if self.edit_prompt:
            linenum, tell = self.edit_prompt
            self.program.edit(self.console, linenum, tell)
            self.edit_prompt = False
        elif self.prompt:
            self.screen.start_line()
            self.screen.write_line("Ok\xff")

    def _auto_step(self):
        """Generate an AUTO line number and wait for input."""
        numstr = str(self.auto_linenum)
        self.screen.write(numstr)
        if self.auto_linenum in self.program.line_numbers:
            self.screen.write('*')
            line = bytearray(self.console.wait_screenline(from_start=True))
            if line[:len(numstr)+1] == numstr+'*':
                line[len(numstr)] = ' '
        else:
            self.screen.write(' ')
            line = bytearray(self.console.wait_screenline(from_start=True))
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
            if e.pos != -1:
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
            pos = self.program.bytecode.tell()
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

    ##########################################################################
    # main event checker

    def wait(self, suppress_events=False):
        """Wait and check events."""
        time.sleep(longtick_s)
        if not suppress_events:
            self.check_events()

    def check_events(self):
        """Main event cycle."""
        time.sleep(tick_s)
        self._check_input()
        self.parser.events.check()
        self.keyboard.drain_event_buffer()

    def _check_input(self):
        """Handle input events."""
        while True:
            try:
                signal = self.input_queue.get(False)
            except Queue.Empty:
                if not self.keyboard.pause:
                    break
                else:
                    time.sleep(tick_s)
                    continue
            # we're on it
            self.input_queue.task_done()
            if signal.event_type == signals.KEYB_QUIT:
                raise error.Exit()
            if signal.event_type == signals.KEYB_CLOSED:
                self.keyboard.close_input()
            elif signal.event_type == signals.KEYB_CHAR:
                # params is a unicode sequence
                self.keyboard.insert_chars(*signal.params)
            elif signal.event_type == signals.KEYB_DOWN:
                # params is e-ASCII/unicode character sequence, scancode, modifier
                self.keyboard.key_down(*signal.params)
            elif signal.event_type == signals.KEYB_UP:
                self.keyboard.key_up(*signal.params)
            elif signal.event_type == signals.PEN_DOWN:
                self.pen.down(*signal.params)
            elif signal.event_type == signals.PEN_UP:
                self.pen.up()
            elif signal.event_type == signals.PEN_MOVED:
                self.pen.moved(*signal.params)
            elif signal.event_type == signals.STICK_DOWN:
                self.stick.down(*signal.params)
            elif signal.event_type == signals.STICK_UP:
                self.stick.up(*signal.params)
            elif signal.event_type == signals.STICK_MOVED:
                self.stick.moved(*signal.params)
            elif signal.event_type == signals.CLIP_PASTE:
                self.keyboard.insert_chars(*signal.params, check_full=False)
            elif signal.event_type == signals.CLIP_COPY:
                text = self.screen.get_text(*(signal.params[:4]))
                self.video_queue.put(signals.Event(
                        signals.VIDEO_SET_CLIPBOARD_TEXT, (text, signal.params[-1])))
