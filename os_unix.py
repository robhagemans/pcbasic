#
# PC-BASIC 3.23  - os_unix.py
#
# UNIX-specific OS utilities
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os
import fcntl
import pexpect

import console
    
shell = '/bin/sh'
shell_cmd = shell + ' -c'


def disk_free(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize

def lock(fhandle, lock, length=0, start=0, whence=0):
    # w locks are rw locks - unix distinguishes 'shared' and 'exclusive' locks 
    # cannot obtain an exclusive lock on a file open for reading.
    # https://mail.python.org/pipermail/python-bugs-list/2001-November/008378.html
    if 'w' in lock and not 'r' in fhandle.mode:  # that's posix access mode
        fcntl.lockf(fhandle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB, length, start, whence)
    else:
        fcntl.lockf(fhandle.fileno(), fcntl.LOCK_SH, length, start, whence)
    
def unlock(fd, length=0, start=0, whence=0):
    fcntl.lockf(fd.fileno(), fcntl.LOCK_UN, length, start, whence)
  
def spawn_interactive_shell(cmd):
    try:
        p = pexpect.spawn(cmd)
    except Exception:
        return 
    while True:
        c = console.get_char()
        if c == '\x08': # BACKSPACE
            p.send('\x7f')
        elif c != '':
            p.send(c)
        c = ''
        try:
            c = p.read_nonblocking(1, timeout=0)
        except: 
            pass
        if c != '':
            if c == '\r':
                console.idle()
                console.check_events()
            elif c == '\x08':
                if console.col !=1:
                    console.col -= 1
            else:
                console.write(c)
        elif not p.isalive(): 
            break
        

