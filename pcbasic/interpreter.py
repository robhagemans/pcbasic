"""
PC-BASIC - interpreter.py
Main interpreter loop

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import logging
import time
import threading
import Queue

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import plat
import error
import util
import tokenise
import program
import signals
import display
import console
import state
# prepare input state
import inputs
import debug
import config
import devices
import cassette
import disk
import rnd
import timedate
import shell
import memory
import machine
import parser
import files
import typeface


class SessionLauncher(object):
    """ Launches a BASIC session. """

    def __init__(self):
        """ Initialise launch parameters. """
        self.quit = config.get('quit')
        self.wait = config.get('wait')
        self.cmd = config.get('exec')
        self.prog = config.get(0) or config.get('run') or config.get('load')
        self.run = (config.get(0) != '') or (config.get('run') != '')
        self.resume = config.get('resume')
        # following GW, don't write greeting for redirected input
        # or command-line filter run
        self.show_greeting = (not self.run and not self.cmd and
            not config.get('input') and not config.get('interface') == 'none')
        if self.resume:
            self.cmd, self.run = '', False

    def __enter__(self):
        """ Resume or start the session. """
        if self.resume and state.load():
            state.session.resume()
        else:
            state.session = Session()
            # load initial program, allowing native-os filenames or BASIC specs
            if self.prog:
                with state.session.files.open_native_or_basic(self.prog) as progfile:
                    state.session.program.load(progfile)
            if self.show_greeting:
                state.session.greet()
        self.thread = threading.Thread(target=state.session.run,
                                args=(self.cmd, self.run, self.quit, self.wait))
        self.thread.start()

    def __exit__(self, dummy_one, dummy_two, dummy_three):
        """ Wait for the interpreter to exit. """
        if self.thread and self.thread.is_alive():
            # request exit
            signals.input_queue.put(signals.Event(signals.KEYB_QUIT))
            # wait for thread to finish
            self.thread.join()


###############################################################################
# interpreter session

tick_s = 0.0001
longtick_s = 0.006 - tick_s


class ResumeFailed(Exception):
    """ Failed to resume session. """
    def __str__(self):
        return self.__doc__


class Session(object):
    """ Interpreter session. """

    def __init__(self):
        """ Initialise the interpreter session. """
        # true if a prompt is needed on next cycle
        self.prompt = True
        # input mode is AUTO (used by AUTO)
        self.auto_mode = False
        self.auto_linenum = 10
        self.auto_increment = 10
        # interpreter is waiting for INPUT or LINE INPUT
        self.input_mode = False
        # previous interpreter mode
        self.last_mode = False, False
        # syntax error prompt and EDIT
        self.edit_prompt = False

        # set initial video mode
        monitor = config.get('monitor')
        video_capabilities = config.get('video')
        state.console_state.screen = display.Screen(config.get('text-width'),
                config.get('video-memory'), video_capabilities, monitor)
        heights_needed = set([8])
        for mode in state.console_state.screen.text_data.values():
            heights_needed.add(mode.font_height)
        for mode in state.console_state.screen.mode_data.values():
            heights_needed.add(mode.font_height)
        # load the graphics fonts, including the 8-pixel RAM font
        # use set() for speed - lookup is O(1) rather than O(n) for list
        chars_needed = set(state.console_state.codepage.cp_to_unicode.values())
        # break up any grapheme clusters and add components to set of needed glyphs
        chars_needed |= set(c for cluster in chars_needed if len(cluster) > 1 for c in cluster)
        state.console_state.fonts = typeface.load_fonts(config.get('font'), heights_needed,
                    chars_needed, state.console_state.codepage.substitutes, warn=config.get('debug'))
        # initialise a fresh textmode screen
        state.console_state.screen.set_mode(state.console_state.screen.mode, 0, 1, 0, 0)

        # interpreter is executing a command
        self.set_parse_mode(False)
        # initialise the console
        self.console = console.Console()
        # direct line buffer
        self.direct_line = StringIO()

        # program parameters
        if not config.get('strict-hidden-lines'):
            max_list_line = 65535
        else:
            max_list_line = 65530
        allow_protect = config.get('strict-protect')
        allow_code_poke = config.get('allow-code-poke')
        # initialise the program
        self.program = program.Program(max_list_line, allow_protect, allow_code_poke)

        # set up variables and memory model state
        # max available memory to BASIC (set by /m)
        max_list = config.get('max-memory')
        max_list[1] = max_list[1]*16 if max_list[1] else max_list[0]
        max_list[0] = max_list[0] or max_list[1]
        max_memory = min(max_list) or 65534
        # length of field record (by default 128)
        # maximum record length (-s)
        max_reclen = max(1, min(32767, config.get('max-reclen')))
        # number of file records
        max_files = config.get('max-files')
        # first field buffer address (workspace size; 3429 for gw-basic)
        reserved_memory = config.get('reserved-memory')
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
        self.devices = files.Devices(self, self.memory.fields)
        self.files = files.Files(self.devices, max_files)

        # set up rest of memory model
        peek_values = {}
        try:
            for a in config.get('peek'):
                seg, addr, val = a.split(':')
                peek_values[int(seg)*0x10 + int(addr)] = int(val)
        except (TypeError, ValueError):
            pass
        self.all_memory = machine.Memory(self.memory, self.devices,
                                        peek_values, config.get('syntax'))

        # initialise timer
        self.timer = timedate.Timer()

        # find program for PCjr TERM command
        pcjr_term = config.get('pcjr-term')
        if pcjr_term and not os.path.exists(pcjr_term):
            pcjr_term = os.path.join(plat.info_dir, pcjr_term)
        if not os.path.exists(pcjr_term):
            pcjr_term = ''
        # initialise the parser
        self.parser = parser.Parser(self, config.get('syntax'),
                                    pcjr_term, config.get('double'))

        # initialise random number generator
        self.randomiser = rnd.RandomNumberGenerator()
        # initialise machine ports
        self.machine = machine.MachinePorts(self)


        # TODO: these may not be necessary
        # stop all sound
        state.console_state.sound.stop_all_sound()
        # Resets STRIG to off
        state.console_state.stick.switch(False)
        # reset sound and PLAY state
        state.console_state.sound.reset()
        # reset DRAW state (angle, scale) and current graphics position
        state.console_state.screen.drawing.reset()

        # set up debugger
        if config.get('debug'):
            self.debugger = debug.Debugger(self)
        else:
            self.debugger = debug.BaseDebugger(self)

        # set up the SHELL command
        option_shell = config.get('shell')
        self.shell = shell.ShellBase()
        if option_shell != 'none':
            if option_shell == 'native':
                shell_command = None
            else:
                shell_command = option_shell
            if plat.system == 'Windows':
                self.shell = shell.WindowsShell(shell_command)
            else:
                try:
                    self.shell = shell.Shell(shell_command)
                except shell.InitFailed:
                    logging.warning('Pexpect module not found. SHELL statement disabled.')

    def greet(self):
        """ Show greeting and keys. """
        greeting = (
            'PC-BASIC {version}\r'
            '(C) Copyright 2013--2016 Rob Hagemans.\r'
            '{free} Bytes free')
        self.console.clear()
        self.console.write_line(greeting.format(
                version=plat.version,
                free=self.memory.get_free()))
        self.console.show_keys(True)

    def clear(self, close_files=False,
              preserve_common=False, preserve_all=False, preserve_deftype=False):
        """ Execute a CLEAR command. """
        #   Resets the stack and string space
        #   Clears all COMMON and user variables
        if not preserve_all:
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
        state.console_state.sound.stop_all_sound()
        # Resets STRIG to off
        state.console_state.stick.switch(False)
        # reset sound and PLAY state
        state.console_state.sound.reset()
        # reset DRAW state (angle, scale) and current graphics position
        state.console_state.screen.drawing.reset()
        self.parser.clear()

    def resume(self):
        """ Resume an interpreter session. """
        # resume from saved emulator state (if requested and available)
        # reload the screen in resumed state
        if not state.console_state.screen.resume():
            raise ResumeFailed()
        # rebuild the audio queue
        for q, store in zip(signals.tone_queue, state.console_state.tone_queue_store):
            signals.load_queue(q, store)
        # override selected settings from command line
        self.devices.resume()
        # suppress double prompt
        if not self.parse_mode:
            self.prompt = False


    ###########################################################################

    def run(self, command, run, quit, wait):
        """ Interactive interpreter session. """
        if command:
            self.store_line(command)
            self.loop()
        if run:
            # position the pointer at start of program and enter execute mode
            self.parser.jump(None)
            self.set_parse_mode(True)
            state.console_state.screen.cursor.reset_visibility()
        try:
            try:
                while True:
                    self.loop()
                    if quit and state.console_state.keyb.buf.is_empty():
                        break
            except error.Exit:
                # pause before exit if requested
                if wait:
                    signals.video_queue.put(signals.Event(signals.VIDEO_SET_CAPTION, 'Press a key to close window'))
                    signals.video_queue.put(signals.Event(signals.VIDEO_SHOW_CURSOR, False))
                    state.console_state.keyb.pause = True
                    # this performs a blocking keystroke read if in pause state
                    self.check_events()
            finally:
                # close interfaces
                signals.video_queue.put(signals.Event(signals.VIDEO_QUIT))
                signals.message_queue.put(signals.Event(signals.AUDIO_QUIT))
                # persist unplayed tones in sound queue
                state.console_state.tone_queue_store = [
                        signals.save_queue(q) for q in signals.tone_queue]
                state.save()
                # close files if we opened any
                self.files.close_all()
                self.devices.close()
        except error.Reset:
            # delete state if resetting
            state.delete()

    def loop(self):
        """ Run read-eval-print loop until control returns to user after a command. """
        try:
            while True:
                self.last_mode = self.parse_mode, self.auto_mode
                if self.parse_mode:
                    try:
                        # may raise Break
                        self.check_events()
                        # returns True if more statements to parse
                        if not self.parser.parse_statement():
                            self.parse_mode = False
                    except error.Break as e:
                        # ctrl-break stops foreground and background sound
                        state.console_state.sound.stop_all_sound()
                        self.handle_break(e)
                elif self.auto_mode:
                    try:
                        # auto step, checks events
                        self.auto_step()
                    except error.Break:
                        # ctrl+break, ctrl-c both stop background sound
                        state.console_state.sound.stop_all_sound()
                        self.auto_mode = False
                else:
                    self.show_prompt()
                    try:
                        # input loop, checks events
                        line = self.console.wait_screenline(from_start=True)
                        self.prompt = not self.store_line(line)
                    except error.Break:
                        state.console_state.sound.stop_all_sound()
                        self.prompt = False
                        continue
                # change loop modes
                if self.switch_mode():
                    break
        except error.RunError as e:
            self.handle_error(e)
            self.prompt = True
        except error.Exit:
            raise
        except error.Reset:
            raise
        except Exception as e:
            self.debugger.bluescreen(e)

    def set_parse_mode(self, on):
        """ Enter or exit parse mode. """
        self.parse_mode = on
        state.console_state.screen.cursor.default_visible = not on

    def switch_mode(self):
        """ Switch loop mode. """
        last_execute, last_auto = self.last_mode
        if self.parse_mode != last_execute:
            # move pointer to the start of direct line (for both on and off!)
            self.parser.set_pointer(False, 0)
            state.console_state.screen.cursor.reset_visibility()
        return ((not self.auto_mode) and
                (not self.parse_mode) and last_execute)

    def store_line(self, line):
        """ Store a program line or schedule a command line for execution. """
        if not line:
            return True
        self.direct_line = tokenise.tokenise_line(line)
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
            self.set_parse_mode(True)
        return not self.parse_mode

    def show_prompt(self):
        """ Show the Ok or EDIT prompt, unless suppressed. """
        if self.parse_mode:
            return
        if self.edit_prompt:
            linenum, tell = self.edit_prompt
            self.program.edit(linenum, tell)
            self.edit_prompt = False
        elif self.prompt:
            self.console.start_line()
            self.console.write_line("Ok\xff")

    def auto_step(self):
        """ Generate an AUTO line number and wait for input. """
        numstr = str(self.auto_linenum)
        self.console.write(numstr)
        if self.auto_linenum in self.program.line_numbers:
            self.console.write('*')
            line = bytearray(self.console.wait_screenline(from_start=True))
            if line[:len(numstr)+1] == numstr+'*':
                line[len(numstr)] = ' '
        else:
            self.console.write(' ')
            line = bytearray(self.console.wait_screenline(from_start=True))
        # run or store it; don't clear lines or raise undefined line number
        self.direct_line = tokenise.tokenise_line(line)
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
            self.set_parse_mode(True)


    ##############################################################################
    # error handling

    def handle_error(self, e):
        """ Handle a BASIC error through error message. """
        # not handled by ON ERROR, stop execution
        self.console.write_error_message(e.message, self.program.get_line_number(e.pos))
        self.set_parse_mode(False)
        self.input_mode = False
        # special case: syntax error
        if e.err == error.STX:
            # for some reason, err is reset to zero by GW-BASIC in this case.
            self.parser.error_num = 0
            if e.pos != -1:
                # line edit gadget appears
                self.edit_prompt = (self.program.get_line_number(e.pos), e.pos+1)

    def handle_break(self, e):
        """ Handle a Break event. """
        # print ^C at current position
        if not self.input_mode and not e.stop:
            self.console.write('^C')
        # if we're in a program, save pointer
        pos = -1
        if self.parser.run_mode:
            pos = self.program.bytecode.tell()
            self.parser.stop = pos
        self.console.write_error_message(e.message, self.program.get_line_number(pos))
        self.set_parse_mode(False)
        self.input_mode = False

    ##########################################################################
    # main event checker

    def wait(self, suppress_events=False):
        """ Wait and check events. """
        time.sleep(longtick_s)
        if not suppress_events:
            self.check_events()

    def check_events(self):
        """ Main event cycle. """
        time.sleep(tick_s)
        self._check_input()
        if self.parser.run_mode:
            self.parser.events.check()
        state.console_state.keyb.drain_event_buffer()

    def _check_input(self):
        """ Handle input events. """
        while True:
            try:
                signal = signals.input_queue.get(False)
            except Queue.Empty:
                if not state.console_state.keyb.pause:
                    break
                else:
                    time.sleep(tick_s)
                    continue
            # we're on it
            signals.input_queue.task_done()
            if signal.event_type == signals.KEYB_QUIT:
                raise error.Exit()
            if signal.event_type == signals.KEYB_CLOSED:
                state.console_state.keyb.close_input()
            elif signal.event_type == signals.KEYB_CHAR:
                # params is a unicode sequence
                state.console_state.keyb.insert_chars(*signal.params)
            elif signal.event_type == signals.KEYB_DOWN:
                # params is e-ASCII/unicode character sequence, scancode, modifier
                state.console_state.keyb.key_down(*signal.params)
            elif signal.event_type == signals.KEYB_UP:
                state.console_state.keyb.key_up(*signal.params)
            elif signal.event_type == signals.PEN_DOWN:
                state.console_state.pen.down(*signal.params)
            elif signal.event_type == signals.PEN_UP:
                state.console_state.pen.up()
            elif signal.event_type == signals.PEN_MOVED:
                state.console_state.pen.moved(*signal.params)
            elif signal.event_type == signals.STICK_DOWN:
                state.console_state.stick.down(*signal.params)
            elif signal.event_type == signals.STICK_UP:
                state.console_state.stick.up(*signal.params)
            elif signal.event_type == signals.STICK_MOVED:
                state.console_state.stick.moved(*signal.params)
            elif signal.event_type == signals.CLIP_PASTE:
                state.console_state.keyb.insert_chars(*signal.params, check_full=False)
            elif signal.event_type == signals.CLIP_COPY:
                text = state.console_state.screen.get_text(*(signal.params[:4]))
                signals.video_queue.put(signals.Event(
                        signals.VIDEO_SET_CLIPBOARD_TEXT, (text, signal.params[-1])))
