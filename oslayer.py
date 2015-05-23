"""
PC-BASIC 3.23  - oslayer.py
Operating system utilities
 
(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import os 
import subprocess
from fnmatch import fnmatch
import logging

import plat
import config
import state
import error
import console
import backend

if plat.system == 'Windows':
    import win32api
    import win32print
    import threading
    import time
    import ctypes
else:
    try:
        import pexpect
    except ImportError:
        pexpect = None    


# D all, move to iolayer
# standard drive mappings
drives = { 'Z': os.getcwd(), }
current_drive = 'Z'
# working directories; must not start with a /
state.io_state.drive_cwd = { 'Z': '', }


shell_enabled = False

native_shell = {
    'Windows': 'CMD.EXE',
    'OSX': '/bin/sh',
    'Linux': '/bin/sh',
    'Unknown_OS': '/bin/sh' }

def prepare():
    """ Initialise oslayer module. """
    global shell_enabled, shell_command

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

    if config.options['shell'] and config.options['shell'] != 'none':
        if (plat.system == 'Windows' or pexpect):
            shell_enabled = True
            if config.options['shell'] == 'native':
                shell_command = native_shell[plat.system]
            else:
                shell_command = config.options['shell']
        else:
            logging.warning('Pexpect module not found. SHELL command disabled.')    
            

#########################################
# calling shell environment

def get_env(parm):
    """ Retrieve environment string by name. """
    if not parm:
        raise error.RunError(5)
    return bytearray(os.getenv(str(parm)) or '')    
        
def get_env_entry(expr):
    """ Retrieve environment string by number. """
    envlist = list(os.environ)
    if expr > len(envlist):
        return bytearray()            
    else:
        return bytearray(envlist[expr-1] + '=' + os.getenv(envlist[expr-1]))   
    

#########################################
# shell

def shell(command):
    """ Execute a shell command or enter interactive shell. """
    # sound stops playing and is forgotten
    state.console_state.sound.stop_all_sound()
    # no key macros
    key_macros_save = state.basic_state.key_macros_off
    state.basic_state.key_macros_off = True
    # no user events
    suspend_event_save = state.basic_state.events.suspend_all
    state.basic_state.events.suspend_all = True
    # run the os-specific shell
    if shell_enabled:
        spawn_shell(command)
    else:
        logging.warning('SHELL statement disabled.')
    # re-enable key macros and event handling
    state.basic_state.key_macros_off = key_macros_save
    state.basic_state.events.suspend_all = suspend_event_save


#########################################
# implementation


#D move to iolayer
if plat.system == 'Windows':
    def map_drives():
        """ Map drives to Windows drive letters. """
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

    def short_name(path, longname):
        """ Get Windows short name or fake it. """
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
    def map_drives():
        """ Map drives to Windows drive letters. """
        global drives
        # map root to C and set current to CWD:
        cwd = os.getcwd()
        # map C to root
        drives['C'] = '/'
        state.io_state.drive_cwd['C'] = cwd[1:]
        # map Z to cwd
        drives['Z'] = cwd
        state.io_state.drive_cwd['Z'] = ''
        # map H to home
        drives['H'] = os.path.expanduser('~')
        if cwd[:len(drives['H'])] == drives['H']:
            state.io_state.drive_cwd['H'] = cwd[len(drives['H'])+1:]
        else:    
            state.io_state.drive_cwd['H'] = ''
    
    def short_name(dummy_path, longname):
        """ Get Windows short name or fake it. """
        # path is only needed on Windows     
        return split_dosname(longname.strip().upper())
   

#D move to iolayer
def split_dosname(name, defext=''):
    """ Convert filename into 8-char trunk and 3-char extension. """
    dotloc = name.find('.')
    if name in ('.', '..'):
        trunk, ext = '', name[1:]
    elif dotloc > -1:
        trunk, ext = name[:dotloc][:8], name[dotloc+1:][:3]
    else:
        trunk, ext = name[:8], defext
    return trunk, ext

#D move to iolayer
def join_dosname(trunk, ext):
    """ Join trunk and extension into file name. """
    return trunk + ('.' + ext if ext else '')

#D move to iolayer
def istype(path, native_name, isdir):
    """ Return whether a file exists and is a directory or regular. """
    name = os.path.join(str(path), str(native_name))
    try:
        return os.path.isdir(name) if isdir else os.path.isfile(name)
    except TypeError:
        # happens for name = '\0'
        return False
            
#D move to iolayer
def dossify(longname, defext=''):
    """ Put name in 8x3, all upper-case format and apply default extension. """ 
    # convert to all uppercase; one trunk, one extension
    name, ext = split_dosname(longname.strip().upper(), defext)
    if ext == None:
        ext = defext
    # no dot if no ext
    return join_dosname(name, ext)

#D move to iolayer
def match_dosname(dosname, path, isdir, find_case):
    """ Find a matching native file name for a given 8.3 DOS name. """
    # check if the dossified name exists as-is
    if istype(path, dosname, isdir):    
        return dosname
    if not find_case:    
        return None
    # for case-sensitive filenames: find other case combinations, if present
    for f in sorted(os.listdir(path)):
        if f.upper() == dosname and istype(path, f, isdir):
            return f
    return None

#D move to iolayer
def match_filename(name, defext, path='', err=53, 
                   isdir=False, find_case=True, make_new=False):
    """ Find or create a matching native file name for a given BASIC name. """
    # check if the name exists as-is; should also match Windows short names.
    # EXCEPT if default extension is not empty, in which case
    # default extension must be found first. Necessary for GW compatibility.
    if not defext and istype(path, name, isdir):
        return name
    # try to match dossified names with default extension    
    dosname = dossify(name, defext)
    fullname = match_dosname(dosname, path, isdir, find_case)
    if fullname:    
        return fullname
    # not found        
    if make_new:
        return dosname
    else:    
        raise error.RunError(err)

#D move to iolayer
def split_drive(s):
    """ Split string in drive letter and rest; return native path for drive. """ 
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
        
#D move to iolayer
def filter_names(path, files_list, mask='*.*'):
    """ Apply filename filter to short version of names. """
    all_files = [short_name(path, name) for name in files_list]
    # apply mask separately to trunk and extension, dos-style.
    # hide dotfiles
    trunkmask, extmask = split_dosname(mask)
    return sorted([(t, e) for (t, e) in all_files 
        if (fnmatch(t, trunkmask.upper()) and fnmatch(e, extmask.upper()) and
            (t or not e or e == '.'))])


if plat.system == 'Windows':
    def disk_free(path):
        """ Return the number of free bytes on the drive. """
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path), 
                                        None, None, ctypes.pointer(free_bytes))
        return free_bytes.value
elif plat.system == 'Android':
    def disk_free(path):
        """ Return the number of free bytes on the drive. """
        return 0        
else:
    def disk_free(path):
        """ Return the number of free bytes on the drive. """
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize
        
###################################################
# SHELL

if plat.system == 'Windows':
    shell_output = ''   

    def process_stdout(p, stream):
        """ Retrieve SHELL output and write to console. """
        global shell_output
        while True:
            c = stream.read(1)
            if c != '': 
                # don't access screen in this thread
                # the other thread already does
                shell_output += c
            elif p.poll() != None:
                break        
            else:
                # don't hog cpu, sleep 1 ms
                time.sleep(0.001)

    def spawn_shell(command):
        """ Run a SHELL subprocess. """
        global shell_output
        cmd = shell_command
        if command:
            cmd += ' /C "' + command + '"'            
        p = subprocess.Popen( str(cmd).split(), stdin=subprocess.PIPE, 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        outp = threading.Thread(target=process_stdout, args=(p, p.stdout))
        outp.daemon = True
        outp.start()
        errp = threading.Thread(target=process_stdout, args=(p, p.stderr))
        errp.daemon = True
        errp.start()
        word = ''
        while p.poll() == None or shell_output:
            if shell_output:
                lines, shell_output = shell_output.split('\r\n'), ''
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
                c = state.console_state.keyb.get_char()
            except error.Break:
                pass    
            if c in ('\r', '\n'): 
                # shift the cursor left so that CMD.EXE's echo can overwrite 
                # the command that's already there. Note that Wine's CMD.EXE
                # doesn't echo the command, so it's overwritten by the output...
                console.write('\x1D' * len(word))
                p.stdin.write(word + '\r\n')
                word = ''
            elif c == '\b':
                # handle backspace
                if word:
                    word = word[:-1]
                    console.write('\x1D \x1D')
            elif c != '':    
                # only send to pipe when enter is pressed
                # needed for Wine and to handle backspace properly
                word += c
                console.write(c)
        outp.join()
        errp.join()

else:
    def spawn_shell(command):
        """ Run a SHELL subprocess. """
        cmd = shell_command
        if command:
            cmd += ' -c "' + command + '"'            
        p = pexpect.spawn(str(cmd))
        while True:
            try:
                c = state.console_state.keyb.get_char()
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

