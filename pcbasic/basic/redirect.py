"""
PC-BASIC - redirect.py
Input/output redirection

(c) 2014--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import threading
import logging
import sys
import platform
import time
from contextlib import contextmanager

if platform.system() == 'Windows':
    import msvcrt
else:
    import select
    import fcntl
    import termios
    import array

from .base import signals
from . import codepage as cp


class RedirectedIO(object):
    """Manage I/O redirection to files, printers and stdio."""

    tick = 0.006

    def __init__(self, codepage, input_file, output_file, append):
        """Initialise redirects."""
        self._stdio = False
        self._input_file = input_file
        self._output_file = output_file
        self._append = append
        # input
        self._active = False
        self._codepage = codepage
        self._input_streams = []
        self._lfcrs = []
        self._encodings = []
        # output
        self._output_echos = []

    def write(self, s):
        """Write a string/bytearray to all redirected outputs."""
        for f in self._output_echos:
            f.write(s)

    def toggle_echo(self, stream):
        """Toggle copying of all screen I/O to stream."""
        if stream in self._output_echos:
            self._output_echos.remove(stream)
        else:
            self._output_echos.append(stream)

    @contextmanager
    def activate(self):
        """Grab and release input stream."""
        self._active = True
        try:
            yield
        finally:
            self._active = False

    def attach(self, queue, stdio):
        """Attach input queue and stdio and start stream reader threads."""
        if stdio and not self._stdio:
            self._stdio = True
            self._output_echos.append(
                        cp.CodecStream(sys.stdout, self._codepage, sys.stdout.encoding or b'utf-8'))
            self._input_streams.append(sys.stdin)
            self._lfcrs.append(platform.system() != 'Windows' and sys.stdin.isatty())
            self._encodings.append(sys.stdin.encoding)
        if self._input_file:
            try:
                self._input_streams.append(open(self._input_file, 'rb'))
            except EnvironmentError as e:
                logging.warning(u'Could not open input file %s: %s', self._input_file, e.strerror)
            else:
                self._lfcrs.append(False)
                self._encodings.append(None)
        if self._output_file:
            mode = 'ab' if self._append else 'wb'
            try:
                # raw codepage output to file
                self._output_echos.append(open(self._output_file, mode))
            except EnvironmentError as e:
                logging.warning(u'Could not open output file %s: %s', self._output_file, e.strerror)
        # launch a daemon thread for each source
        for s, encoding, lfcr in zip(self._input_streams, self._encodings, self._lfcrs):
            # launch a thread to allow nonblocking reads on both Windows and Unix
            thread = threading.Thread(target=self._process_input, args=(s, queue, encoding, lfcr))
            thread.daemon = True
            thread.start()

    def _process_input(self, stream, queue, encoding, lfcr):
        """Process input from stream."""
        if platform.system() == 'Windows':
            if stream == sys.stdin:
                get_chars = _get_chars_windows_console
            else:
                get_chars = _get_chars_file
        else:
            get_chars = _get_chars
        while True:
            time.sleep(self.tick)
            if not self._active:
                continue
            instr = get_chars(stream)
            if instr is None:
                # input stream is closed, stop the thread
                queue.put(signals.Event(signals.STREAM_CLOSED))
                return
            elif not instr:
                continue
            instr = instr.replace(b'\r\n', b'\r')
            if lfcr:
                instr = instr.replace(b'\n', b'\r')
            if encoding:
                queue.put(signals.Event(signals.STREAM_CHAR,
                        (instr.decode(encoding, b'replace'),) ))
            else:
                # raw input means it's already in the BASIC codepage
                # but the keyboard functions use unicode
                queue.put(signals.Event(signals.STREAM_CHAR,
                        (self._codepage.str_to_unicode(instr, preserve_control=True),) ))


##############################################################################
# non-blocking character read

def _get_chars(stream):
    """Get characters from unix stream, nonblocking."""
    # this works for everything on unix, and sockets on Windows
    instr = []
    # output buffer for ioctl call
    sock_size = array.array('i', [0])
    # while buffer has characters/lines to read
    while select.select([stream], [], [], 0)[0]:
        # find number of bytes available
        fcntl.ioctl(stream, termios.FIONREAD, sock_size)
        count = sock_size[0]
        # and read them all
        c = stream.read(count)
        if not c:
            return None
        instr.append(c)
    return b''.join(instr)

def _get_chars_windows_console(dummy_stream):
    """Get characters from windows console, nonblocking."""
    instr = []
    # get characters while keyboard buffer has them available
    # this does not echo
    while msvcrt.kbhit():
        c = msvcrt.getch()
        if not c:
            return None
        instr.append(c)
    return b''.join(instr)

def _get_chars_file(stream):
    """Get characters from file."""
    # just read the whole file and be done with it
    return stream.read() or None
