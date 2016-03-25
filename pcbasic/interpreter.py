"""
PC-BASIC - interpreter.py
Main interpreter loop

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import os
import sys
import traceback
import logging

import plat
import error
import util
import tokenise
import program
import statements
import console
import state
import backend
import reset
import flow
import debug
import config
import devices
import disk
import var

# true if a prompt is needed on next cycle
state.basic_state.prompt = True
# input mode is AUTO (used by AUTO)
state.basic_state.auto_mode = False
# interpreter is executing a command
state.basic_state.execute_mode = False
# interpreter is waiting for INPUT or LINE INPUT
state.basic_state.input_mode = False
# previous interpreter mode
state.basic_state.last_mode = False, False


def prepare():
    """ Initialise interpreter module. """
    global quit, wait, run, prog, cmd
    quit = config.get('quit')
    wait = config.get('wait')
    # load/run program
    run = config.get(0) or config.get('run')
    prog = run or config.get('load')
    cmd = config.get('exec')

def start():
    """ Start the interpreter. """
    if prog:
        # on load, accept capitalised versions and default extension
        with disk.open_native_or_dos_filename(prog) as progfile:
            program.load(progfile)
        # ensure memory model is up to date
        reset.clear()
    print_greeting(console)
    if cmd:
        store_line(cmd)
    if run:
        # run command before program
        if cmd:
            cycle()
        # position the pointer at start of program and enter execute mode
        flow.jump(None)
        state.basic_state.execute_mode = True
        state.console_state.screen.cursor.reset_visibility()
    loop()

def loop():
    """ Read-eval-print loop until quit or exception. """
    try:
        while True:
            cycle()
            if quit and state.console_state.keyb.buf.is_empty():
                break
    except error.Exit:
        # pause before exit if requested
        if wait:
            backend.video_queue.put(backend.Event(backend.VIDEO_SET_CAPTION, 'Press a key to close window'))
            backend.video_queue.put(backend.Event(backend.VIDEO_SHOW_CURSOR, False))
            state.console_state.keyb.pause = True
            # this performs a blocking keystroke read if in pause state
            backend.check_events()
    finally:
        state.save()
        try:
            # close files if we opened any
            devices.close_files()
        except (NameError, AttributeError) as e:
            logging.debug('Error on closing files: %s', e)
        try:
            devices.close_devices()
        except (NameError, AttributeError) as e:
            logging.debug('Error on closing devices: %s', e)

def cycle():
    """ Read-eval-print loop: run once. """
    try:
        while True:
            state.basic_state.last_mode = state.basic_state.execute_mode, state.basic_state.auto_mode
            if state.basic_state.execute_mode:
                try:
                    # may raise Break
                    backend.check_events()
                    handle_basic_events()
                    # returns True if more statements to parse
                    if not statements.parse_statement():
                        state.basic_state.execute_mode = False
                except error.RunError as e:
                    trap_error(e)
                except error.Break as e:
                    # ctrl-break stops foreground and background sound
                    state.console_state.sound.stop_all_sound()
                    handle_break(e)
            elif state.basic_state.auto_mode:
                try:
                    # auto step, checks events
                    auto_step()
                except error.Break:
                    # ctrl+break, ctrl-c both stop background sound
                    state.console_state.sound.stop_all_sound()
                    state.basic_state.auto_mode = False
            else:
                show_prompt()
                try:
                    # input loop, checks events
                    line = console.wait_screenline(from_start=True)
                    state.basic_state.prompt = not store_line(line)
                except error.Break:
                    state.console_state.sound.stop_all_sound()
                    state.basic_state.prompt = False
                    continue
            # change loop modes
            if switch_mode():
                break
    except error.RunError as e:
        handle_error(e)
        state.basic_state.prompt = True
    except error.Exit:
        raise
    except Exception as e:
        if debug.debug_mode:
            raise
        bluescreen(e)

def switch_mode():
    """ Switch loop mode. """
    last_execute, last_auto = state.basic_state.last_mode
    if state.basic_state.execute_mode != last_execute:
        # move pointer to the start of direct line (for both on and off!)
        flow.set_pointer(False, 0)
        state.console_state.screen.cursor.reset_visibility()
    return ((not state.basic_state.auto_mode) and
            (not state.basic_state.execute_mode) and last_execute)

def store_line(line):
    """ Store a program line or schedule a command line for execution. """
    if not line:
        return True
    state.basic_state.direct_line = tokenise.tokenise_line(line)
    c = util.peek(state.basic_state.direct_line)
    if c == '\0':
        # check for lines starting with numbers (6553 6) and empty lines
        program.check_number_start(state.basic_state.direct_line)
        program.store_line(state.basic_state.direct_line)
        reset.clear()
    elif c != '':
        # it is a command, go and execute
        state.basic_state.execute_mode = True
    return not state.basic_state.execute_mode

def print_greeting(console):
    """ Print the greeting and the KEY row if we're not running a program. """
    greeting = (
        'PC-BASIC {version} {note}\r'
        '(C) Copyright 2013--2016 Rob Hagemans.\r'
        '{free} Bytes free')
    # following GW, don't write greeting for redirected input
    # or command-line filter run
    if (not config.get('run') and not config.get('exec') and
             not config.get('input') and not config.get(0) and
             not config.get('interface') == 'none'):
        debugstr = ' [DEBUG mode]' if config.get('debug') else ''
        params = { 'version': plat.version, 'note': debugstr, 'free': var.fre()}
        console.clear()
        console.write_line(greeting.format(**params))
        console.show_keys(True)

def show_prompt():
    """ Show the Ok or EDIT prompt, unless suppressed. """
    if state.basic_state.execute_mode:
        return
    if state.basic_state.edit_prompt:
        linenum, tell = state.basic_state.edit_prompt
        program.edit(linenum, tell)
        state.basic_state.edit_prompt = False
    elif state.basic_state.prompt:
        console.start_line()
        console.write_line("Ok\xff")

def auto_step():
    """ Generate an AUTO line number and wait for input. """
    numstr = str(state.basic_state.auto_linenum)
    console.write(numstr)
    if state.basic_state.auto_linenum in state.basic_state.line_numbers:
        console.write('*')
        line = bytearray(console.wait_screenline(from_start=True))
        if line[:len(numstr)+1] == numstr+'*':
            line[len(numstr)] = ' '
    else:
        console.write(' ')
        line = bytearray(console.wait_screenline(from_start=True))
    # run or store it; don't clear lines or raise undefined line number
    state.basic_state.direct_line = tokenise.tokenise_line(line)
    c = util.peek(state.basic_state.direct_line)
    if c == '\0':
        # check for lines starting with numbers (6553 6) and empty lines
        empty, scanline = program.check_number_start(state.basic_state.direct_line)
        if not empty:
            program.store_line(state.basic_state.direct_line)
            reset.clear()
        state.basic_state.auto_linenum = scanline + state.basic_state.auto_increment
    elif c != '':
        # it is a command, go and execute
        state.basic_state.execute_mode = True


############################
# event and error handling

def handle_basic_events():
    """ Jump to user-defined event subs if events triggered. """
    if state.basic_state.events.suspend_all or not state.basic_state.run_mode:
        return
    for event in state.basic_state.events.all:
        if (event.enabled and event.triggered
                and not event.stopped and event.gosub is not None):
            # release trigger
            event.triggered = False
            # stop this event while handling it
            event.stopped = True
            # execute 'ON ... GOSUB' subroutine;
            # attach handler to allow un-stopping event on RETURN
            flow.jump_gosub(event.gosub, event)

def trap_error(e):
    """ Handle a BASIC error through trapping. """
    if e.pos is None:
        if state.basic_state.run_mode:
            e.pos = state.basic_state.bytecode.tell()-1
        else:
            e.pos = -1
    state.basic_state.errn = e.err
    state.basic_state.errp = e.pos
    # don't jump if we're already busy handling an error
    if state.basic_state.on_error is not None and state.basic_state.on_error != 0 and not state.basic_state.error_handle_mode:
        state.basic_state.error_resume = state.basic_state.current_statement, state.basic_state.run_mode
        flow.jump(state.basic_state.on_error)
        state.basic_state.error_handle_mode = True
        state.basic_state.events.suspend_all = True
    else:
        raise e

def handle_error(e):
    """ Handle a BASIC error through error message. """
    # not handled by ON ERROR, stop execution
    console.write_error_message(e.message, program.get_line_number(e.pos))
    state.basic_state.error_handle_mode = False
    state.basic_state.execute_mode = False
    state.basic_state.input_mode = False
    # special case: syntax error
    if e.err == error.STX:
        # for some reason, err is reset to zero by GW-BASIC in this case.
        state.basic_state.errn = 0
        if e.pos != -1:
            # line edit gadget appears
            state.basic_state.edit_prompt = (program.get_line_number(e.pos), e.pos+1)

def handle_break(e):
    """ Handle a Break event. """
    # print ^C at current position
    if not state.basic_state.input_mode and not e.stop:
        console.write('^C')
    # if we're in a program, save pointer
    pos = -1
    if state.basic_state.run_mode:
        pos = state.basic_state.bytecode.tell()
        state.basic_state.stop = pos
    console.write_error_message(e.message, program.get_line_number(pos))
    state.basic_state.execute_mode = False
    state.basic_state.input_mode = False

def bluescreen(e):
    """ Display a modal exception message. """
    state.console_state.screen.screen(0, 0, 0, 0, new_width=80)
    console.clear()
    console.init_mode()
    exc_type, exc_value, exc_traceback = sys.exc_info()
    # log the standard python error
    logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    # format the error more readably on the screen
    state.console_state.screen.set_border(4)
    state.console_state.screen.set_attr(0x70)
    console.write_line('EXCEPTION')
    state.console_state.screen.set_attr(15)
    if state.basic_state.run_mode:
        state.basic_state.bytecode.seek(-1, 1)
        program.edit(program.get_line_number(state.basic_state.bytecode.tell()),
                                         state.basic_state.bytecode.tell())
        console.write_line('\n')
    else:
        state.basic_state.direct_line.seek(0)
        console.write_line(str(tokenise.detokenise_compound_statement(state.basic_state.direct_line)[0])+'\n')
    stack = traceback.extract_tb(exc_traceback)
    for s in stack[-4:]:
        stack_line = '{0}:{1}, {2}'.format(
            os.path.split(s[0])[-1], s[1], s[2])
        stack_line_2 = '    {0}'.format(s[3])
        state.console_state.screen.set_attr(15)
        console.write_line(stack_line)
        state.console_state.screen.set_attr(7)
        console.write_line(stack_line_2)
    exc_message = traceback.format_exception_only(exc_type, exc_value)[0]
    state.console_state.screen.set_attr(15)
    console.write('{0}:'.format(exc_type.__name__))
    state.console_state.screen.set_attr(7)
    console.write_line(' {0}'.format(str(exc_value)))
    state.console_state.screen.set_attr(0x70)
    console.write_line(
        '\nThis is a bug in PC-BASIC.')
    state.console_state.screen.set_attr(7)
    console.write(
        'Sorry about that. Please send the above messages to the bugs forum\nby e-mail to ')
    state.console_state.screen.set_attr(15)
    console.write(
        'bugs@discussion.pcbasic.p.re.sf.net')
    state.console_state.screen.set_attr(7)
    console.write(
        ' or by filing a bug\nreport at ')
    state.console_state.screen.set_attr(15)
    console.write(
        'https://github.com/robhagemans/pcbasic/issues')
    state.console_state.screen.set_attr(7)
    console.write_line(
        '. Please include')
    console.write_line('as much information as you can about what you were doing and how this happened.')
    console.write_line('Thank you!')
    state.console_state.screen.set_attr(7)
    flow.set_pointer(False)


prepare()
