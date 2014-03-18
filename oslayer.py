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

# datetime offset for duration of the run (so that we don't need permission to touch the system clock)
# given in seconds        
time_offset = datetime.timedelta()

# posix access modes for BASIC modes INPUT ,OUTPUT, RANDOM, APPEND and internal LOAD and SAVE modes
access_modes = { 'I':'rb', 'O':'wb', 'R':'r+b', 'A':'ab', 'L': 'rb', 'S': 'wb' }
# posix access modes for BASIC ACCESS mode for RANDOM files only
access_access = { 'R': 'rb', 'W': 'wb', 'RW': 'r+b' }


def timer_milliseconds():
    global time_offset
    now = datetime.datetime.today() + time_offset
    midnight = datetime.datetime(now.year, now.month, now.day)
    diff = now-midnight
    seconds = diff.seconds
    micro = diff.microseconds
    return long(seconds)*1000 + long(micro)/1000 

def safe_open(name, mode, access):
    name = str(name)
    posix_access = access_access[access] if (access and mode == 'R') else access_modes[mode]  
    try:
        # create file if writing and doesn't exist yet    
        if '+' in posix_access and not os.path.exists(name):
            open(name, 'wb').close() 
        return open(name, posix_access)
    except EnvironmentError as e:
        handle_oserror(e)
    
def safe(fnname, *fnargs):
    try:
        return fnname(*fnargs)
    except EnvironmentError as e:
        handle_oserror(e)

os_error = {
    # file not found
    errno.ENOENT: 53, errno.EISDIR: 53, errno.ENOTDIR: 53,
    # permission denied
    errno.EAGAIN: 70, errno.EACCES: 70, errno.EBUSY: 70, errno.EROFS: 70, errno.EPERM: 70,
    # file already exists
    errno.EEXIST: 58,
    # disk full
    errno.ENOSPC: 61, 
    # disk not ready
    errno.ENXIO: 71, errno.ENODEV: 71,
    # disk media error
    errno.EIO: 72,
    # path/file access error
    errno.ENOTEMPTY: 75,
    }
        
def handle_oserror(e):        
    try:
        basic_err = os_error[e.errno]
    except KeyError:
        # unknown; internal error
        basic_err = 51
    raise error.RunError(basic_err) 

def istype(name, isdir):
    name = str(name)
    return os.path.exists(name) and ((isdir and os.path.isdir(name)) or (not isdir and os.path.isfile(name)))
        
# put name in 8x3, all upper-case format            
def dosname_write(s, defext='BAS', path='', dummy=0, isdir_dummy=False):
    pre = str(path)
    if path:
        pre += os.sep
    s = s.upper()
    if '.' in s:
        name = s[:s.find('.')]
        ext = s[s.find('.')+1:]
    else:
        name = s[:8]
        ext = defext
    name = name[:8].strip()
    ext = ext[:3].strip()
    if ext:    
        return pre + name+'.'+ext            
    else:
        return pre + name

# if name does not exist, put name in 8x3, all upper-case format with standard extension            
def dosname_read(s, defext='BAS', path='', err=53, isdir=False):
    pre = str(path)
    if path:
        pre += os.sep
    if istype(pre+s, isdir):
        return s
    s = dosname_write(s, '', pre)
    if istype(pre+s, isdir):    
        return s
    if defext:
        s = dosname_write(s, defext, pre)
        if istype(pre+s, isdir):    
            return s
    # 53: file not found
    raise error.RunError(err)

# find a unix path to match the given dos-style path
def dospath(s, defext, err, action, isdir):
    # split over backslashes
    elements = string.split(s, '\\')
    name = elements.pop()
    if len(elements) > 0 and elements[0] == '':
        elements[0] = os.sep
    # find a matching 
    test = ''
    for e in elements:
        # skip double slashes
        if e:
            test += dosname_read(e, '', test, err, True) + os.sep
    return action(name, defext, test, err, isdir)

dospath_read = partial(dospath, action=dosname_read, isdir=False)
dospath_write = partial(dospath, action=dosname_write, isdir=False)
dospath_read_dir = partial(dospath, action=dosname_read, isdir=True)
dospath_write_dir = partial(dospath, action=dosname_write, isdir=True)

# for FILES command
# apply filename filter and DOSify names
def pass_dosnames(files, mask='*.*'):
    mask = mask.rsplit('.', 1)
    if len(mask) == 2:
        trunkmask, extmask = mask
    else:
        trunkmask, extmask = mask[0], ''
    dosfiles = []
    for name in files:
        if name.find('.') > -1:
            trunk, ext = name[:name.find('.')][:8], name[name.find('.')+1:][:3]
        else:
            trunk, ext = name[:8], ''
        # non-DOSnames passed as UnixName....    
        if (ext and name != trunk+'.'+ext) or (ext == '' and name != trunk and name != '.'):
            ext = '...'
        if name in ('.', '..'):
            trunk, ext = '', ''
        # apply mask separately to trunk and extension, dos-style.
        if not fnmatch.fnmatch(trunk, trunkmask) or not fnmatch.fnmatch(ext, extmask):
            continue
        trunk += ' ' * (8-len(trunk))
        if ext:
            ext = '.' + ext + ' ' * (3-len(ext)) 
        elif name == '.':
            ext = '.   '
        elif name == '..':
            ext = '..  '
        else:
            ext = '    '    
        dosfiles.append(trunk + ext)
    return dosfiles

# print to LPR printer (ok for CUPS)
# TODO: use Windows printing subsystem for Windows, LPR is not standard there.
def line_print(printbuf, printer_name=''):
    options = ''
    if printer_name != '':
        options += ' -P ' + printer_name
    if printbuf != '':
        pr = os.popen("lpr " + options, "w")
        pr.write(printbuf)
        pr.close()
        
# platform-specific:
import platform
if platform.system() == 'Windows':
    from os_windows import *
else:    
    from os_unix import *

