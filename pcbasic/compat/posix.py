"""
PC-BASIC - compat.posix
Interface for Unix-like system calls

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import locale
import logging
import select
import subprocess
import fcntl
import termios
import array
import struct

# set locale - this is necessary for curses and *maybe* for clipboard handling
# there's only one locale setting so best to do it all upfront here
# NOTE that this affects str.upper() etc.
# don't do this on Windows as it makes the console codepage different from the stdout encoding ?
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error as e:
    # mis-configured locale can throw an error here, no need to crash
    logging.error(e)

from .python2 import which
from .base import HOME_DIR, MACOS

# text conventions
# ctrl+D
EOF = b'\x04'
UEOF = u'\x04'
# LF end-of-line
EOL = b'\n'

# shell conventions
# console encoding
SHELL_ENCODING = sys.stdin.encoding or locale.getpreferredencoding()
# window suppression not needed on Unix
HIDE_WINDOW = None


##############################################################################
# various

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

# preserve original terminal size
try:
    TERM_SIZE = struct.unpack(
        'HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\0'*8))[:2]
except Exception:
    TERM_SIZE = 25, 80

def set_dpi_aware():
    """Enable HiDPI awareness."""

##############################################################################
# file system

def get_free_bytes(path):
    """Return the number of free bytes on the drive."""
    # note that from Python 3.3 onwards, we can use the cross-platform shutil.disk_usage
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize

def get_short_pathname(native_path):
    """Return Windows short path name or None if not available."""
    return None

def get_unicode_argv():
    """Convert command-line arguments to unicode."""
    # the official parameter should be LC_CTYPE but that's None in my locale
    # on Windows, this would only work if the mbcs CP_ACP includes the characters we need;
    # on MacOS, if launched from Finder, ignore the additional "process serial number" argument
    return [
        arg.decode(SHELL_ENCODING, errors='replace')
        for arg in sys.argv if not arg.startswith(b'-psn_')
    ]

def is_hidden(path):
    """File is hidden."""
    # dot files are hidden on unixy systems
    base = os.path.basename(path)
    return base.startswith(u'.') and (base not in (u'.', u'..'))


##############################################################################
# printing

if which('paps'):
    def line_print(printbuf, printer):
        """Print the buffer to a LPR printer using PAPS."""
        options = b''
        if printer and printer != u'default':
            options = b'-P "%s"' % (printer.encode(SHELL_ENCODING, 'replace'),)
        if printbuf:
            # A4 paper is 595 points wide by 842 points high.
            # Letter paper is 612 by 792 points.
            # the below seems to allow 82 chars horizontally on A4; it appears
            # my PAPS version doesn't quite use cpi correctly as 10cpi should
            # allow 80 chars on A4 with a narrow margin but only does so with a
            # margin of 0.
            pr = subprocess.Popen(
                b'paps --cpi=11 --lpi=6 --left-margin=20 --right-margin=20 '
                '--top-margin=6 --bottom-margin=6 '
                '| lpr %s' % (options,), shell=True, stdin=subprocess.PIPE)
            # PAPS does not recognise CRLF
            printbuf = printbuf.replace(b'\r\n', b'\n')
            pr.stdin.write(printbuf)
            pr.stdin.close()

else:
    def line_print(printbuf, printer):
        """Print the buffer to a LPR (CUPS or older UNIX) printer."""
        options = b''
        if printer and printer != u'default':
            options = b'-P "%s"' % (printer.encode(SHELL_ENCODING, 'replace'),)
        if printbuf:
            # cups defaults to 10 cpi, 6 lpi.
            pr = subprocess.Popen(b'lpr %s' % (options,), shell=True, stdin=subprocess.PIPE)
            pr.stdin.write(printbuf)
            pr.stdin.close()


##############################################################################
# non-blocking input

def key_pressed():
    """Return whether a character is ready to be read from the keyboard."""
    return select.select([sys.stdin], [], [], 0)[0] != []

def read_all_available(stream):
    """Read all available characters from a stream; nonblocking; None if closed."""
    # this works for everything on unix, and sockets on Windows
    instr = []
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
    return b''.join(instr)
