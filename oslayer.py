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
import unicodepage

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

#########################################
# date & time & env

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
    
#########################################
# error handling

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

        
#########################################
# drives & paths

def istype(path, name, isdir):
    name = os.path.join(str(path), str(name))
    return os.path.exists(name) and ((isdir and os.path.isdir(name)) or (not isdir and os.path.isfile(name)))
        
# put name in 8x3, all upper-case format the was GW-BASIC does it (differs from Windows short name)         
#    # cryptic errors given by GW-BASIC:    
#    if ext.find('.') > -1:
#        # 53: file not found
#        raise error.RunError(errdots)
def dossify_write(s, defext='BAS', dummy_path='', dummy_err=0, dummy_isdir=False):
    # convert to all uppercase
    s = s.upper()
    # one trunk, one extension
    if '.' in s:
        name, ext = s.split('.', 1)
    else:
        name, ext = s, defext
    # 8.3, no spaces
    name, ext = name[:8].strip(), ext[:3].strip()
    # no dot if no ext
    return name + ('.' + ext if ext else '')

# find a matching file/dir to read
# if name does not exist, put name in 8x3, all upper-case format with standard extension            
def find_name_read(s, defext='BAS', path='', err=53, isdir=False):
    # check if the name exists as-is
    if istype(path, s, isdir):
        return s
    # check if the dossified name exists with no extension if none given   
    full = dossify_write(s, '', path)
    if istype(path, full, isdir):    
        return full
    # check if the dossified name exists with a default extension
    if defext:
        full = dossify_write(s, defext, path)
        if istype(path, full, isdir):    
            return full
    # not found        
    raise error.RunError(err)
        
# substitute drives and cwds    
def get_drive_path(s, err):    
    drivepath = s.split(':')
    if len(drivepath) > 1:
        letter, s = drivepath[0].upper(), drivepath[1]
    else:
        # no drive specified, use current drive & dir
        letter = current_drive
    try:    
        if not s or s[0] != '\\':
            # relative path
            path = os.path.join(drives[letter], drive_cwd[letter])
        else:
            # absolute path
            path = drives[letter] 
            s = s[1:]
    except KeyError:        
        # path not found
        raise error.RunError(76)   
    # split relative path over backslashes
    elements = s.split('\\')
    # whatever's after the last \\ is the name of the subject file or dir
    name = elements.pop()
    # find a matching directory for every step in the path; append found name to path
    for e in elements:
        # skip double slashes
        if e:
            path = os.path.join(path, find_name_read(e, '', path, err, True))
    return letter, path, name
    
# find a unix path to match the given dos-style path
def dospath(s, defext, err, action, isdir):
    # substitute drives and cwds
    _, path, name = get_drive_path(str(s), err)
    # return absolute path to file        
    if name:
        return os.path.join(path, action(name, defext, path, err, isdir))
    else:
        # no file name, just dirs
        return path

dospath_read = partial(dospath, action=find_name_read, isdir=False)
dospath_write = partial(dospath, action=dossify_write, isdir=False)
dospath_read_dir = partial(dospath, action=find_name_read, isdir=True)
dospath_write_dir = partial(dospath, action=dossify_write, isdir=True)

    
# for FILES command
# apply filename filter and DOSify names
def pass_dosnames(path, files, mask='*.*'):
    mask = str(mask).rsplit('.', 1)
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
    drive, path, mask = get_drive_path(str(pathmask), 53)
    mask = mask.upper()
    if mask == '':
        mask = '*.*'
    roots, dirs, files = [], [], []
    for root, dirs, files in safe(os.walk, path):
        break
    # get working dir in DOS format
    # NOTE: this is always the current dir, not the one being listed
    console.write_line(drive + ':\\' + drive_cwd[drive].replace(os.sep, '\\'))
    if (roots, dirs, files) == ([], [], []):
        raise error.RunError(53)
    dosfiles = pass_dosnames(path, files, mask)
    dosfiles = [ name+'     ' for name in dosfiles ]
    dirs += ['.', '..']
    dosdirs = pass_dosnames(path, dirs, mask)
    dosdirs = [ name+'<DIR>' for name in dosdirs ]
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
        console.write_line(line)       
        # allow to break during dir listing & show names flowing on screen
        console.check_events()             
    console.write_line(' ' + str(disk_free(path)) + ' Bytes free')

def chdir(name):
    # substitute drives and cwds
    letter, path, name = get_drive_path(str(name), 76)
    if name:
        newdir = os.path.abspath(os.path.join(path, find_name_read(name, '', path, 76, True)))
    else:
        newdir = path    
    base = len(drives[letter])
    if drives[letter][base-1] == os.sep:
        # root /
        base -= 1
    # if cwd is shorter than drive prefix (like when we go .. on a drive letter root), this is just an empty path, ie the root.    
    drive_cwd[letter] = newdir[base+1:]
    if letter == current_drive:
        safe(os.chdir, newdir)

def mkdir(name):
    safe(os.mkdir, dospath_write_dir(str(name), '', 76))
    
def rmdir(name):    
    safe(os.rmdir, dospath_read_dir(str(name), '', 76))
    
def rename(oldname, newname):    
    oldname = dospath_read(str(oldname), '', 53)
    newname = dospath_write(str(newname), '', 76)
    if os.path.exists(newname):
        # file already exists
        raise error.RunError(58)
    safe(os.rename, oldname, newname)
        
    
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

