"""
PC-BASIC - redirect.py
Input/output redirection

(c) 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import threading
import logging
import Queue
import sys
import platform

from .base import signals
from . import codepage as cp


def get_redirection(codepage, stdio, input_file, output_file, append, queue):
    """Initialise redirection objects."""
    if stdio:
        stdout_stream = cp.CodecStream(
                sys.stdout, codepage, sys.stdout.encoding or b'utf-8')
        stdin_stream = sys.stdin
    else:
        stdout_stream, stdin_stream = None, None
    output_redirection = OutputRedirection(output_file, append, stdout_stream)
    input_stream = None
    if input_file:
        try:
            input_stream = open(input_file, b'rb')
        except EnvironmentError as e:
            logging.warning(u'Could not open input file %s: %s', input_file, e.strerror)
    input_redirection = InputRedirection(
            [(input_stream, False, None),
            (stdin_stream, platform.system() != 'Windows' and sys.stdin.isatty(), sys.stdin.encoding)],
            codepage, queue)
    return input_redirection, output_redirection


class OutputRedirection(object):
    """Manage I/O redirection."""

    def __init__(self, option_output, append, filter_stream):
        """Initialise redirects."""
        # redirect output to file or printer
        self._output_echos = []
        # filter interface depends on redirection output
        if filter_stream:
            self._output_echos.append(filter_stream)
        if option_output:
            mode = b'ab' if append else b'wb'
            try:
                # raw codepage output to file
                self._output_echos.append(open(option_output, mode))
            except EnvironmentError as e:
                logging.warning(u'Could not open output file %s: %s', option_output, e.strerror)

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



class InputRedirection(object):
    """Manage I/O redirection."""

    def __init__(self, input_list, codepage, queue):
        """Initialise redirects."""
        self._codepage = codepage
        self._sources = []
        self._input_streams = []
        self._lfcrs = []
        self._encodings = []
        for f, lfcr, encoding in input_list:
            if f:
                self._input_streams.append(f)
                self._lfcrs.append(lfcr)
                self._encodings.append(encoding)
        self.attach(queue)

    def attach(self, queue):
        """Attach input queue and start stream reader threads."""
        # allow None as well as empty list
        if not self._input_streams:
            return
        # launch a daemon thread for each source
        for s, encoding, lfcr in zip(self._input_streams, self._encodings, self._lfcrs):
            # launch a thread to allow nonblocking reads on both Windows and Unix
            thread = threading.Thread(target=self._process_input, args=(s, queue, encoding, lfcr))
            thread.daemon = True
            thread.start()
            self._sources.append(queue)

    def __getstate__(self):
        """Pickler."""
        pickle_dict = self.__dict__
        # don't pickle the queues
        del pickle_dict['_sources']
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickler."""
        # don't pickle the queues
        self.__dict__ = pickle_dict
        self._sources = []

    def _process_input(self, stream, queue, encoding, lfcr):
        """Process input from stream."""
        while True:
            # blocking read
            instr = stream.readline().replace('\r\n', '\r')
            if lfcr:
                instr = instr.replace('\n', '\r')
            if not instr:
                # input stream is closed, stop the thread
                queue.put(signals.Event(signals.STREAM_CLOSED))
                return
            if encoding:
                queue.put(signals.Event(signals.STREAM_CHAR,
                        (instr.decode(encoding, b'replace'),) ))
            else:
                # raw input means it's already in the BASIC codepage
                # but the keyboard functions use unicode
                queue.put(signals.Event(signals.STREAM_CHAR,
                        (self._codepage.str_to_unicode(instr, preserve_control=True),) ))
