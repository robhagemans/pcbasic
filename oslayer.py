#
# PC-BASIC 3.23  - oslayer.py
#
# Operating system utilities
# 
# (c) 2013, 2014 Rob Hagemans 
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
import StringIO

import error

# datetime offset for duration of the run (so that we don't need permission to touch the system clock)
# given in seconds        
time_offset = datetime.timedelta()

# posix access modes for BASIC modes INPUT ,OUTPUT, RANDOM, APPEND and internal LOAD and SAVE modes
access_modes = { 'I':'rb', 'O':'wb', 'R':'r+b', 'A':'ab', 'L': 'rb', 'S': 'wb' }
# posix access modes for BASIC ACCESS mode for RANDOM files only
access_access = { 'R': 'rb', 'W': 'wb', 'RW': 'r+b' }

os_error = {
    # file not found
    errno.ENOENT: 53, errno.EISDIR: 53, errno.ENOTDIR: 53,
    # permission denied
    errno.EAGAIN: 70, errno.EACCES: 70, errno.EBUSY: 70, errno.EROFS: 70, errno.EPERM: 70,
    # disk full
    errno.ENOSPC: 61, 
    # disk not ready
    errno.ENXIO: 71, errno.ENODEV: 71,
    # disk media error
    errno.EIO: 72,
    # path/file access error
    errno.EEXIST: 75, errno.ENOTEMPTY: 75,
    }

nullstream = open(os.devnull, 'w')       

def timer_milliseconds():
    global time_offset
    now = datetime.datetime.today() + time_offset
    midnight = datetime.datetime(now.year, now.month, now.day)
    diff = now-midnight
    seconds = diff.seconds
    micro = diff.microseconds
    return long(seconds)*1000 + long(micro)/1000 

def set_time(timestr):    
    global time_offset
    now = datetime.datetime.today() + time_offset
    timelist = [0, 0, 0]
    pos, listpos, word = 0, 0, ''
    while pos < len(timestr):
        if listpos > 2:
            break
        c = chr(timestr[pos])
        if c in (':', '.'):
            timelist[listpos] = int(word)
            listpos += 1
            word = ''
        elif (c < '0' or c > '9'): 
            raise error.RunError(5)
        else:
            word += c
        pos += 1
    if word:
        timelist[listpos] = int(word)     
    if timelist[0] > 23 or timelist[1] > 59 or timelist[2] > 59:
        raise error.RunError(5)
    newtime = datetime.datetime(now.year, now.month, now.day, timelist[0], timelist[1], timelist[2], now.microsecond)
    time_offset += newtime - now    
        
def set_date(datestr):    
    global time_offset
    now = datetime.datetime.today() + time_offset
    datelist = [1, 1, 1]
    pos, listpos, word = 0, 0, ''
    if len(datestr) < 8:
        raise error.RunError(5)
    while pos < len(datestr):
        if listpos > 2:
            break
        c = chr(datestr[pos])
        if c in ('-', '/'):
            datelist[listpos] = int(word)
            listpos += 1
            word = ''
        elif (c < '0' or c > '9'): 
            if listpos == 2:
                break
            else:
                raise error.RunError(5)
        else:
            word += c
        pos += 1
    if word:
        datelist[listpos] = int(word)     
    if (datelist[0] > 12 or datelist[1] > 31 or
            (datelist[2] > 77 and datelist[2] < 80) or 
            (datelist[2] > 99 and datelist[2] < 1980 or datelist[2] > 2099)):
        raise error.RunError(5)
    if datelist[2] <= 77:
        datelist[2] = 2000 + datelist[2]
    elif datelist[2] < 100 and datelist[2] > 79:
        datelist[2] = 1900 + datelist[2]
    try:
        newtime = datetime.datetime(datelist[2], datelist[0], datelist[1], now.hour, now.minute, now.second, now.microsecond)
    except ValueError:
        raise error.RunError(5)
    time_offset += newtime - now    
    
def get_time():
    return bytearray((datetime.datetime.today() + time_offset).strftime('%H:%M:%S'))
    
def get_date():
    return bytearray((datetime.datetime.today() + time_offset).strftime('%m-%d-%Y'))

def get_env(parm):
    if not parm:
        raise error.RunError(5)
    val = os.getenv(str(parm))
    if val == None:
        val = ''
    return bytearray(val)    
        
def get_env_entry(expr):
    envlist = list(os.environ)
    if expr > len(envlist):
        return bytearray()            
    else:
        val = os.getenv(envlist[expr-1])
        return bytearray(envlist[expr-1] + '=' + val)   
    
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
 
def handle_oserror(e):        
    try:
        basic_err = os_error[e.errno]
    except KeyError:
        # unknown; internal error
        basic_err = 51
    raise error.RunError(basic_err) 

#############################

def istype(name, isdir):
    name = str(name)
    return os.path.exists(name) and ((isdir and os.path.isdir(name)) or (not isdir and os.path.isfile(name)))
        
# put name in 8x3, all upper-case format          
    #    # cryptic errors given by GW-BASIC:    
    #    if ext.find('.') > -1:
    #        # 53: file not found
    #        raise error.RunError(errdots)
def dosname_write(s, defext='BAS', path='', dummy=0, isdir_dummy=False):
    if not s:
        raise error.RunError(64)
    pre = replace_drive(str(path))
    if path and pre[-1] != os.sep:
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

def replace_drive(pre):
    # get drive letter, if any
    drivepath = string.split(pre, ':')
    if len(drivepath) > 1:
        pre = os.path.join(get_drive(drivepath[0]), drivepath[-1])
    else:
        pre = os.path.join(get_drive(''), drivepath[-1])
    return pre

# if name does not exist, put name in 8x3, all upper-case format with standard extension            
def dosname_read(s, defext='BAS', path='', err=53, isdir=False):
    if not s:
        raise error.RunError(64)
    pre = replace_drive(str(path))
    if path and pre[-1] != os.sep:
        pre += os.sep
    if istype(pre+s, isdir):
        return pre+s
    full = dosname_write(s, '', pre)
    if istype(full, isdir):    
        return full
    if defext:
        full = dosname_write(s, defext, pre)
        if istype(full, isdir):    
            return full
    raise error.RunError(err)

# find a unix path to match the given dos-style path
def dospath(s, defext, err, action, isdir):
    drivepath = s.split(':')
    if len(drivepath) > 1:
        test = drivepath[0] + ":"
        s = drivepath[1]    
    else:
        test = ''    
    # split over backslashes
    elements = s.split('\\')
    name = elements.pop()
    if elements:
        if elements[0] == '':
            elements[0] = os.sep
    # find a matching 
    for e in elements:
        # skip double slashes
        if e:
            test = dosname_read(e, '', test, err, True) + os.sep
    if name:
        return action(name, defext, test, err, isdir)
    else:
        # no file name, just dirs
        return replace_drive(test)     

dospath_read = partial(dospath, action=dosname_read, isdir=False)
dospath_write = partial(dospath, action=dosname_write, isdir=False)
dospath_read_dir = partial(dospath, action=dosname_read, isdir=True)
dospath_write_dir = partial(dospath, action=dosname_write, isdir=True)

# for FILES command
# apply filename filter and DOSify names
def pass_dosnames(path, files, mask='*.*'):
    mask = mask.rsplit('.', 1)
    if len(mask) == 2:
        trunkmask, extmask = mask
    else:
        trunkmask, extmask = mask[0], ''
    dosfiles = []
    for name in files:
        trunk, ext = dossify(path, name)
        # apply mask separately to trunk and extension, dos-style.
        if not fnmatch.fnmatch(trunk.upper(), trunkmask.upper()) or not fnmatch.fnmatch(ext.upper(), extmask.upper()):
            continue
        if not trunk and ext and ext != '.':
            # hide dotfiles
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

def files(pathmask, console):
    path, mask = '.', '*.*'
    pathmask = str(pathmask)
    # get drive letter
    drivepath = pathmask.split(':')
    if len(drivepath) > 1:
        drive = drivepath[0] + ":"
        pathmask = drivepath[1]    
    else:
        drive = ''  
    # split path and mask    
    pathmask = pathmask.rsplit('\\', 1)
    if len(pathmask) > 1:
        path = str(pathmask[0])
        path = path if path else '\\'
        mask = str(pathmask[1])
    else:
        if pathmask[0]:
            mask = str(pathmask[0]) 
    path = drive + path                  
    mask = mask.upper()
    if mask == '':
        mask = '*.*'
#    # get top level directory for '.'
    path = dospath_read_dir(path, '', 53)
    path = os.path.abspath(path)
    roots, dirs, files = [], [], []
    for root, dirs, files in safe(os.walk, path):
        break
    # get working dir, replace / with \
    # NOTE: this is always the current dir, not the one being listed
    # FIXME: shld be current dir *on the drive we look at*
    console.write(dossify_path(os.getcwd()) + '\n')
    if (roots, dirs, files) == ([], [], []):
        raise error.RunError(53)
    dosfiles = pass_dosnames(path, files, mask)
    dosfiles = [ name+'     ' for name in dosfiles ]
    dirs += ['.', '..']
    dosdirs = pass_dosnames(path, dirs, mask)
    dosdirs = [ name+'<DIR>' for name in dosdirs ]
    #dosdirs += [ '        .   <DIR>', '        ..  <DIR>' ]
    dosfiles.sort()
    dosdirs.sort()    
    output = dosdirs + dosfiles
    num = console.width/20
    if len(output) == 0:
        # file not found
        raise error.RunError(53)
    while len(output) > 0:
        line = ' '.join(output[:num])
        output = output[num:]
        console.write(line+'\n')       
        # allow to break during dir listing & show names flowing on screen
        console.check_events()             
    console.write(' ' + str(disk_free(path)) + ' Bytes free\n')

    
# print to CUPS or windows printer    
class CUPSStream(StringIO.StringIO):
    def __init__(self, printer_name=''):
        self.printer_name = printer_name
        StringIO.StringIO.__init__(self)

    def close(self):
        self.flush()

    # flush buffer to Windows printer    
    def flush(self):
        printbuf = self.getvalue()
        if not printbuf:
            return      
        self.truncate(0)
        utf8buf = ''
        for c in printbuf:
            utf8buf += unicodepage.cp_to_utf8[printbuf]
        line_print(utf8buf, self.printer_name)

        
# platform-specific:
import platform
if platform.system() == 'Windows':
    from os_windows import *
else:    
    from os_unix import *

