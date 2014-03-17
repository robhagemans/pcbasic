#
# PC-BASIC 3.23  - os_windows.py
#
# Windows-specific OS utilities
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os
import msvcrt
import ctypes
import string
import fnmatch
import subprocess
import threading

import error
import console
 
shell = 'CMD'    
shell_cmd = shell + ' /c'

    
def disk_free(path):
    free_bytes = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes))
    return free_bytes.value

#def lock(fd, lock, length=0, start=0, whence=0):
#    curpos = fd.tell()
#    fd.seek(start)
#    msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, length)
#    fd.seek(curpos)
         
#def unlock(fd, length=0, start=0, whence=0):
#    curpos = fd.tell()   
#    fd.seek(start)
#    msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, length)
#    fd.seek(curpos)
    
def process_stdout(p, stream):
    while True:
        c = stream.read(1)
        if c != '': # and c != '\r':
            if c!= '\r':
                console.write(c)
            else:
                console.check_events()
        elif p.poll() != None:
            break        

def spawn_interactive_shell(cmd):
    p = subprocess.Popen( cmd.split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True )
    outp = threading.Thread(target=process_stdout, args=(p, p.stdout))
    outp.daemon = True
    outp.start()
    errp = threading.Thread(target=process_stdout, args=(p, p.stderr))
    errp.daemon = True
    errp.start()
    chars = 0
    while p.poll() == None:
        console.idle()
        c = console.get_char()
        if p.poll () != None:
            break
        else:    
            if c in ('\r', '\n'): 
                # fix double echo after enter press
                console.write('\x1D'*chars)
                chars = 0
                p.stdin.write('\r\n')
            elif c != '':
                p.stdin.write(c)
                # windows only seems to echo this to the pipe after enter pressed
                console.write(c)
                chars +=1
    outp.join()
    errp.join()
        
