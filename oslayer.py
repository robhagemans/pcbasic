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
import errno
import fnmatch
from functools import partial
import StringIO

import error
import console
import unicodepage
import plat
import state
import backend
import time

# 1 ms sleep time for output process
sleep_time = 0.001

if plat.system == 'Windows':
    import msvcrt
    import win32ui
    import win32gui
    import win32api
    import win32con
    import win32print
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

nullstream = open(os.devnull, 'w')       

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

drives = { 'C': os.getcwd(), '@': os.path.join(plat.basepath, 'info') }
current_drive = 'C'
# must not start with a /
drive_cwd = { 'C': '', '@': '' }

if plat.system == 'Windows':
    def windows_map_drives():
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
                drive_cwd[drive_letter] = cwd[3:]  
                drives[drive_letter] = cwd[:3]
            except WindowsError:
                pass    
        os.chdir(save_current)    

    # get windows short name
    def dossify(path, name):
        if not path:
            path = current_drive
        try:
            shortname = win32api.GetShortPathName(os.path.join(path, name)).upper()
        except WindowsError:
            # something went wrong, show as dots in FILES
            return "........", "..."
        split = shortname.split('\\')[-1].split('.')
        trunk, ext = split[0], ''
        if len(split)>1:
            ext = split[1]
        if len(trunk)>8 or len(ext)>3:
            # on some file systems, ShortPathName returns the long name
            trunk = trunk[:8]
            ext = '...'    
        return trunk, ext    

    # assume Windows filesystems all case insensitive
    # if you're using this with an EXT2 partition on Windows, you're just weird ;)
    def find_name_case(s, path, isdir):
        return None
        
else:
# to map root to C and set current to CWD:
#    drives = { 'C': '/', '@': os.path.join(plat.basepath, 'info') }
#    drive_cwd = { 'C': os.getcwd()[1:], '@': '' }
    
    def windows_map_drives():
        pass
    
    # change names in FILES to some 8.3 variant             
    def dossify(path, name):
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
   
    def find_name_case(s, path, isdir):
        listdir = sorted(os.listdir(path))
        capsdict = {}
        for f in listdir:
            caps = dossify_write(f, '', path)
            if caps in capsdict:
                capsdict[caps] += [f]
            else:
                capsdict[caps] = [f]
        try:
            for scaps in capsdict[dossify_write(s, '', path)]:
                if istype(path, scaps, isdir):
                    return scaps
        except KeyError:
            return None


def istype(path, name, isdir):
    name = os.path.join(str(path), str(name))
    return os.path.exists(name) and ((isdir and os.path.isdir(name)) or (not isdir and os.path.isfile(name)))
        
# put name in 8x3, all upper-case format the was GW-BASIC does it (differs from Windows short name)         
#    # cryptic errors given by GW-BASIC:    
#    if ext.find('.') > -1:
#        # 53: file not found
#        raise error.RunError(errdots)
def dossify_write(s, defext='BAS', dummy_path='', dummy_err=0, dummy_isdir=False, dummy_findcase=True):
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
def find_name_read(s, defext='BAS', path='', err=53, isdir=False, find_case=True):
    # check if the name exists as-is
    if istype(path, s, isdir):
        return s
    # check if the dossified name exists with no extension if none given   
    full = dossify_write(s, '', path)
    if istype(path, full, isdir):    
        return full
    # for case-sensitive filenames: find other case combinations, if present
    if find_case:
        full = find_name_case(s, path, isdir)
        if full:    
            return full
    # check if the dossified name exists with a default extension
    if defext:
        full = dossify_write(s, defext, path)
        if istype(path, full, isdir):    
            return full
        if find_case:
            full = find_name_case(s + '.' + defext, path, isdir)
            if full:    
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
def dospath(s, defext, err, action, isdir, find_case=True):
    # substitute drives and cwds
    _, path, name = get_drive_path(str(s), err)
    # return absolute path to file        
    if name:
        return os.path.join(path, action(name, defext, path, err, isdir, find_case))
    else:
        # no file name, just dirs
        return path

dospath_read = partial(dospath, action=find_name_read, isdir=False)
dospath_write = partial(dospath, action=dossify_write, isdir=False)
dospath_read_dir = partial(dospath, action=find_name_read, isdir=True)
dospath_write_dir = partial(dospath, action=dossify_write, isdir=True)

    
# for FILES command
# apply filename filter and DOSify names
def pass_dosnames(path, files_list, mask='*.*'):
    mask = str(mask).rsplit('.', 1)
    if len(mask) == 2:
        trunkmask, extmask = mask
    else:
        trunkmask, extmask = mask[0], ''
    dosfiles = []
    for name in files_list:
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

def files(pathmask):
    drive, path, mask = get_drive_path(str(pathmask), 53)
    mask = mask.upper()
    if mask == '':
        mask = '*.*'
    roots, dirs, files_list = [], [], []
    for roots, dirs, files_list in safe(os.walk, path):
        break
    # get working dir in DOS format
    # NOTE: this is always the current dir, not the one being listed
    console.write_line(drive + ':\\' + drive_cwd[drive].replace(os.sep, '\\'))
    if (roots, dirs, files_list) == ([], [], []):
        raise error.RunError(53)
    dosfiles = pass_dosnames(path, files_list, mask)
    dosfiles = [ name+'     ' for name in dosfiles ]
    dirs += ['.', '..']
    dosdirs = pass_dosnames(path, dirs, mask)
    dosdirs = [ name+'<DIR>' for name in dosdirs ]
    dosfiles.sort()
    dosdirs.sort()    
    output = dosdirs + dosfiles
    num = state.console_state.width/20
    if len(output) == 0:
        # file not found
        raise error.RunError(53)
    while len(output) > 0:
        line = ' '.join(output[:num])
        output = output[num:]
        console.write_line(line)       
        # allow to break during dir listing & show names flowing on screen
        backend.check_events()             
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

    def shell(command):
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
                    backend.check_events()
                    console.write_line(line)
                console.write(last)    
            if p.poll() != None:
                # drain output then break
                continue    
            c = console.get_char()
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
    def shell(command):
        cmd = '/bin/sh'
        if command:
            cmd += ' -c "' + command + '"'            
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
                    if state.console_state.col != 1:
                        state.console_state.col -= 1
                else:
                    console.write(c)
            if c == '' and not p.isalive(): 
                return


###################################################
# printing

# these values are not shown as special graphic chars but as their normal effect
control = (
    '\x07', # BEL
    #'\x08',# BACKSPACE
    '\x09', # TAB 
    '\x0a', # LF
    '\x0b', # HOME
    '\x0c', # clear screen
    '\x0d', # CR
    '\x1c', # RIGHT
    '\x1d', # LEFT
    '\x1e', # UP
    '\x1f', # DOWN
    ) 
    
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
            if c in control:
                utf8buf += c
            else:    
                utf8buf += unicodepage.cp_to_utf8[c]
        line_print(utf8buf, self.printer_name)

if plat.system == 'Windows':
    # print to Windows printer
    def line_print(printbuf, printer_name):        
        if printer_name == '' or printer_name=='default':
            printer_name = win32print.GetDefaultPrinter()
        handle = win32ui.CreateDC()
        handle.CreatePrinterDC(printer_name)
        handle.StartDoc("PC-BASIC 3_23 Document")
        handle.StartPage()
        # a4 = 210x297mm = 4950x7001px; Letter = 216x280mm=5091x6600px; 
        # 65 tall, 100 wide with 50x50 margins works for US letter
        # 96 wide works for A4 with 75 x-margin
        y, yinc = 50, 100
        lines = printbuf.split('\r\n')
        slines = []
        for l in lines:
            slines += [l[i:i+96] for i in range(0, len(l), 96)]
        for line in slines:
            handle.TextOut(75, y, line) 
            y += yinc
            if y > 6500:  
                y = 50
                handle.EndPage()
                handle.StartPage()
        handle.EndPage()
        handle.EndDoc()       

elif plat.system == 'Android':
    def line_print(printbuf, printer_name):
        # printing not supported on Android
        pass          

else:
    # print to LPR printer (ok for CUPS)
    def line_print(printbuf, printer_name): 
        options = ''
        if printer_name != '' and printer_name != 'default':
            options += ' -P ' + printer_name
        if printbuf != '':
            pr = os.popen("lpr " + options, "w")
            pr.write(printbuf)
            pr.close()

