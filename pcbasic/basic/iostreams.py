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

from ..compat import WIN32, read_all_available, stdio, random_id, text_type
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

    def add_pipes(self, input=None, output=None):
        """Add input/output pipes."""
        self._add_input_streams(*_make_iterable(input))
        self._add_output_streams(*_make_iterable(output))

    def remove_pipes(self, input=None, output=None):
        """Remove input/output pipes."""
        self._remove_input_streams(*_make_iterable(input))
        self._remove_output_streams(*_make_iterable(output))

    def toggle_output_stream(self, stream):
        """Toggle copying of all screen I/O to stream."""
        stream = self._get_wrapped_output_stream(stream)
        if stream.name in (_stream.name for _stream in self._output_streams):
            self._output_streams.remove(stream)
        else:
            self._output_streams.append(stream)

    def _add_input_streams(self, *input_streams):
        """Attach input streams."""
        if not input_streams:
            return
        first_streams = not self._input_streams
        has_stdin = any(_stream.name == stdio.stdin.name for _stream in self._input_streams)
        for stream in input_streams:
            stream = self._get_wrapped_input_stream(stream)
            if not (has_stdin and stream.name == stdio.stdin.name):
                # include stdin stream at most once, others may be replicated
                self._input_streams.append(stream)
        if first_streams and self._input_streams:
            self._launch_input_thread()

    def _remove_input_streams(self, *input_streams):
        """Detach output streams."""
        for stream_to_remove in input_streams:
            name = self._get_wrapped_output_stream(stream_to_remove).name
            for stream in self._input_streams:
                # remove the first stream whose name matches
                if stream.name == name:
                    self._input_streams.remove(stream)
                    break
            else:
                raise ValueError("can't remove input stream {}, not attached".format(stream.name))

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
        if not hasattr(stream, 'name'):
            stream.name = 'input_' + random_id(8)
        return NonBlockingInputWrapper(
            stream, self._codepage, lfcr=not WIN32 and stream.isatty()
        )

    def _add_output_streams(self, *output_streams):
        """Attach output streams."""
        has_stdout = any(_stream.name == stdio.stdout.name for _stream in self._output_streams)
        for stream in output_streams:
            stream = self._get_wrapped_output_stream(stream)
            # include stdout stream at most once, others may be replicated
            # (if you do need multiple stdio streams, change the stream name)
            # this avoids duplicating stdio steams on resume
            if not (has_stdout and stream.name == stdio.stdout.name):
                self._output_streams.append(stream)

    def _remove_output_streams(self, *output_streams):
        """Detach output streams."""
        for stream_to_remove in output_streams:
            name = self._get_wrapped_output_stream(stream_to_remove).name
            for stream in self._output_streams:
                # remove the first stream whose name matches
                if stream.name == name:
                    self._output_streams.remove(stream)
                    break
            else:
                raise ValueError("can't remove output stream {}, not attached".format(stream.name))

    def _get_wrapped_output_stream(self, stream):
        """Interpret stream argument and get the appropriate stream."""
        if stream in (u'stdio', b'stdio'):
            stream = stdio.stdout
        elif not hasattr(stream, 'write'):
            raise TypeError(
                'output_streams must be file-like or "stdio", not `%s`'
                % (type(stream),)
            )
        if not hasattr(stream, 'name'):
            stream.name = 'output_' + random_id(8)
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
            for stream in self._input_streams:
                instr = stream.read()
                if instr is None:
                    self._remove_closed_stream(stream)
                elif instr:
                    self._queues.inputs.put(signals.Event(signals.STREAM_CHAR, (instr,)))

    def _remove_closed_stream(self, stream):
        """
        Remove a closed stream from the list.
        """
        if len(self._input_streams) == 1:
            # exit the interpreter instead of closing last input
            # the input is preserved for resume
            self._queues.inputs.put(signals.Event(signals.STREAM_CLOSED))
        else:
            # input stream is closed, remove it
            self._input_streams.remove(stream)


def _make_iterable(arg):
    """Make the argument iterable, don't iterate over files or strings."""
    if not arg:
        return ()
    if hasattr(arg, 'read') or isinstance(arg, (bytes, text_type)):
        return (arg,)
    try:
        iter(arg)
    except TypeError:
        return (arg,)
    return arg



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
