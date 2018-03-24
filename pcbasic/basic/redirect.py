"""
PC-BASIC - redirect.py
Input/output redirection

(c) 2014--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import sys
import time
from contextlib import contextmanager

from ..compat import WIN32, read_all_available
from .base import signals


class RedirectedIO(object):
    """Manage I/O redirection to files, printers and stdio."""

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
        # this is perhaps unnecessary without threads
        self._active = True
        try:
            yield
        finally:
            self._active = False

    def attach_streams(self, stdio):
        """Attach i/o streams."""
        if stdio and not self._stdio:
            self._stdio = True
            self._output_echos.append(OutputStreamWrapper(
                        sys.stdout, self._codepage, sys.stdout.encoding))
            lfcr = not WIN32 and sys.stdin.isatty()
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

    def process_input(self, queue):
        """Process input from streams."""
        for stream in self._input_streams:
            if not self._active:
                return
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
        self._encoding = encoding or 'utf-8'
        # converter with DBCS lead-byte buffer for utf8 output redirection
        self._uniconv = codepage.get_converter(preserve_control=True)
        self._stream = stream

    def write(self, s):
        """Write to codec stream."""
        self._stream.write(self._uniconv.to_unicode(s).encode(self._encoding, 'replace'))
        self._stream.flush()


class InputStreamWrapper(object):
    """Converter and non-blocking input wrapper."""

    def __init__(self, stream, codepage, encoding, lfcr):
        """Set up codec."""
        self._codepage = codepage
        self._encoding = encoding or 'utf-8'
        self._lfcr = lfcr
        self._stream = stream

    def read(self):
        """Read all chars available; nonblocking; returns unicode."""
        # we need non-blocking readers
        s = read_all_available(self._stream)
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
