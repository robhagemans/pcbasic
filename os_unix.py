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
import string
import fcntl
import fnmatch

import error
import console

import pexpect
import glob
    
shell = '/bin/sh'

def disk_free(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize
        

def lock(fd, access, lock, length=0, start=0, whence=0):
    # w locks are rw locks - unix distinguishes 'shared' and 'exclusive' locks 
    if 'W' in access.upper():
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, length, start, whence)
    else:
        fcntl.lockf(fd, fcntl.LOCK_SH, length, start, whence)


def unlock(fd):
    fcntl.flock(ins.fhandle, fcntl.LOCK_UN)
    
  
def spawn_interactive_shell(cmd):
    shell = pexpect.spawn(cmd)
    
    while True:
        #console.idle()
        c = console.get_char()
        if c != '':
            shell.send(c)
            
        c = ''
        try:
            c = shell.read_nonblocking(1, timeout=0)
        except: 
            pass
            
        if c != '':
            if c=='\r':
                console.idle()
                console.check_events()
            else:
                console.write(c)
                
        elif not shell.isalive(): 
            break
        
        

