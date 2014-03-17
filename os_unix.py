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
    # BASIC locks:
    #   '':   (SHARED): allow shared locks by others.
    #   'W':  (LOCK WRITE): deny write access to others, allow read
    #   'R':  (LOCK READ): deny read access to others, alow write
    #   'RW': (LOCK READ WRITE): deny both read and write locks to others.
    #   Default is RW, so you can't open a default mode on a file that is SHARED.
    # Unix locks:
    #   LOCK_SH: shared lock: allow other shared but not exclusive locks - others can read but not write.    
    #   LOCK_EX: exclusive lock: don't allow other locks; others can neither read nor write.
    # You cannot obtain an exclusive lock on a file open for reading:
    #   https://mail.python.org/pipermail/python-bugs-list/2001-November/008378.html
    # It also appears you cannot obtain a shared lock on a file open for reading.
    # Is seems a perfect mapping is not possible - Unix has no 'deny read but not write' lock.
    # Mapping used here:
    #   SHARED -> LOCK_SH; LOCK WRITE -> LOCK_SH; LOCK READ -> LOCK_EX; LOCK READ WRITE -> LOCK_EX
    if 'R' in lock and not 'r' in fhandle.mode:  # that's posix access mode
        fcntl.lockf(fhandle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB, length, start, whence)
    else:
        fcntl.lockf(fhandle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB, length, start, whence)
    
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
        

