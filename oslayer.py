#
# PC-BASIC 3.23  - oslayer.py
#
# Operating system utilities
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os 
import datetime
import errno
import fnmatch
import string
from functools import partial

import error

# platform-specific:
import platform
if platform.system() == 'Windows':
    from os_windows import *
else:    
    from os_unix import *

# datetime offset for duration of the run (so that we don't need permission to touch the system clock)
# given in seconds        
time_offset = datetime.timedelta()


def timer_milliseconds():
    global time_offset
    now = datetime.datetime.today() + time_offset
    midnight = datetime.datetime(now.year, now.month, now.day)
    diff = now-midnight
    seconds = diff.seconds
    micro = diff.microseconds
    return long(seconds)*1000 + long(micro)/1000 

def safe_open(name, access):
    name = str(name)
    try:
        # create file if writing and doesn't exist yet    
        if '+' in access and not os.path.exists(name):
            open(name, 'wb').close() 
        return open(name, access)
    except EnvironmentError as e:
        handle_oserror(e)
    
def safe_lock(fd, access, locktype, length=0, start=0, whence=0):
    try:
        lock(fd, access, locktype, length, start, whence)
    except EnvironmentError as e:
        handle_oserror(e)

def safe_unlock(fd):
    try:
        unlock(fd)
    except EnvironmentError as e:
        handle_oserror(e)
        
def handle_oserror(e):        
    if e.errno in (errno.ENOENT, errno.EISDIR, errno.ENOTDIR):
        # file not found
        raise error.RunError(53)
    elif e.errno in (errno.EACCES, errno.EBUSY, errno.EROFS, errno.EPERM):
        # permission denied
        raise error.RunError(70)
    elif e.errno == errno.EEXIST:
        # file already exists
        raise error.RunError(58)
    elif e.errno == errno.ENOSPC:
        # disk full
        raise error.RunError(61) 
    elif e.errno in (errno.ENXIO, errno.ENODEV):
        # disk not ready
        raise error.RunError(71) 
    elif e.errno == errno.EIO:
        # disk media error    
        raise error.RunError(72) 
    elif e.errno == errno.ENOTEMPTY:
        # path/file access error
        raise error.RunError(75)  
    else:
        # unknown; internal error
        raise error.RunError(51)

def istype(name, isdir):
    name = str(name)
    return os.path.exists(name) and ((isdir and os.path.isdir(name)) or (not isdir and os.path.isfile(name)))
        
# put name in 8x3, all upper-case format            
def dosname_write(s, defext='BAS', path='', dummy=0, isdir_dummy=False):
    pre=path
    if path != '':
        pre += '/'
    s = s.upper()
    if '.' in s:
        name = s[:s.find('.')]
        ext = s[s.find('.')+1:]
    else:
        name = s[:8]
        ext = defext
    name = name[:8].strip()
    ext = ext[:3].strip()
    if len(ext) > 0:    
        return pre + name+'.'+ext            
    else:
        return pre + name

# if name does not exist, put name in 8x3, all upper-case format with standard extension            
def dosname_read(s, defext='BAS', path='', err=53, isdir=False):
    pre = path
    if path != '':
        pre += '/'
    if istype(pre+s, isdir):
        return s
    s = dosname_write(s, '', pre)
    if istype(pre+s, isdir):    
        return s
    if defext != '':
        s = dosname_write(s, defext, pre)
        if istype(pre+s, isdir):    
            return s
    # 53: file not found
    raise error.RunError(err)

# find a unix path to match the given dos-style path
def dospath_action(s, defext, err, action, isdir):
    # split over backslashes
    elements = string.split(s, '\\')
    name = elements.pop()
    if len(elements)>0 and elements[0] == '':
        elements[0] = '/'
    # find a matching 
    test = ''
    for e in elements:
        # skip double slashes
        if e=='':
            continue
        test += dosname_read(e, '', test, err, isdir)
        test += os.sep
    test += action(name, defext, test, err, isdir)
    return test

dospath_read = partial(dospath_action, action=dosname_read, isdir=False)
dospath_write = partial(dospath_action, action=dosname_write, isdir=False)
dospath_read_dir = partial(dospath_action, action=dosname_read, isdir=True)
dospath_write_dir = partial(dospath_action, action=dosname_write, isdir=True)

# for FILES command
# apply filename filter and DOSify names
def pass_dosnames(files, mask='*.*'):
    mask = mask.rsplit('.', 1)
    if len(mask) == 2:
        trunkmask, extmask = mask
    else:
        trunkmask = mask[0]
        extmask = ''    
    dosfiles = []
    for name in files:
        if name.find('.') > -1:
            trunk = name[:name.find('.')][:8]
            ext = name[name.find('.')+1:][:3]
        else:
            trunk = name[:8]
            ext = ''
        # non-DOSnames passed as UnixName....    
        if len(ext)>0 and name != trunk+'.'+ext:
            ext = '...'
        elif ext=='' and name != trunk and name!='.':
            ext = '...'
        if name in ('.', '..'):
            trunk = ''
            ext = ''
        # apply mask separately to trunk and extension, dos-style.
        if not fnmatch.fnmatch(trunk, trunkmask) or not fnmatch.fnmatch(ext, extmask):
            continue
        trunk += ' ' * (8-len(trunk))
        if len(ext) > 0:
            ext = '.' + ext + ' ' * (3-len(ext)) 
        elif name == '.':
            ext = '.   '
        elif name == '..':
            ext = '..  '
        else:
            ext = '    '    
        dosfiles.append(trunk+ext)
    return dosfiles


##########################

# print to LPR printer (ok for CUPS)
# TODO: Windows XP reference says it has an LPR command, but is it standard on all windows or part of a POSIX module?
def line_print(printbuf, printer_name=''):
    options = ''
    if printer_name != '':
        options += ' -P ' + printer_name
    if printbuf != '':
        pr = os.popen("lpr " + options, "w")
        pr.write(printbuf)
        pr.close()
        

