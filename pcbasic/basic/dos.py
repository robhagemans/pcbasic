"""
PC-BASIC - dos.py
Operating system shell and environment

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import logging
import threading
import time
from collections import deque
import subprocess
from subprocess import Popen, PIPE

from ..compat import SHELL_ENCODING, HIDE_WINDOW
from ..compat import which, split_quoted, getenvu, setenvu, iterenvu
from .codepage import CONTROL
from .base import error
from . import values


# command interpreter must support command.com convention
# to be able to use SHELL "dos-command"
# on linux, "wine cmd.exe" works OK
# dosemu can probably be made to work with a wrapper script
# sh doesn't work but makes little sense to use anyway as it's totally unlike MS-DOS
SHELL_COMMAND_SWITCH = u'/C'


##########################################
# calling shell environment

class Environment(object):
    """Handle environment changes."""

    def __init__(self, values, codepage):
        """Initialise."""
        self._values = values
        self._codepage = codepage

    def _setenv(self, key, value):
        """Set environment (bytes) key to (bytes) value."""
        assert isinstance(key, bytes), type(key)
        assert isinstance(value, bytes), type(value)
        # only accept ascii-128 for keys
        try:
            ukey = key.decode('ascii')
        except UnicodeError:
            raise error.BASICError(error.IFC)
        # enforce uppercase
        ukey = ukey.upper()
        uvalue = self._codepage.bytes_to_unicode(value)
        setenvu(ukey, uvalue)

    def _getenv(self, key):
        """Get environment (bytes) value or b''."""
        assert isinstance(key, bytes), type(key)
        # only accept ascii-128 for keys
        try:
            ukey = key.decode('ascii')
        except UnicodeError:
            raise error.BASICError(error.IFC)
        # enforce uppercase
        ukey = ukey.upper()
        return self._codepage.unicode_to_bytes(getenvu(ukey, u''))

    def _getenv_item(self, index):
        """Get environment (bytes) 'key=value' or b'', by zero-based index."""
        envlist = list(iterenvu())
        try:
            ukey = envlist[index]
        except IndexError:
            return b''
        else:
            key = self._codepage.unicode_to_bytes(ukey)
            value = self._codepage.unicode_to_bytes(getenvu(ukey, u''))
            return b'%s=%s' % (key, value)

    def environ_(self, args):
        """ENVIRON$: get environment string."""
        expr, = args
        if isinstance(expr, values.String):
            key = expr.to_str()
            if not key:
                raise error.BASICError(error.IFC)
            result = self._getenv(key)
        else:
            index = values.to_int(expr)
            error.range_check(1, 255, index)
            result = self._getenv_item(index-1)
        return self._values.new_string().from_str(result)

    def environ_statement_(self, args):
        """ENVIRON: set environment string."""
        envstr = values.next_string(args)
        list(args)
        eqs = envstr.find(b'=')
        if eqs <= 0:
            raise error.BASICError(error.IFC)
        self._setenv(envstr[:eqs], envstr[eqs+1:])


#########################################
# shell

class Shell(object):
    """Launcher for command shell."""

    def __init__(self, queues, keyboard, console, files, codepage, shell):
        """Initialise the shell."""
        self._shell = shell
        self._queues = queues
        self._keyboard = keyboard
        self._console = console
        self._files = files
        self._codepage = codepage
        self._last_command = deque()
        self._encoding = None

    def _process_stdout(self, stream, output):
        """Retrieve SHELL output and write to console."""
        while True:
            # blocking read
            c = stream.read(1)
            # stream ends if process closes
            if not c:
                return
            # don't access console in this thread
            # the other thread already does
            output.append(c)

    def launch(self, command):
        """Run a SHELL subprocess."""
        logging.debug('Executing SHELL command `%r` with command interpreter `%s`', command, self._shell)
        if not self._shell:
            logging.warning('SHELL statement not enabled: no command interpreter specified.')
            raise error.BASICError(error.IFC)
        # split by whitespace but protect quotes
        cmd = split_quoted(self._shell, quote=u'"', strip_quotes=False)
        # find executable on path
        cmd[0] = which(cmd[0], path='.' + os.pathsep + os.environ.get("PATH"))
        if not cmd[0]:
            logging.warning(u'SHELL: command interpreter `%s` not found.', self._shell)
            raise error.BASICError(error.IFC)
        if command:
            cmd += [SHELL_COMMAND_SWITCH, self._codepage.bytes_to_unicode(command, box_protect=False)]
        # get working directory; also raises IFC if current_device is CAS1
        work_dir = self._files.get_native_cwd()
        try:
            p = Popen(
                cmd, shell=False, cwd=work_dir,
                stdin=PIPE, stdout=PIPE, stderr=PIPE,
                # first try with HIDE_WINDOW to avoid ugly command window popping up on windows
                startupinfo=HIDE_WINDOW
            )
        except EnvironmentError:
            try:
                # HIDE_WINDOW not allowed on Windows when called from console
                p = Popen(
                    cmd, shell=False, cwd=work_dir,
                    stdin=PIPE, stdout=PIPE, stderr=PIPE,
                )
            except EnvironmentError as err:
                logging.warning(
                    u'SHELL: command interpreter `%s` not accessible: %s', self._shell, err
                )
                raise error.BASICError(error.IFC)
        shell_output = self._launch_reader_thread(p.stdout)
        shell_cerr = self._launch_reader_thread(p.stderr)
        try:
            self._communicate(p, shell_output, shell_cerr)
        except EnvironmentError as e:
            logging.warning(e)
        finally:
            # ensure the process is terminated on exit
            if p.poll() is None:
                p.kill()

    def _launch_reader_thread(self, stream):
        """Launch output reader."""
        shell_output = deque()
        outp = threading.Thread(target=self._process_stdout, args=(stream, shell_output))
        # daemonise or join later? if we join, a shell that doesn't close will hang us on exit
        outp.daemon = True
        outp.start()
        return shell_output

    def _drain_final(self, shell_output):
        """Drain final output from shell."""
        if not shell_output:
            return
        elif not self._detect_encoding(shell_output):
            # one-char output, must be rare...
            shell_output.append(b'\r')
        elif not shell_output[-1] in (self._enc(u'\r'), self._enc(u'\n')):
            shell_output.append(self._enc(u'\r'))
        self._show_output(shell_output)

    def _communicate(self, p, shell_output, shell_cerr):
        """Communicate with launched shell."""
        word = []
        while p.poll() is None:
            self._show_output(shell_output)
            self._show_output(shell_cerr)
            try:
                self._queues.wait()
                # expand=False suppresses key macros
                c = self._keyboard.get_fullchar(expand=False)
            except error.Break:
                pass
            if not c:
                continue
            elif c in (b'\r', b'\n'):
                # put sentinel on queue
                shell_output.append(b'')
                shell_cerr.append(b'')
                # send the command
                self._send_input(p.stdin, word)
                word = []
            elif c == b'\b':
                # handle backspace
                if word:
                    word.pop()
                    self._console.write(b'\x1D \x1D')
            elif not c.startswith(b'\0'):
                # exclude e-ascii (arrow keys not implemented)
                word.append(c)
                self._console.write(c)
        # drain final output
        self._drain_final(shell_output)
        self._drain_final(shell_cerr)

    def _send_input(self, pipe, word):
        """Write keyboard input to pipe."""
        # for shell input, send CRLF or LF depending on platform
        self._last_command.extend(word)
        bytes_word = b''.join(word) + b'\r\n'
        unicode_word = self._codepage.bytes_to_unicode(
            bytes_word, preserve=CONTROL, box_protect=False
        )
        # cmd.exe /u outputs UTF-16 but does not accept it as input...
        pipe.write(unicode_word.encode(SHELL_ENCODING, errors='replace'))
        # explicit flush as pipe may not be line buffered. blocks in python 3 without
        pipe.flush()

    def _detect_encoding(self, shell_output):
        """Detect UTF-16LE output."""
        if self._encoding:
            return True
        elif len(shell_output) > 1:
            # detect UTF-16 output (assuming the first output char is ascii...)
            self._encoding = 'utf-16le' if shell_output[1] == b'\0' else SHELL_ENCODING
            return True
        return False

    def _enc(self, unitext):
        """Encode argument."""
        return unitext.encode(self._encoding, errors='replace')

    def _show_output(self, shell_output):
        """Write shell output to console."""
        # detect sentinel for start of new command
        if shell_output and self._detect_encoding(shell_output):
            # detect sentinel for start of new command
            # wait for at least one LF
            if not shell_output[0]:
                if b'\n' not in shell_output:
                    return
            # can't do a comprehension as it will crash if the deque is accessed by the thread
            lines = deque()
            while shell_output:
                lines.append(shell_output.popleft())
            # push back last char if not aligned to encoding
            if self._encoding == 'utf-16le' and lines[-1] != b'\0':
                shell_output.appendleft(lines.pop())
            # detect echo
            while not lines[0]:
                lines.popleft()
                while lines:
                    reply = lines.popleft()
                    if self._encoding == 'utf-16le':
                        reply += lines.popleft()
                    try:
                        cmd = self._last_command.popleft()
                    except IndexError:
                        cmd = b''
                    if self._enc(cmd) != reply:
                        lines.appendleft(reply)
                        if reply not in (self._enc(u'\r'), self._enc(u'\n')):
                            # two CRs, for some reason
                            lines.appendleft(self._enc(u'\r'))
                        break
            outstr = b''.join(lines)
            # accept CRLF or LF in output
            outstr = outstr.replace(self._enc(u'\r\n'), self._enc(u'\r'))
            # remove BELs (dosemu uses these a lot)
            outstr = outstr.replace(self._enc(u'\x07'), b'')
            outstr = outstr.decode(self._encoding, errors='replace')
            outstr = self._codepage.unicode_to_bytes(outstr, errors='replace')
            logging.debug('SHELL output: %r', outstr)
            self._console.write(outstr)
