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
import subprocess
import errno
from fnmatch import fnmatch
from functools import partial
import StringIO
import logging

import config
import error
import console
import unicodepage
import plat
import state
import backend
import time


if plat.system == 'Windows':
    #import msvcrt
    #import win32ui
    #import win32gui
    import win32api
    #import win32con
    import win32print
    import tempfile
    import subprocess
    import threading
else:
    try:
        import pexpect
    except ImportError:
        import logging
        logging.warning('Pexpect module not found. SHELL command will not work.')    
    

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


def prepare():
    """ Initialise oslayer module. """
    for a in config.options['mount']:
        try:
            # the last one that's specified will stick
            letter, path = a.split(':', 1)
            path = os.path.realpath(path)
            if not os.path.isdir(path):
                logging.warning('Could not mount %s', a)
            else:    
                drives[letter.upper()] = path
                state.io_state.drive_cwd[letter.upper()] = ''
        except (TypeError, ValueError):
            logging.warning('Could not mount %s', a)
    if config.options['map-drives']:
        map_drives()


#########################################
# environment

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
# open a file & catch errors

def open_file(native_name, mode, access):
    name = str(native_name)
    posix_access = access_access[access] if (access and mode == 'R') else access_modes[mode]  
    try:
        # create file if writing and doesn't exist yet    
        if '+' in posix_access and not os.path.exists(name):
            open(name, 'wb').close() 
        return open(name, posix_access)
    except EnvironmentError as e:
        handle_oserror(e)

#########################################
# drives & paths

drives = { 'C': os.getcwd(), '@': os.path.join(plat.basepath, 'info') }
current_drive = 'C'
# must not start with a /
state.io_state.drive_cwd = { 'C': '', '@': '' }

def chdir(name):
    # substitute drives and cwds
    letter, drivepath, relpath, _ = native_path_elements(name, err=76, join_name=True)
    # if cwd is shorter than drive prefix (like when we go .. on a drive letter root), this is just an empty path, ie the root.    
    state.io_state.drive_cwd[letter] = relpath
    if letter == current_drive:
        safe(os.chdir, os.path.join(drivepath, relpath))

def mkdir(name):
    safe(os.mkdir, native_path(name, err=76, isdir=True, make_new=True))
    
def rmdir(name):    
    safe(os.rmdir, native_path(name, err=76, isdir=True))

def kill(name):
    safe(os.remove, native_path(name, find_case=False))

def files(pathmask):
    # forward slashes - file not found
    # GW-BASIC sometimes allows leading or trailing slashes
    # and then does weird things I don't understand. 
    if '/' in str(pathmask):
        raise error.RunError(53)   
    drive, drivepath, relpath, mask = native_path_elements(pathmask, err=53)
    path = os.path.join(drivepath, relpath)
    mask = mask.upper() or '*.*'
    all_names = safe(os.listdir, path)
    dirs = [n for n in all_names if os.path.isdir(os.path.join(path, n))]
    fils = [n for n in all_names if not os.path.isdir(os.path.join(path, n))]
    # output working dir in DOS format
    # NOTE: this is always the current dir, not the one being listed
    console.write_line(drive + ':\\' + state.io_state.drive_cwd[drive].replace(os.sep, '\\'))
    # filter according to mask
    dirs = filter_names(path, dirs + ['.', '..'], mask)
    fils = filter_names(path, fils, mask)
    if not dirs and not fils:
        raise error.RunError(53)
    # format and print contents
    output = ( 
          [('%-8s.%-3s' % (t, e) if (e or not t) else '%-8s    ' % t) + '<DIR>' for t, e in dirs]
        + [('%-8s.%-3s' % (t, e) if e else '%-8s    ' % t) + '     ' for t, e in fils])
    num = state.console_state.width // 20
    while len(output) > 0:
        line = ' '.join(output[:num])
        output = output[num:]
        console.write_line(line)       
        # allow to break during dir listing & show names flowing on screen
        backend.check_events()             
    console.write_line(' %d Bytes free' % disk_free(path))
    
def rename(oldname, newname):    
    oldname = native_path(str(oldname), err=53, isdir=False)
    newname = native_path(str(newname), err=76, isdir=False, make_new=True)
    if os.path.exists(newname):
        # file already exists
        raise error.RunError(58)
    safe(os.rename, oldname, newname)

# find a unix path to match the given dos-style path
def native_path(path_and_name, defext='', err=53, isdir=False, find_case=True, make_new=False):
    # substitute drives and cwds
    _, drivepath, relpath, name = native_path_elements(path_and_name, err)
    # return absolute path to file        
    path = os.path.join(drivepath, relpath)
    if name:
        path = os.path.join(path, match_filename(name, defext, path, err, isdir, find_case, make_new))
    # get full normalised path
    return os.path.abspath(path)

#########################################
# shell

def shell(command):
    # sound stops playing and is forgotten
    backend.stop_all_sound()
    # no key macros
    key_macros_save = state.basic_state.key_macros_off
    state.basic_state.key_macros_off = True
    # no user events
    suspend_event_save = state.basic_state.suspend_all_events
    state.basic_state.suspend_all_events = True
    # run the os-specific shell
    spawn_shell(command)
    # re-enable key macros and event handling
    state.basic_state.key_macros_off = key_macros_save
    state.basic_state.suspend_all_events = suspend_event_save



#########################################
# implementation
 
if plat.system == 'Windows':
    def map_drives():
        global current_drive
        # get all drives in use by windows
        # if started from CMD.EXE, get the 'current working dir' for each drive
        # if not in CMD.EXE, there's only one cwd
        current_drive = os.path.abspath(os.getcwd()).split(':')[0]
        save_current = os.getcwd()
        for drive_letter in win32api.GetLogicalDriveStrings().split(':\\\x00')[:-1]:
            try:
                os.chdir(drive_letter + ':')
                cwd = win32api.GetShortPathName(os.getcwd())
                # must not start with \\
                state.io_state.drive_cwd[drive_letter] = cwd[3:]  
                drives[drive_letter] = cwd[:3]
            except WindowsError:
                pass    
        os.chdir(save_current)    

    # get windows short name
    def short_name(path, longname):
        if not path:
            path = current_drive
        path_and_longname = os.path.join(str(path), str(longname)) 
        try:
            # gets the short name if it exists, keeps long name otherwise
            path_and_name = win32api.GetShortPathName(path_and_longname)
        except WindowsError:
            # something went wrong - keep long name (happens for swap file)
            path_and_name = path_and_longname
        # last element of path is name    
        name = path_and_name.split(os.sep)[-1]
        # if we still have a long name, shorten it now
        return split_dosname(name.strip().upper())
        
else:
# to map root to C and set current to CWD:
#    drives = { 'C': '/', '@': os.path.join(plat.basepath, 'info') }
#    state.io_state.drive_cwd = { 'C': os.getcwd()[1:], '@': '' }
    
    def map_drives():
        pass
    
    # change names in FILES to uppercase 8.3
    # path is only needed for Windows     
    def short_name(dummy_path, longname):
        return split_dosname(longname.strip().upper())
   

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
        
def split_dosname(name):
    if name in ('.', '..'):
        trunk, ext = '', name[1:]
    elif name.find('.') > -1:
        trunk, ext = name[:name.find('.')][:8], name[name.find('.')+1:][:3]
    else:
        trunk, ext = name[:8], ''
    return trunk, ext

def join_dosname(trunk, ext):
    return trunk + ('.' + ext if ext else '')

def istype(path, native_name, isdir):
    name = os.path.join(str(path), str(native_name))
    return os.path.exists(name) and ((isdir and os.path.isdir(name)) or (not isdir and os.path.isfile(name)))
        
# put name in 8x3, all upper-case format the way GW-BASIC does it (differs from Windows short name)         
def dossify(longname, defext=''):
    # convert to all uppercase
    # one trunk, one extension
    name, ext = split_dosname(longname.strip().upper())
    if not ext:
        ext = defext
    # no dot if no ext
    return join_dosname(name, ext)

def match_dosname(dosname, path, isdir, find_case):
    # check if the dossified name exists with no extension if none given   
    if istype(path, dosname, isdir):    
        return dosname
    if not find_case:    
        return None
    # for case-sensitive filenames: find other case combinations, if present
    listdir = sorted(os.listdir(path))
    capsdict = {}
    for f in listdir:
        caps = dossify(f, '')
        if caps in capsdict:
            capsdict[caps] += [f]
        else:
            capsdict[caps] = [f]
    try:
        for scaps in capsdict[dosname]:
            if istype(path, scaps, isdir):
                return scaps
    except KeyError:
        return None

# find a matching file/dir to read
# if name does not exist, put name in 8x3, all upper-case format with standard extension            
def match_filename(name, defext='BAS', path='', err=53, isdir=False, find_case=True, make_new=False):
    # check if the name exists as-is
    # this should also match Windows short filenames
    if istype(path, name, isdir):
        return name
    # try to match dossified names with and without default extension    
    for ext in (('', defext) if defext else ('',)):    
        dosname = dossify(name, ext)
        fullname = match_dosname(dosname, path, isdir, find_case)
        if fullname:    
            return fullname
    # not found        
    if make_new:
        return dosname
    else:    
        raise error.RunError(err)


def split_drive(s):
    s = str(s)
    # don't accept forward slashes, they confuse issues.
    if '/' in s:
        # bad file number - this is what GW produces here
        raise error.RunError(52)   
    drive_and_path = s.split(':')
    if len(drive_and_path) > 1:
        letter, remainder = drive_and_path[0].upper(), drive_and_path[1]
    else:
        # no drive specified, use current drive & dir
        letter, remainder = current_drive, s
    try:    
        drivepath = drives[letter]
    except KeyError:        
        # path not found
        raise error.RunError(76)   
    return letter, drivepath, remainder
        
# substitute drives and cwds    
def native_path_elements(s, err, join_name=False): 
    letter, drivepath, s = split_drive(s)
    # get path below drive letter
    relpath = '' 
    if not s or s[0] != '\\':
        relpath = state.io_state.drive_cwd[letter]
    # split into path elements and strip whitespace
    elements = [ e.strip() for e in relpath.split(os.sep) + s.split('\\') ]
    # whatever's after the last \\ is the name of the subject file or dir
    # if the path ends in \\, there's no name
    name = '' if (join_name or not elements) else elements.pop()
    # drop .. at top of relpath (don't go outside of 'drive')
    # parse internal .. and . (like normpath)
    i = 0
    while i < len(elements):
        if elements[i] == '.':
            del elements[i]
        elif elements[i] == '..':
            del elements[i]     
            if i > 0:
                del elements[i-1]
                i -= 1
        else:
            i += 1
    # find a matching directory for every step in the path; append found name to path
    path = drivepath
    # include joining slash
    baselen = len(drivepath) + 1
    # find the native matches for each step in the path 
    for e in elements:
        # skip double slashes
        if e:
            path = os.path.join(path, match_filename(e, '', path, err, isdir=True))
    return letter, drivepath, path[baselen:], name
    

# apply filename filter to short names
def filter_names(path, files_list, mask='*.*'):
    all_files = [short_name(path, name) for name in files_list]
    # apply mask separately to trunk and extension, dos-style.
    # hide dotfiles
    trunkmask, extmask = split_dosname(mask)
    return sorted([(t, e) for (t, e) in all_files 
        if (fnmatch(t, trunkmask.upper()) and fnmatch(e, extmask.upper()) and
            t or not e or e == '.')])
        
###################################################
# FILES: disk_free

if plat.system == 'Windows':
    import ctypes
    def disk_free(path):
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value

elif plat.system == 'Android':
    def disk_free(path):
        # TODO: implement with jnius
        return 0        

else:
    def disk_free(path):
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize
        
###################################################
# SHELL

if plat.system == 'Windows':
    shell_output = ''   
    # 1 ms sleep time for output process
    sleep_time = 0.001

    def process_stdout(p, stream):
        global shell_output
        while True:
            c = stream.read(1)
            if c != '': 
                # don't access screen in this thread, the other thread already does
                shell_output += c
            elif p.poll() != None:
                break        
            else:
                # don't hog cpu
                time.sleep(sleep_time)

    def spawn_shell(command):
        global shell_output
        if not command:
            command = 'CMD'
        p = subprocess.Popen( str(command).split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True )
        outp = threading.Thread(target=process_stdout, args=(p, p.stdout))
        outp.daemon = True
        outp.start()
        errp = threading.Thread(target=process_stdout, args=(p, p.stderr))
        errp.daemon = True
        errp.start()
        word = ''
        while p.poll() == None or shell_output:
            if shell_output:
                lines = shell_output.split('\r\n')
                shell_output = '' 
                last = lines.pop()
                for line in lines:
                    # progress visible - keep updating the backend
                    # don't process anything but video events here
                    backend.video.check_events()
                    console.write_line(line)
                console.write(last)    
            if p.poll() != None:
                # drain output then break
                continue    
            try:    
                c = backend.get_char()
            except error.Break:
                pass    
            if c in ('\r', '\n'): 
                # Windows CMD.EXE echo to overwrite the command that's already there
                # NOTE: WINE cmd.exe doesn't echo the command, so it's overwritten by the output...
                console.write('\x1D' * len(word))
                p.stdin.write(word + '\r\n')
                word = ''
            elif c == '\b':
                # handle backspace
                if word:
                    word = word[:-1]
                    console.write('\x1D \x1D')
            elif c != '':    
                # only send to pipe when enter pressed rather than p.stdin.write(c)
                # workaround for WINE - it seems to attach a CR to each letter sent to the pipe. not needed in proper Windows.
                # also needed to handle backsapce properly
                word += c
                console.write(c)
        outp.join()
        errp.join()

else:
    def spawn_shell(command):
        cmd = '/bin/sh'
        if command:
            cmd += ' -c "' + command + '"'            
        try:
            p = pexpect.spawn(str(cmd))
        except Exception:
            return 
        while True:
            try:
                c = backend.get_char()
            except error.Break:
                # ignore ctrl+break in SHELL
                pass
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
                    if state.console_state.col != 1:
                        console.set_pos(state.console_state.row, 
                                        state.console_state.col-1)
                else:
                    console.write(c)
            if c == '' and not p.isalive(): 
                return

prepare()

