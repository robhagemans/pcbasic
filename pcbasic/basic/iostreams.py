"""
PC-BASIC - iostreams.py
Input/output streams

(c) 2014--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import sys
import time
from contextlib import contextmanager

from ..compat import WIN32, read_all_available
from .base import signals


class IOStreams(object):
    """Manage input/output to files, printers and stdio."""

    def __init__(self, codepage, input_file, output_file, append, utf8):
        """Initialise I/O streams."""
        self._stdio = False
        self._input_file = input_file
        self._output_file = output_file
        self._append = append
        self._codepage = codepage
        # external encoding for files; None means raw codepage bytes
        self._encoding = 'utf-8' if utf8 else None
        # input
        self._active = False
        self._input_streams = []
        # output
        self._output_echos = []

    def write(self, s):
        """Write a string/bytearray to all stream outputs."""
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
            out_encoding = sys.stdout.encoding if sys.stdout.isatty() else self._encoding
            in_encoding = sys.stdin.encoding if sys.stdin.isatty() else self._encoding
            self._output_echos.append(
                    OutputStreamWrapper(sys.stdout, self._codepage, out_encoding))
            lfcr = not WIN32 and sys.stdin.isatty()
            self._input_streams.append(
                    InputStreamWrapper(sys.stdin, self._codepage, in_encoding, lfcr))
        if self._input_file:
            try:
                self._input_streams.append(InputStreamWrapper(
                        open(self._input_file, 'rb'), self._codepage, self._encoding, False))
            except EnvironmentError as e:
                logging.warning(u'Could not open input file %s: %s', self._input_file, e.strerror)
        if self._output_file:
            mode = 'ab' if self._append else 'wb'
            try:
                # raw codepage output to file
                self._output_echos.append(OutputStreamWrapper(
                        open(self._output_file, mode), self._codepage, self._encoding))
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
        self._encoding = encoding
        # converter with DBCS lead-byte buffer for utf8 output redirection
        self._uniconv = codepage.get_converter(preserve_control=True)
        self._stream = stream

    def write(self, s):
        """Write bytes to codec stream."""
        if self._encoding:
            self._stream.write(self._uniconv.to_unicode(s).encode(self._encoding, 'replace'))
        else:
            # raw output
            self._stream.write(s)
        self._stream.flush()


class InputStreamWrapper(object):
    """Converter and non-blocking input wrapper."""

    def __init__(self, stream, codepage, encoding, lfcr):
        """Set up codec."""
        self._codepage = codepage
        self._encoding = encoding
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
