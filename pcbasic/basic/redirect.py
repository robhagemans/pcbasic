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


class RedirectedIO(object):
    """Manage I/O redirection to files, printers and stdio."""

    tick = 0.006

    def __init__(self, codepage, input_file, output_file, append):
        """Initialise redirects."""
        self._stdio = False
        self._input_file = input_file
        self._output_file = output_file
        self._append = append
        self._codepage = codepage
        # input
        self._active = False
        self._input_streams = []
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

    def attach(self, queues, stdio):
        """Attach input queue and stdio and start stream reader threads."""
        queue = queues.inputs
        if stdio and not self._stdio:
            self._stdio = True
            self._output_echos.append(OutputStreamWrapper(
                        sys.stdout, self._codepage, sys.stdout.encoding or 'utf-8'))
            lfcr = platform.system() != 'Windows' and sys.stdin.isatty()
            self._input_streams.append(InputStreamWrapper(
                        sys.stdin, self._codepage, sys.stdin.encoding, lfcr))
        if self._input_file:
            try:
                self._input_streams.append(InputStreamWrapper(
                        open(self._input_file, 'rb'), self._codepage, None, False))
            except EnvironmentError as e:
                logging.warning(u'Could not open input file %s: %s', self._input_file, e.strerror)
        if self._output_file:
            mode = 'ab' if self._append else 'wb'
            try:
                # raw codepage output to file
                self._output_echos.append(open(self._output_file, mode))
            except EnvironmentError as e:
                logging.warning(u'Could not open output file %s: %s', self._output_file, e.strerror)
        # launch a daemon thread for each source
        for stream in self._input_streams:
            # launch a thread to allow nonblocking reads on both Windows and Unix
            thread = threading.Thread(target=self._process_input, args=(stream, queue))
            thread.daemon = True
            thread.start()

    def _process_input(self, stream, queue):
        """Process input from stream."""
        while True:
            time.sleep(self.tick)
            if not self._active:
                continue
            instr = stream.read()
            if instr is None:
                # input stream is closed, stop the thread
                queue.put(signals.Event(signals.STREAM_CLOSED))
                return
            elif instr:
                queue.put(signals.Event(signals.STREAM_CHAR, (instr,)))


class OutputStreamWrapper(object):
    """Converter stream wrapper."""

    def __init__(self, stream, codepage, encoding):
        """Set up codec."""
        self._encoding = encoding
        # converter with DBCS lead-byte buffer for utf8 output redirection
        self._uniconv = codepage.get_converter(preserve_control=True)
        self._stream = stream

    def write(self, s):
        """Write to codec stream."""
        self._stream.write(self._uniconv.to_unicode(bytes(s)).encode(
                    self._encoding, 'replace'))


class InputStreamWrapper(object):
    """Converter and non-blocking input wrapper."""

    def __init__(self, stream, codepage, encoding, lfcr):
        """Set up codec."""
        self._codepage = codepage
        self._encoding = encoding
        self._lfcr = lfcr
        self._stream = stream
        # we need non-blocking readers to be able to deactivate the thread
        if platform.system() == 'Windows':
            if self._stream == sys.stdin:
                self._get_chars = _get_chars_windows_console
            else:
                self._get_chars = _get_chars_file
        else:
            self._get_chars = _get_chars

    def read(self):
        """Read all chars available; nonblocking; returns unicode."""
        s = self._get_chars(self._stream)
        if s is None:
            return s
        s = s.replace(b'\r\n', b'\r')
        if self._lfcr:
            s = s.replace(b'\n', b'\r')
        if self._encoding:
            return s.decode(self._encoding, 'replace')
        else:
            # raw input means it's already in the BASIC codepage
            # but the keyboard functions use unicode
            # for input, don't use lead-byte buffering beyond the convert call
            return self._codepage.str_to_unicode(s, preserve_control=True)


##############################################################################
# non-blocking character read

def _get_chars(stream):
    """Get characters from unix stream, nonblocking."""
    # this works for everything on unix, and sockets on Windows
    instr = []
    closed = False
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
            closed = True
            break
        instr.append(c)
    if not instr and closed:
        return None
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
