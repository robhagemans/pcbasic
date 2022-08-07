"""
PC-BASIC - iostreams.py
Input/output streams

(c) 2014--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import threading
import sys
import time
import io
from contextlib import contextmanager

from ..compat import WIN32, read_all_available, stdio
from .base import signals
from .codepage import CONTROL


# sleep period for input thread
# does not need to be very short as it reads multiple bytes in one cycle
TICK = 0.03


class IOStreams(object):
    """Manage input/output to files, printers and stdio."""

    def __init__(self, queues, codepage):
        """Initialise I/O streams."""
        self._queues = queues
        self._codepage = codepage
        # disable input streams at start
        self._active = False
        # flag for input daemon thread
        self._stop_threads = False
        # streams
        self._input_streams = []
        self._output_streams = []

    def __getstate__(self):
        """Pickle the streams."""
        return self.__dict__

    def __setstate__(self, pickle_dict):
        """Unpickle and resume the streams."""
        self.__dict__.update(pickle_dict)
        if self._input_streams:
            self._launch_input_thread()

    def add_input_streams(self, *input_streams):
        """Attach input streams."""
        if not input_streams:
            return
        first_streams = not self._input_streams
        has_stdin = any(_stream.name == stdio.stdin.name for _stream in self._input_streams)
        for stream in input_streams:
            if not (has_stdin and stream.name == stdio.stdin.name):
                # include stdin stream at most once, others may be replicated
                self._input_streams.append(self._get_wrapped_input_stream(stream))
        if first_streams and self._input_streams:
            self._launch_input_thread()

    #def remove_input_streams(self, *input_streams):
    #    """Detach input streams."""
    #    for stream in input_streams:
    #        self._input_streams.remove(self._get_wrapped_input_stream(stream))

    def _get_wrapped_input_stream(self, stream):
        """Interpret stream argument and get the appropriate stream."""
        if stream in (u'stdio', b'stdio'):
            # sentinel value
            # stdin needs to be picked at runtime as both console.stdin and sys.stdin can change
            # and we would be keeping a reference to a closed/bad file
            stream = stdio.stdin
        elif not hasattr(stream, 'read'):
            raise TypeError(
                'input_streams must be file-like or "stdio", not `%s`'
                % (type(stream),)
            )
        return NonBlockingInputWrapper(
            stream, self._codepage, lfcr=not WIN32 and stream.isatty()
        )

    def add_output_streams(self, *output_streams):
        """Attach output streams."""
        has_stdout = any(_stream.name == stdio.stdout.name for _stream in self._output_streams)
        for stream in output_streams:
            if not (has_stdout and stream.name == stdio.stdout.name):
                # include stdout stream at most once, others may be replicated
                self._output_streams.append(self._get_wrapped_output_stream(stream))

    def remove_output_streams(self, *output_streams):
        """Detach output streams."""
        for stream in output_streams:
            self._output_streams.remove(self._get_wrapped_output_stream(stream))

    def toggle_output_stream(self, stream):
        """Toggle copying of all screen I/O to stream."""
        stream = self._get_wrapped_output_stream(stream)
        if stream in self._output_streams:
            self._output_streams.remove(stream)
        else:
            self._output_streams.append(stream)

    def _get_wrapped_output_stream(self, stream):
        """Interpret stream argument and get the appropriate stream."""
        if stream in (u'stdio', b'stdio'):
            stream = stdio.stdout
        elif not hasattr(stream, 'write'):
            raise TypeError(
                'output_streams must be file-like or "stdio", not `%s`'
                % (type(stream),)
            )
        return self._codepage.wrap_output_stream(stream, preserve=CONTROL)

    def close(self):
        """Kill threads before exit."""
        self._stop_threads = True

    def flush(self):
        """Flush output streams."""
        for f in self._output_streams:
            f.flush()

    def write(self, s):
        """Write bytes to all stream outputs."""
        for f in self._output_streams:
            f.write(s)

    @contextmanager
    def activate(self):
        """Grab and release input stream."""
        self._active = True
        try:
            yield
        finally:
            self._active = False


    def _launch_input_thread(self):
        """Launch a thread to allow nonblocking reads on both Windows and Unix."""
        thread = threading.Thread(target=self._process_input, args=())
        thread.daemon = True
        thread.start()

    def _process_input(self):
        """Process input from streams."""
        while True:
            time.sleep(TICK)
            if self._stop_threads:
                return
            if not self._active:
                continue
            queue = self._queues.inputs
            for stream in self._input_streams:
                instr = stream.read()
                if instr is None:
                    break
                elif instr:
                    queue.put(signals.Event(signals.STREAM_CHAR, (instr,)))
            else:
                # executed if not break
                continue
            # exit the interpreter instead of closing last input
            # the input is preserved for resume
            if len(self._input_streams) == 1:
                queue.put(signals.Event(signals.STREAM_CLOSED))
                return
            # input stream is closed, remove it
            self._input_streams.remove(stream)


class NonBlockingInputWrapper(object):
    """
    Non-blocking input wrapper, converts CRLF.
    Wraps unicode or bytes stream; always produces unicode.
    """

    def __init__(self, stream, codepage, lfcr):
        """Set up codec."""
        self._stream = stream
        self._lfcr = lfcr
        # codepage, used to read unicode from bytes streams
        self._codepage = codepage
        try:
            self.name = stream.name
        except AttributeError:
            self.name = ''

    def read(self):
        """Read all chars available; nonblocking; returns unicode."""
        # we need non-blocking readers
        s = read_all_available(self._stream)
        # can be None (closed) or b'' (no input)
        if s is None:
            return None
        elif not s:
            return u''
        if isinstance(s, bytes):
            # raw input means it's already in the BASIC codepage
            # but the keyboard functions use unicode
            # for input, don't use lead-byte buffering beyond the convert call
            s = self._codepage.bytes_to_unicode(s, preserve=CONTROL)
        # replace CRLF (and, if desired, LF) with CR
        s = s.replace(u'\r\n', u'\r')
        if self._lfcr:
            s = s.replace(u'\n', u'\r')
        return s
