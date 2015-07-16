"""
PC-BASIC - shell.py
Operating system shell and environment

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import os
import subprocess
import logging

import plat
import config
import state
import error
import console
import backend

if plat.system == 'Windows':
    import threading
    import time
else:
    try:
        import pexpect
    except ImportError:
        pexpect = None


shell_enabled = False

native_shell = {
    'Windows': 'CMD.EXE',
    'OSX': '/bin/sh',
    'Linux': '/bin/sh',
    'Unknown_OS': '/bin/sh' }

def prepare():
    """ Initialise shell module. """
    global shell_enabled, shell_command
    if config.options['shell'] and config.options['shell'] != 'none':
        if (plat.system == 'Windows' or pexpect):
            shell_enabled = True
            if config.options['shell'] == 'native':
                shell_command = native_shell[plat.system]
            else:
                shell_command = config.options['shell']
        else:
            logging.warning('Pexpect module not found. SHELL command disabled.')

#########################################
# calling shell environment

def get_env(parm):
    """ Retrieve environment string by name. """
    if not parm:
        raise error.RunError(5)
    return bytearray(os.getenv(str(parm)) or '')

def get_env_entry(expr):
    """ Retrieve environment string by number. """
    envlist = list(os.environ)
    if expr > len(envlist):
        return bytearray()
    else:
        return bytearray(envlist[expr-1] + '=' + os.getenv(envlist[expr-1]))


#########################################
# shell

def shell(command):
    """ Execute a shell command or enter interactive shell. """
    # sound stops playing and is forgotten
    state.console_state.sound.stop_all_sound()
    # no key macros
    key_macros_save = state.basic_state.key_macros_off
    state.basic_state.key_macros_off = True
    # no user events
    suspend_event_save = state.basic_state.events.suspend_all
    state.basic_state.events.suspend_all = True
    # run the os-specific shell
    if shell_enabled:
        spawn_shell(command)
    else:
        logging.warning('SHELL statement disabled.')
    # re-enable key macros and event handling
    state.basic_state.key_macros_off = key_macros_save
    state.basic_state.events.suspend_all = suspend_event_save


if plat.system == 'Windows':
    shell_output = ''

    def process_stdout(p, stream):
        """ Retrieve SHELL output and write to console. """
        global shell_output
        while True:
            c = stream.read(1)
            if c != '':
                # don't access screen in this thread
                # the other thread already does
                shell_output += c
            elif p.poll() != None:
                break
            else:
                # don't hog cpu, sleep 1 ms
                time.sleep(0.001)

    def spawn_shell(command):
        """ Run a SHELL subprocess. """
        global shell_output
        cmd = shell_command
        if command:
            cmd += ' /C "' + command + '"'
        p = subprocess.Popen( str(cmd).split(), stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        outp = threading.Thread(target=process_stdout, args=(p, p.stdout))
        outp.daemon = True
        outp.start()
        errp = threading.Thread(target=process_stdout, args=(p, p.stderr))
        errp.daemon = True
        errp.start()
        word = ''
        while p.poll() == None or shell_output:
            if shell_output:
                lines, shell_output = shell_output.split('\r\n'), ''
                last = lines.pop()
                for line in lines:
                    # progress visible - keep updating the backend
                    # don't process anything but video events here
                    backend.video.check_events()
                    console.write_line(line)
                console.write(last)
            if p.poll() != None:
                # drain output then break
                continue
            try:
                c = state.console_state.keyb.get_char()
            except error.Break:
                pass
            if c in ('\r', '\n'):
                # shift the cursor left so that CMD.EXE's echo can overwrite
                # the command that's already there. Note that Wine's CMD.EXE
                # doesn't echo the command, so it's overwritten by the output...
                console.write('\x1D' * len(word))
                p.stdin.write(word + '\r\n')
                word = ''
            elif c == '\b':
                # handle backspace
                if word:
                    word = word[:-1]
                    console.write('\x1D \x1D')
            elif c != '':
                # only send to pipe when enter is pressed
                # needed for Wine and to handle backspace properly
                word += c
                console.write(c)
        outp.join()
        errp.join()

else:
    def spawn_shell(command):
        """ Run a SHELL subprocess. """
        cmd = shell_command
        if command:
            cmd += ' -c "' + command + '"'
        p = pexpect.spawn(str(cmd))
        while True:
            try:
                c = state.console_state.keyb.get_char()
            except error.Break:
                # ignore ctrl+break in SHELL
                pass
            if c == '\b': # BACKSPACE
                p.send('\x7f')
            elif c != '':
                p.send(c)
            while True:
                try:
                    c = p.read_nonblocking(1, timeout=0)
                except:
                    c = ''
                if c == '' or c == '\n':
                    break
                elif c == '\r':
                    console.write_line()
                elif c == '\b':
                    if state.console_state.col != 1:
                        console.set_pos(state.console_state.row,
                                        state.console_state.col-1)
                else:
                    console.write(c)
            if c == '' and not p.isalive():
                return

prepare()
