""" 
ANSI|pipe Python connection module
Redirect standard I/O through ANSI|pipe executable
to enable UTF-8, ANSI escape sequences and dual mode CLI/GUI executables
when packaging Python applications to a Windows executable.

based on DualModeI.cpp from dualsybsystem.
Python version (c) 2015 Rob Hagemans
This module is released under the terms of the MIT license.
"""

import os
import sys
import platform

if platform.system() == 'Windows':
    pid = os.getpid()

    # construct named pipe names
    name_out = '\\\\.\\pipe\\ANSIPIPE_%d_POUT' % pid
    name_in = '\\\\.\\pipe\\ANSIPIPE_%d_PIN' % pid
    name_err = '\\\\.\\pipe\\ANSIPIPE_%d_PERR' % pid

    # attach named pipes to stdin/stdout/stderr
    try:
        sys.stdout = open(name_out, 'wb', 0)
        sys.stdin = open(name_in, 'rb', 0)
        sys.stderr = open(name_err, 'wb', 0)
        ok = True;
    except EnvironmentError:
        sys.stdout = sys.__stdout__
        sys.stdin = sys.__stdin__
        sys.stderr = sys.__stderr__
        ok = False;

    # minimal replacements for tty.setraw() and termios.tcsa
    # using ansipipe-only escape sequences
    ONLCR = 4
    ECHO = 8
    ICRNL = 256

    TCSADRAIN = 1

    termios_state = ICRNL | ECHO

    if ok:
        def setraw(fd, dummy=None):
            """ Set raw terminal mode (Windows stub). """
            tcsetattr(fd, dummy, 0)

        def tcsetattr(fd, dummy, attr):
            """ Set terminal attributes (Windows stub). """
            if (fd == sys.stdin.fileno()):
                num = 254
                sys.stdout.write('\x1b]%d;ECHO\x07' % (num + (attr & ECHO != 0)))
                sys.stdout.write('\x1b]%d;ICRNL\x07' % (num + (attr & ICRNL != 0)))
                sys.stdout.write('\x1b]%d;ONLCR\x07' % (num + (attr & ONLCR != 0)))
                termios_state = attr

        def tcgetattr(fd):
            """ Get terminal attributes (Windows stub). """
            if (fd == sys.stdin.fileno()):
                return termios_state
            else:
                return 0

    else:
        def setraw(fd, dummy=None):
            pass
        def tcsetattr(fd, dummy, attr):
            pass
        def tcgetattr(fd):
            return 0

else:
    ok = True;
