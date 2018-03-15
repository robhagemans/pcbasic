"""
PC-BASIC - dos.py
Operating system shell and environment

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import logging
import threading
import time
import re
from collections import deque
import subprocess
from subprocess import Popen, PIPE

from ..compat import WIN32, SHELL_ENCODING
from .base import error
from . import values


# delay for input threads, in seconds
DELAY = 0.001

if WIN32:
    # cmd.exe conventions, should also be used by other shells
    SHELL_COMMAND_SWITCH = u'/C'
    # the shell echoes its input
    SHELL_ECHOES = True
    # CRLF end-of-line
    EOL = b'\r\n'
    # avoid haveing an empty CMD window popping up in front of ours
    HIDE_WINDOW = subprocess.STARTUPINFO()
    HIDE_WINDOW.dwFlags |= 1  # STARTF_USESHOWWINDOW
    HIDE_WINDOW.wShowWindow = 0 # SW_HIDE
else:
    # sh conventions, standard on Unix
    SHELL_COMMAND_SWITCH = u'-c'
    # the does not echo its input
    SHELL_ECHOES = False
    # LF end-of-line
    EOL = b'\n'
    # not needed on Unix
    HIDE_WINDOW = None


def split_quoted(line, split_by=u'\s', quote=u'"'):
    """Split by separators, preserving quoted blocks."""
    return re.findall(ur'[^%s%s][^%s]*|%s.+?"' % (quote, split_by, split_by, quote), line)


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

class Shell(object):
    """Launcher for command shell."""

    def __init__(self, queues, keyboard, screen, codepage, shell):
        """Initialise the shell."""
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
        if not self._shell:
            logging.warning(b'SHELL statement not enabled: %s', self._warn)
            raise error.BASICError(error.IFC)
        shell_output = deque()
        shell_cerr = deque()
        cmd = split_quoted(self._shell)
        if command:
            cmd += [SHELL_COMMAND_SWITCH, self._codepage.str_to_unicode(command)]
        try:
            p = Popen(
                    cmd, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE, startupinfo=HIDE_WINDOW)
        except (EnvironmentError, UnicodeEncodeError) as e:
            logging.warning(u'SHELL: command interpreter `%s` not accessible: %s', self._shell, e)
            raise error.BASICError(error.IFC)
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
                if SHELL_ECHOES:
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
        bytes_word = b''.join(word) + EOL
        unicode_word = self._codepage.str_to_unicode(bytes_word, preserve_control=True)
        pipe.write(unicode_word.encode(SHELL_ENCODING, errors='replace'))

    def _show_output(self, shell_output):
        """Write shell output to screen."""
        if shell_output:
            lines = []
            while shell_output:
                lines.append(shell_output.popleft())
            lines = b''.join(lines).split(EOL)
            lines = (l.decode(SHELL_ENCODING, errors='replace') for l in lines)
            lines = (self._codepage.str_from_unicode(l, errors='replace') for l in lines)
            self._screen.write('\r'.join(lines))
