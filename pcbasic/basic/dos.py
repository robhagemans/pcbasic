"""
PC-BASIC - dos.py
Operating system shell and environment

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import subprocess
import logging
import threading
import time
import locale
from collections import deque

from .base import error
from . import values


# delay for input threads, in seconds
DELAY = 0.001

# the shell's encoding
ENCODING = locale.getpreferredencoding()


class InitFailed(Exception):
    """Shell object initialisation failed."""


#########################################
# calling shell environment

class Environment(object):
    """Handle environment changes."""

    def __init__(self, values):
        """Initialise."""
        self._values = values

    def environ_(self, args):
        """ENVIRON$: get environment string."""
        expr, = args
        if isinstance(expr, values.String):
            parm = expr.to_str()
            if not parm:
                raise error.BASICError(error.IFC)
            envstr = os.getenv(parm) or b''
        else:
            expr = values.to_int(expr)
            error.range_check(1, 255, expr)
            envlist = list(os.environ)
            if expr > len(envlist):
                envstr = ''
            else:
                envstr = '%s=%s' % (envlist[expr-1], os.getenv(envlist[expr-1]))
        return self._values.new_string().from_str(envstr)

    def environ_statement_(self, args):
        """ENVIRON: set environment string."""
        envstr = values.next_string(args)
        list(args)
        eqs = envstr.find('=')
        if eqs <= 0:
            raise error.BASICError(error.IFC)
        envvar = str(envstr[:eqs])
        val = str(envstr[eqs+1:])
        os.environ[envvar] = val


#########################################
# shell

def get_shell_manager(queues, keyboard, screen, codepage, shell, syntax):
    """Return a new shell manager object."""
    # move to shell_ generator
    if syntax == 'pcjr':
        return ErrorShell()
    try:
        if sys.platform == 'win32':
            return WindowsShell(queues, keyboard, screen, codepage, shell)
        else:
            return UnixShell(queues, keyboard, screen, codepage, shell)
    except InitFailed as e:
        #logging.warning(e)
        return ShellBase()


class ShellBase(object):
    """Launcher for command shell."""

    def launch(self, command):
        """Launch the shell."""
        logging.warning(b'SHELL statement disabled.')


# remove
class ErrorShell(ShellBase):
    """Launcher to throw IFC."""

    def launch(self, command):
        """Launch the shell."""
        raise error.BASICError(error.IFC)


class UnixShell(ShellBase):
    """Launcher for Unix shell."""

    _command_pattern = u'%s -c "%s"'
    _eol = b'\n'
    _echoes = False

    def __init__(self, queues, keyboard, screen, codepage, shell):
        """Initialise the shell."""
        if not shell:
            raise InitFailed()
        # need shell=True, command seems to be a shell feature
        # shouldn't we check for existence of an executable instead?
        # since below we run with shell=False
        if subprocess.call(b'command -v %s >/dev/null 2>&1' % (shell,), shell=True) != 0:
            raise InitFailed()
        self._shell = shell
        self._queues = queues
        self._keyboard = keyboard
        self._screen = screen
        self._codepage = codepage

    def _process_stdout(self, stream, output):
        """Retrieve SHELL output and write to console."""
        while True:
            # blocking read
            c = stream.read(1)
            if c:
                # don't access screen in this thread
                # the other thread already does
                output.append(c)
            else:
                # don't hog cpu, sleep 1 ms
                time.sleep(DELAY)

    def launch(self, command):
        """Run a SHELL subprocess."""
        shell_output = deque()
        shell_cerr = deque()
        cmd = self._shell
        if command:
            cmd = self._command_pattern % (self._shell, self._codepage.str_to_unicode(command))
        p = subprocess.Popen(
                cmd.encode(ENCODING).split(), shell=False,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        outp = threading.Thread(target=self._process_stdout, args=(p.stdout, shell_output))
        # daemonise or join later?
        outp.daemon = True
        outp.start()
        errp = threading.Thread(target=self._process_stdout, args=(p.stderr, shell_cerr))
        errp.daemon = True
        errp.start()
        word = []
        while p.poll() is None or shell_output or shell_cerr:
            self._show_output(shell_output)
            self._show_output(shell_cerr)
            if p.poll() is not None:
                # drain output then break
                continue
            try:
                self._queues.wait()
                # expand=False suppresses key macros
                c = self._keyboard.get_fullchar(expand=False)
            except error.Break:
                pass
            if not c:
                continue
            elif c in (b'\r', b'\n'):
                n_chars = len(word)
                # shift the cursor left so that CMD.EXE's echo can overwrite
                # the command that's already there.
                if self._echoes:
                    self._screen.write(b'\x1D' * len(word))
                else:
                    self._screen.write_line()
                # send line-buffered input to pipe
                self._send_input(p.stdin, word)
                word = []
            elif c == b'\b':
                # handle backspace
                if word:
                    word.pop()
                    self._screen.write(b'\x1D \x1D')
            elif not c.startswith(b'\0'):
                # exclude e-ascii (arrow keys not implemented)
                word.append(c)
                self._screen.write(c)

    def _send_input(self, pipe, word):
        """Write keyboard input to pipe."""
        bytes_word = b''.join(word) + self._eol
        unicode_word = self._codepage.str_to_unicode(bytes_word, preserve_control=True)
        pipe.write(unicode_word.encode(ENCODING))

    def _show_output(self, shell_output):
        """Write shell output to screen."""
        if shell_output:
            lines = []
            while shell_output:
                lines.append(shell_output.popleft())
            lines = b''.join(lines).split(self._eol)
            lines = [self._codepage.str_from_unicode(l.decode(ENCODING)) for l in lines]
            self._screen.write('\r'.join(lines))


class WindowsShell(UnixShell):
    """Launcher for Windows shell."""

    _command_pattern = u'%s /C "%s"'
    _eol = b'\r\n'
    _echoes = True

    def __init__(self, queues, keyboard, screen, codepage, shell):
        """Initialise the shell."""
        if not shell:
            raise InitFailed()
        self._shell = shell
        self._queues = queues
        self._keyboard = keyboard
        self._screen = screen
        self._codepage = codepage
