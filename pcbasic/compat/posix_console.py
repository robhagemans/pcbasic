"""
PC-BASIC - compat.posix_console
POSIX console support

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import tty
import termios
import select
import fcntl
import array
import struct

from .base import MACOS, PY2, HOME_DIR, wrap_input_stream, wrap_output_stream


if PY2:
    stdin = wrap_input_stream(sys.stdin)
    stdout = wrap_output_stream(sys.stdout)
    stderr = wrap_output_stream(sys.stderr)
else:
    stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr

# output buffer for ioctl call
_sock_size = array.array('i', [0])

# no such thing as console- and GUI-apps
# check if we can treat stdin like a tty, file or socket
HAS_CONSOLE = True
if not sys.stdin.isatty():
    try:
        fcntl.ioctl(sys.stdin, termios.FIONREAD, _sock_size)
    except EnvironmentError:
        # maybe /dev/null, but not a real file or console
        HAS_CONSOLE = False
        if MACOS:
            # for macOS - presumably we're launched as a bundle, set working directory to user home
            # bit of a hack but I don't know a better way
            os.chdir(HOME_DIR)

# save termios state
_term_attr = None

# preserve original terminal size
try:
    TERM_SIZE = struct.unpack(
        'HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\0'*8)
    )[:2]
except Exception:
    TERM_SIZE = 25, 80

def set_raw():
    """Enter raw terminal mode."""
    global _term_attr
    fd = sys.stdin.fileno()
    _term_attr = termios.tcgetattr(fd)
    tty.setraw(fd)

def unset_raw():
    """Leave raw terminal mode."""
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _term_attr)

def key_pressed():
    """Return whether a character is ready to be read from the keyboard."""
    return select.select([sys.stdin], [], [], 0)[0] != []

def read_all_available(stream):
    """Read all available characters from a stream; nonblocking; None if closed."""
    # this function works for everything on unix, and sockets on Windows
    instr = []
    # we're getting bytes counts for unicode which is pretty useless - so back to bytes
    try:
        encoding = stream.encoding
        stream = stream.buffer
    except:
        encoding = None
    # if buffer has characters/lines to read
    if select.select([stream], [], [], 0)[0]:
        # find number of bytes available
        fcntl.ioctl(stream, termios.FIONREAD, _sock_size)
        count = _sock_size[0]
        # and read them all
        c = stream.read(count)
        if not c and not instr:
            # break out, we're closed
            return None
        instr.append(c)
    if encoding:
        return b''.join(instr).decode(encoding, 'replace')
    return b''.join(instr)
