#
# PC-BASIC 3.23  - os_unix.py
#
# UNIX-specific OS utilities
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os
import fcntl
import pexpect
import console
import unicodepage    
    
shell = '/bin/sh'
shell_cmd = shell + ' -c'


def disk_free(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize
    
def spawn_interactive_shell(cmd):
    try:
        p = pexpect.spawn(str(cmd))
    except Exception:
        return 
    while True:
        c = console.get_char()
        if c == '\b': # BACKSPACE
            p.send('\x7f')
        elif c != '':
            p.send(c)
        while True:
            try:
                c = p.read_nonblocking(1, timeout=0)
            except: 
                c = ''
            if c == '' or c == '\n':
                break
            elif c == '\r':
                console.write_line()    
            elif c == '\b':
                if console.col != 1:
                    console.col -= 1
            else:
                console.write(c)
        if c == '' and not p.isalive(): 
            return
            
# change names in FILES to some 8.3 variant             
def dossify(name):
    if name.find('.') > -1:
        trunk, ext = name[:name.find('.')][:8], name[name.find('.')+1:][:3]
    else:
        trunk, ext = name[:8], ''
    # non-DOSnames passed as UnixName....    
    if (ext and name != trunk+'.'+ext) or (ext == '' and name != trunk and name != '.'):
        ext = '...'
    if name in ('.', '..'):
        trunk, ext = '', ''
    return trunk, ext

def dossify_path(path):
    dospath = 'Z:'
    for name in path.split(os.sep):
        trunk, ext = dossify(name)
        if trunk == '' and ext == '':
            continue    
        dospath += '\\' + trunk
        if ext:
            dospath += '.' + ext
    return dospath        
            
# print to LPR printer (ok for CUPS)
def line_print(printbuf, printer_name): 
    options = ''
    if printer_name != '' and printer_name != 'default':
        options += ' -P ' + printer_name
    if printbuf != '':
        pr = os.popen("lpr " + options, "w")
        pr.write(printbuf)
        pr.close()
            
