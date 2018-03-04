"""
PC-BASIC - dos.py
Operating system shell and environment

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import subprocess
import logging
import threading
import time
import locale
import platform

try:
    import pexpect
except ImportError:
    pexpect = None

from .base import error
from . import values


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

def get_shell_manager(keyboard, screen, codepage, shell_command, syntax):
    """Return a new shell manager object."""
    if syntax == 'pcjr':
        return ErrorShell()
    if shell_command:
        if platform.system() == 'Windows':
            return WindowsShell(keyboard, screen, codepage, shell_command)
        else:
            try:
                return Shell(keyboard, screen, codepage, shell_command)
            except InitFailed:
                logging.warning('Pexpect module not found. SHELL statement disabled.')
    return ShellBase()


class ShellBase(object):
    """Launcher for command shell."""

    def launch(self, command):
        """Launch the shell."""
        logging.warning(b'SHELL statement disabled.')


class ErrorShell(ShellBase):
    """Launcher to throw IFC."""

    def launch(self, command):
        """Launch the shell."""
        raise error.BASICError(error.IFC)


class WindowsShell(ShellBase):
    """Launcher for Windows CMD shell."""

    def __init__(self, keyboard, screen, codepage, shell_command):
        """Initialise the shell."""
        self.keyboard = keyboard
        self.screen = screen
        self.command = shell_command
        self.codepage = codepage
        self._encoding = locale.getpreferredencoding()

    def _process_stdout(self, stream, shell_output):
        """Retrieve SHELL output and write to console."""
        while True:
            # blocking read
            c = stream.read(1)
            if c:
                # don't access screen in this thread
                # the other thread already does
                shell_output.append(c)
            else:
                # don't hog cpu, sleep 1 ms
                time.sleep(0.001)

    def launch(self, command):
        """Run a SHELL subprocess."""
        shell_output = []
        cmd = self.command
        if command:
            cmd += u' /C ' + self.codepage.str_to_unicode(command)
        p = subprocess.Popen(cmd.encode(self._encoding).split(), stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        outp = threading.Thread(target=self._process_stdout, args=(p.stdout, shell_output))
        outp.daemon = True
        outp.start()
        errp = threading.Thread(target=self._process_stdout, args=(p.stderr, shell_output))
        errp.daemon = True
        errp.start()
        word = b''
        while p.poll() is None or shell_output:
            if shell_output:
                lines, shell_output[:] = b''.join(shell_output).split('\r\n'), []
                last = lines.pop()
                for line in lines:
                    self.screen.write_line(self.codepage.str_from_unicode(line.decode(self._encoding)))
                self.screen.write(self.codepage.str_from_unicode(last.decode(self._encoding)))
            if p.poll() is not None:
                # drain output then break
                continue
            try:
                # expand=False suppresses key macros
                c = self.keyboard.get_fullchar(expand=False)
            except error.Break:
                pass
            if c in (b'\r', b'\n'):
                # shift the cursor left so that CMD.EXE's echo can overwrite
                # the command that's already there. Note that Wine's CMD.EXE
                # doesn't echo the command, so it's overwritten by the output...
                self.screen.write(b'\x1D' * len(word))
                p.stdin.write(self.codepage.str_to_unicode(word + b'\r\n', preserve_control=True).encode(self._encoding))
                word = b''
            elif c == b'\b':
                # handle backspace
                if word:
                    word = word[:-1]
                    self.screen.write(b'\x1D \x1D')
            elif c != b'':
                # only send to pipe when enter is pressed
                # needed for Wine and to handle backspace properly
                word += c
                self.screen.write(c)


class Shell(ShellBase):
    """Launcher for Unix shell."""

    def __init__(self, keyboard, screen, codepage, shell_command):
        """Initialise the shell."""
        if not pexpect:
            raise InitFailed()
        self.keyboard = keyboard
        self.screen = screen
        self.command = shell_command
        self.codepage = codepage
        self._encoding = locale.getpreferredencoding()

    def launch(self, command):
        """Run a SHELL subprocess."""
        cmd = self.command
        if command:
            cmd += u' -c "' + self.codepage.str_to_unicode(command) + u'"'
        p = pexpect.spawn(cmd.encode(self._encoding))
        while True:
            try:
                # expand=False suppresses key macros
                c = self.keyboard.get_char(expand=False)
            except error.Break:
                # ignore ctrl+break in SHELL
                pass
            if c == b'\b':
                p.send(b'\x7f')
            elif c < b' ':
                p.send(c.encode(self._encoding))
            elif c != b'':
                c = self.codepage.to_unicode(c).encode(self._encoding)
                p.send(c)
            while True:
                try:
                    c = p.read_nonblocking(1, timeout=0).decode(self._encoding)
                except:
                    c = u''
                if c == u'' or c == u'\n':
                    break
                elif c == u'\r':
                    self.screen.write_line()
                elif c == u'\b':
                    if self.screen.current_col != 1:
                        self.screen.set_pos(
                                self.screen.current_row,
                                self.screen.current_col-1)
                else:
                    self.screen.write(self.codepage.from_unicode(c))
            if c == u'' and not p.isalive():
                return
