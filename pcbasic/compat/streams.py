import sys
import io
import os
import codecs
import tempfile
from contextlib import contextmanager

from .base import PY2


# unicode stream wrappers

def wrap_output_stream(stream):
    """Wrap std bytes streams to make them behave more like in Python 3."""
    wrapped = codecs.getwriter(stream.encoding or 'utf-8')(stream)
    wrapped.buffer = stream
    return wrapped

def wrap_input_stream(stream):
    """Wrap std bytes streams to make them behave more like in Python 3."""
    wrapped = codecs.getreader(stream.encoding or 'utf-8')(stream)
    wrapped.buffer = stream
    return wrapped


# pause/quiet standard streams
# based on https://eli.thegreenplace.net/2015/redirecting-all-kinds-of-stdout-in-python/

@contextmanager
def muffle(std_stream_name, preserve=False):
    """Pause/quiet standard streams."""
    # usually stdout -> 1 stderr -> 2
    original_fd = getattr(sys, std_stream_name).fileno()
    if not PY2:
        encoding = getattr(sys, std_stream_name).encoding

    def _redirect_to(to_fd):
        """Redirect std stream to the given file descriptor."""
        # the original flushes the C-level buffer stdout here
        # this requires access to libc, which is a pain on Python3 on Windows
        # also we don't care too much if a few chars from external source get dropped
        #libc.fflush(c_stdout)
        # flush and close - also closes the file descriptor
        getattr(sys, std_stream_name).close()
        # make original_fd point to the same file as to_fd
        os.dup2(to_fd, original_fd)
        # create a new sys.stdout or sys.stderr that points to the redirected fd
        if PY2:
            new_stream = os.fdopen(original_fd, 'wb')
        else:
            new_stream = io.TextIOWrapper(os.fdopen(original_fd, 'wb'), encoding=encoding)
            # we need a mode attribute for pickling, regular stdio has this
            new_stream.mode = 'w'
        # change sys.std*** to the new stream
        setattr(sys, std_stream_name, new_stream)

    # save a copy of the original fd in saved_stdout_fd
    saved_fd = os.dup(original_fd)
    try:
        # Create a temporary file and redirect stdout to it
        if preserve:
            temp_file = tempfile.TemporaryFile(mode='w+b')
        else:
            temp_file = io.open(os.devnull, 'wb')
        _redirect_to(temp_file.fileno())
        try:
            yield
        finally:
            _redirect_to(saved_fd)
            # if requested, copy all output received during redirection back into the stream now
            if preserve:
                temp_file.flush()
                temp_file.seek(0, io.SEEK_SET)
                if PY2:
                    getattr(sys, std_stream_name).write(temp_file.read())
                else:
                    getattr(sys, std_stream_name).buffer.write(temp_file.read())
            temp_file.close()
    finally:
        os.close(saved_fd)


class StdIOBase:
    """holds standard unicode streams."""

    def __init__(self):
        self._redirected = set()
        self._reattach_streams()

    # standard unicode streams
    def _reattach_streams(self, quiet=()):
        self.stdin, self.stdout, self.stderr = sys.stdin, sys.stdout, sys.stderr

    @contextmanager
    def quiet(self, stream_name=None):
        """Silence stdout or stderr."""
        if not stream_name:
            with muffle('stdout'):
                with muffle('stderr'):
                    self._redirected = self._redirected.union({'stdout', 'stderr'})
                    self._reattach_streams()
                    yield
            self._redirected -= {'stdout', 'stderr'}
        else:
            with muffle(stream_name):
                self._redirected.add(stream_name)
                self._reattach_streams()
                yield
            self._redirected -= {stream_name}
        self._reattach_streams()
