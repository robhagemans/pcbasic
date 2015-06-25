"""
PC-BASIC - disk.py
Disk Devices

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

##############################################################################
# Disk devices

import os
import errno
import logging
import string
from fnmatch import fnmatch

import plat
if plat.system == 'Windows':
    import win32api
    import ctypes
    
import config
import error
import state
import backend
import console
# for value_to_uint
import vartypes
import iolayer
import unicodepage


# GW-BASIC FILE CONTROL BLOCK structure:
# source: IBM Basic reference 1982 (for BASIC-C, BASIC-D, BASIC-A) appendix I-5
# byte  length  description
# 0     1       Mode 1-input 2-output 4-random 16-append
# 1     38      MSDOS FCB:
# ------------------------
# 0     1       Drive number (0=Default, 1=A, etc)
# 01h   8       blank-padded file name
# 09h   3       blank-padded file extension
# 0Ch   2       current block number
# 0Eh   2       logical record size
# 10h   4       file size
# 14h   2       date of last write (see #01666 at AX=5700h)
# 16h   2       time of last write (see #01665 at AX=5700h) (DOS 1.1+)
# 18h   8       reserved (see #01347,#01348,#01349,#01350,#01351)
# 20h   1       record within current block
# 21h   4       random access record number (if record size is > 64 bytes, high byte is omitted)
# ------------------------
# 39    2       For seq files, the number of sectors read or written. For random files, 1+the last record read or written
# 41    1       Number of bytes in sector when read or written
# 42    1       Number of bytes left in input buffer
# 43    3       (reserved)
# 46    1       Drive number 0=A, 1=B, 248=LPT3,2 250=COM2,1 252=CAS1 253=LPT1 254=SCRN 255=KYBD
# 47    1       Device width
# 48    1       Position in buffer for PRINT#
# 49    1       internal use during LOAD and SAVE
# 50    1       Output position used during tab expansion
# 51    128     Physical data buffer for transfer between DOS and BASIC. Can examine this data in seq I/O mode.
# 179   2       Variable length record size, default 128
# 181   2       Current physical record number
# 183   2       Current logical record number
# 185   1       (reserved)
# 186   2       Position for PRINT#, INPUT#, WRITE#
# 188   n       FIELD buffer, default length 128 (given by /s:n)


# fields are preserved on file close, so have a separate store
state.io_state.fields = {}

# translate os error codes to BASIC error codes
os_error = {
    # file not found
    errno.ENOENT: 53, errno.EISDIR: 53, errno.ENOTDIR: 53,
    # permission denied
    errno.EAGAIN: 70, errno.EACCES: 70, errno.EBUSY: 70,
    errno.EROFS: 70, errno.EPERM: 70,
    # disk full
    errno.ENOSPC: 61,
    # disk not ready
    errno.ENXIO: 71, errno.ENODEV: 71,
    # disk media error
    errno.EIO: 72,
    # path/file access error
    errno.EEXIST: 75, errno.ENOTEMPTY: 75,
    }

# accept CR, LF and CRLF line endings; interpret as CR only if the next line starts with a number
universal_newline = False
# interpret "ascii" program files as UTF-8
utf8_files = False

#####################

def prepare():
    """ Initialise disk devices. """
    global utf8_files, universal_newline
    utf8_files = config.options['utf8']
    universal_newline = not config.options['strict-newline']
    if config.options['map-drives']:
        drives, current_drive = map_drives()
    else:
        drives = { 'Z': (os.getcwd(), '') }
        current_drive = 'Z'
    for a in config.options['mount']:
        try:
            # the last one that's specified will stick
            letter, path = a.split(':', 1)
            path = os.path.realpath(path)
            if not os.path.isdir(path):
                logging.warning('Could not mount %s', a)
            else:
                drives[letter.upper()] = path, ''
        except (TypeError, ValueError):
            logging.warning('Could not mount %s', a)
    # allowable drive letters in GW-BASIC are letters or @
    for letter in '@' + string.ascii_uppercase:
        try:
            path, cwd = drives[letter]
        except KeyError:
            path, cwd = None, ''
        backend.devices[letter + ':'] = DiskDevice(letter, path, cwd)
    iolayer.current_device = backend.devices[current_drive + ':']
    # initialise field buffers
    reset_fields()

def reset_fields():
    """ Initialise FIELD buffers. """
    state.io_state.fields = {}
    for i in range(iolayer.max_files):
        state.io_state.fields[i] = iolayer.Field(i)


if plat.system == 'Windows':
    def map_drives():
        """ Map Windows drive letters to PC-BASIC disk devices. """
        # get all drives in use by windows
        # if started from CMD.EXE, get the 'current working dir' for each drive
        # if not in CMD.EXE, there's only one cwd
        current_drive = os.path.abspath(os.getcwd()).split(':')[0]
        save_current = os.getcwd()
        drives = {}
        for drive_letter in win32api.GetLogicalDriveStrings().split(':\\\x00')[:-1]:
            try:
                os.chdir(drive_letter + ':')
                cwd = win32api.GetShortPathName(os.getcwd())
                # must not start with \\
                drives[drive_letter] = cwd[:3], cwd[3:]
            except OSError:
                pass
        os.chdir(save_current)
        return drives, current_drive
else:
    def map_drives():
        """ Map useful Unix directories to PC-BASIC disk devices. """
        drives = {}
        # map C to root
        cwd = os.getcwd()
        drives['C'] = '/', cwd[1:]
        # map Z to cwd
        drives['Z'] = cwd, ''
        # map H to home
        home = os.path.expanduser('~')
        # if cwd is in home tree, set it also on H:
        if cwd[:len(home)] == home:
            drives['H'] = home, cwd[len(drives['H'])+1:]
        else:
            drives['H'] = home, ''
        return drives, 'Z'


##############################################################################
# Locks

# dict of native file names by number, for locking
state.io_state.locks = {}

def list_locks(name):
    """ Retrieve a list of files open to the same disk stream. """
    return [ state.io_state.files[fnum]
                   for (fnum, fname) in state.io_state.locks.iteritems()
                   if fname == name ]

def acquire_lock(name, number, lock_type, access):
    """ Try to lock a file. """
    already_open = list_locks(name)
    state.io_state.locks[number] = name
    for f in already_open:
        if (
                # default mode: don't accept if SHARED/LOCK present
                ((not lock_type) and f.lock_type) or
                # LOCK READ WRITE: don't accept if already open
                (lock_type == 'RW') or
                # SHARED: don't accept if open in default mode
                (lock_type == 'S' and not f.lock_type) or
                # LOCK READ or LOCK WRITE: accept base on ACCESS of open file
                (lock_type in f.access) or (f.lock_type in access)):
            # permission denied
            raise error.RunError(70)

def release_lock(number):
    """ Release the lock on a file before closing. """
    del state.io_state.locks[number]

##############################################################################
# Exception handling

def safe(fnname, *fnargs):
    """ Execute OS function and handle errors. """
    try:
        return fnname(*fnargs)
    except EnvironmentError as e:
        handle_oserror(e)

def handle_oserror(e):
    """ Translate OS and I/O exceptions to BASIC errors. """
    try:
        basic_err = os_error[e.errno]
    except KeyError:
        # unknown; internal error
        basic_err = 51
    raise error.RunError(basic_err)

def get_diskdevice_and_path(path):
    """ Return the disk device and remaining path for given BASIC path. """
    splits = str(path).upper().split(':', 1)
    if len(splits) == 0:
        return iolayer.current_device, ''
    elif len(splits) == 1:
        return iolayer.current_device, splits[0]
    else:
        # must be a disk device
        if len(splits[0]) > 1:
            # 68: device unavailable
            raise error.RunError(68)
        try:
            return backend.devices[splits[0] + ':'], splits[1]
        except KeyError:
            raise error.RunError(68)


##############################################################################
# DOS name translation

if plat.system == 'Windows':
    def short_name(path, longname):
        """ Get Windows short name or fake it. """
        path_and_longname = os.path.join(path, longname)
        try:
            # gets the short name if it exists, keeps long name otherwise
            path_and_name = win32api.GetShortPathName(path_and_longname)
        except OSError:
            # something went wrong - keep long name (happens for swap file)
            path_and_name = path_and_longname
        # last element of path is name
        name = path_and_name.split(os.sep)[-1]
        # if we still have a long name, shorten it now
        return split_dosname(name.strip().upper())
else:
    def short_name(dummy_path, longname):
        """ Get Windows short name or fake it. """
        # path is only needed on Windows
        return split_dosname(longname.strip().upper())

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

def join_dosname(trunk, ext):
    """ Join trunk and extension into file name. """
    return trunk + ('.' + ext if ext else '')

def istype(path, native_name, isdir):
    """ Return whether a file exists and is a directory or regular. """
    name = os.path.join(str(path), str(native_name))
    try:
        return os.path.isdir(name) if isdir else os.path.isfile(name)
    except TypeError:
        # happens for name = '\0'
        return False

def dossify(longname, defext=''):
    """ Put name in 8x3, all upper-case format and apply default extension. """
    # convert to all uppercase; one trunk, one extension
    name, ext = split_dosname(longname.strip().upper(), defext)
    # no dot if no ext
    return join_dosname(name, ext)

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

def filter_names(path, files_list, mask='*.*'):
    """ Apply filename filter to short version of names. """
    all_files = [short_name(path, name) for name in files_list]
    # apply mask separately to trunk and extension, dos-style.
    # hide dotfiles
    trunkmask, extmask = split_dosname(mask)
    return sorted([(t, e) for (t, e) in all_files
        if (fnmatch(t, trunkmask.upper()) and fnmatch(e, extmask.upper()) and
            (t or not e or e == '.'))])

################################

class DiskDevice(object):
    """ Disk device (A:, B:, C:, ...) """

    allowed_modes = 'IOR'

    # posix access modes for BASIC modes INPUT, OUTPUT, RANDOM, APPEND
    # and internal LOAD and SAVE modes
    access_modes = { 'I':'rb', 'O':'wb', 'R':'r+b', 'A':'ab' }
    # posix access modes for BASIC ACCESS mode for RANDOM files only
    access_access = { 'R': 'rb', 'W': 'wb', 'RW': 'r+b' }

    def __init__(self, letter, path, cwd=''):
        """ Initialise a disk device. """
        self.letter = letter
        # mount root
        # this is a native path, using os.sep
        self.path = path
        # current working directory on this drive
        # this is a DOS relative path, no drive letter; including leading \\
        # stored with os.sep but given using backslash separators
        self.cwd = os.path.join(*cwd.split('\\'))

    def close(self):
        """ Close disk device. """
        pass

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """ Open a file on a disk drive. """
        if not self.path:
            # undefined disk drive: path not found
            raise error.RunError(76)
        # set default extension for programs
        if set(filetype).intersection(set('PBA')):
            defext = 'BAS'
        else:
            defext = ''
        # translate the file name to something DOS-ish if necessary
        if mode in ('O', 'A'):
            # don't open output or append files more than once
            self.check_file_not_open(param)
        if mode == 'I':
            name = self.native_path(param, defext)
        else:
            # random files: try to open matching file
            # if it doesn't exist, create an all-caps 8.3 file name
            name = self.native_path(param, defext, make_new=True)
        # obtain a lock
        acquire_lock(name, number, lock, access)
        # open the underlying stream
        fhandle = self.open_stream(name, mode, access)
        # apply the BASIC file wrapper
        return open_diskfile(fhandle, filetype, mode, name, number, access, lock, reclen)

    def open_stream(self, native_name, mode, access):
        """ Open a stream on disk by os-native name with BASIC mode and access level. """
        name = str(native_name)
        if (access and mode == 'R'):
            posix_access = self.access_access[access]
        else:
            posix_access = self.access_modes[mode]
        try:
            # create file if in RANDOM or APPEND mode and doesn't exist yet
            # OUTPUT mode files are created anyway since they're opened with wb
            if ((mode == 'A' or (mode == 'R' and access == 'RW')) and
                    not os.path.exists(name)):
                open(name, 'wb').close()
            if mode == 'A':
                # APPEND mode is only valid for text files (which are seekable);
                # first cut off EOF byte, if any.
                f = open(name, 'r+b')
                try:
                    f.seek(-1, 2)
                    if f.read(1) == '\x1a':
                        f.seek(-1, 1)
                        f.truncate()
                except IOError:
                    pass
                f.close()
            return open(name, posix_access)
        except EnvironmentError as e:
            handle_oserror(e)
        except TypeError:
            # bad file number, which is what GW throws for open chr$(0)
            raise error.RunError(52)

    def check_file_not_open(self, path):
        """ Raise an error if the file is open. """
        for f in state.io_state.files:
            if self.native_path(path) == state.io_state.files[f].name:
                raise error.RunError(55)

    def native_path_elements(self, path_without_drive, err, join_name=False):
        """ Return elements of the native path for a given BASIC path. """
        path_without_drive = str(path_without_drive)
        if '/' in path_without_drive:
            # bad file number - this is what GW produces here
            raise error.RunError(52)
        if not self.path:
            # this drive letter is not available (not mounted)
            # path not found
            raise error.RunError(76)
        # get path below drive letter
        if path_without_drive and path_without_drive[0] == '\\':
            # absolute path specified
            elements = path_without_drive.split('\\')
        else:
            elements = self.cwd.split(os.sep) + path_without_drive.split('\\')
        # strip whitespace
        elements = map(str.strip, elements)
        # whatever's after the last \\ is the name of the subject file or dir
        # if the path ends in \\, there's no name
        name = '' if (join_name or not elements) else elements.pop()
        # parse internal .. and . (like normpath but with \\)
        # drop leading . and .. (this is what GW-BASIC does at drive root)
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
        # prepend drive root path to allow filename matching
        path = self.path
        baselen = len(path) + (path[-1] != os.sep)
        # find the native matches for each step in the path
        for e in elements:
            # skip double slashes
            if e:
                # find a matching directory for every step in the path;
                # append found name to path
                path = os.path.join(path, match_filename(e, '', path, err, isdir=True))
        # return drive root path, relative path, file name
        return path[:baselen], path[baselen:], name

    def native_path(self, path_and_name, defext='', err=53,
                    isdir=False, find_case=True, make_new=False):
        """ Find os-native path to match the given BASIC path. """
        # substitute drives and cwds
        drivepath, relpath, name = self.native_path_elements(path_and_name, err)
        # return absolute path to file
        path = os.path.join(drivepath, relpath)
        if name:
            path = os.path.join(path,
                match_filename(name, defext, path, err, isdir, find_case, make_new))
        # get full normalised path
        return os.path.abspath(path)

    def chdir(self, name):
        """ Change working directory to given BASIC path. """
        # get drive path and relative path
        dpath, rpath, _ = self.native_path_elements(name, err=76, join_name=True)
        # set cwd for the specified drive
        self.cwd = rpath
        # set the cwd in the underlying os (really only useful for SHELL)
        if self == iolayer.current_device:
            safe(os.chdir, os.path.join(dpath, rpath))

    def mkdir(self, name):
        """ Create directory at given BASIC path. """
        safe(os.mkdir, self.native_path(name, err=76, isdir=True, make_new=True))

    def rmdir(self, name):
        """ Remove directory at given BASIC path. """
        safe(os.rmdir, self.native_path(name, err=76, isdir=True))

    def kill(self, name):
        """ Remove regular file at given BASIC path. """
        safe(os.remove, self.native_path(name))

    def rename(self, oldname, newname):
        """ Rename a file or directory. """
        # note that we can't rename to another drive: "Rename across disks"
        oldname = self.native_path(str(oldname), err=53, isdir=False)
        newname = self.native_path(str(newname), err=76, isdir=False, make_new=True)
        if os.path.exists(newname):
            # file already exists
            raise error.RunError(58)
        safe(os.rename, oldname, newname)

    def files(self, pathmask):
        """ Write directory listing to console. """
        # forward slashes - file not found
        # GW-BASIC sometimes allows leading or trailing slashes
        # and then does weird things I don't understand.
        if '/' in str(pathmask):
            # file not found
            raise error.RunError(53)
        if not self.path:
            # undefined disk drive: file not found
            raise error.RunError(53)
        drivepath, relpath, mask = self.native_path_elements(pathmask, err=53)
        path = os.path.join(drivepath, relpath)
        mask = mask.upper() or '*.*'
        # output working dir in DOS format
        # NOTE: this is always the current dir, not the one being listed
        dir_elems = [join_dosname(*short_name(path, e)) for e in self.cwd.split(os.sep)]
        console.write_line(self.letter + ':\\' + '\\'.join(dir_elems))
        fils = ''
        if mask == '.':
            dirs = [split_dosname(dossify((os.sep+relpath).split(os.sep)[-1:][0]))]
        elif mask == '..':
            dirs = [split_dosname(dossify((os.sep+relpath).split(os.sep)[-2:][0]))]
        else:
            all_names = safe(os.listdir, path)
            dirs = [n for n in all_names if os.path.isdir(os.path.join(path, n))]
            fils = [n for n in all_names if not os.path.isdir(os.path.join(path, n))]
            # filter according to mask
            dirs = filter_names(path, dirs + ['.', '..'], mask)
            fils = filter_names(path, fils, mask)
        if not dirs and not fils:
            raise error.RunError(53)
        # format and print contents
        output = (
              [('%-8s.%-3s' % (t, e) if (e or not t) else '%-8s    ' % t) + '<DIR>' for t, e in dirs]
            + [('%-8s.%-3s' % (t, e) if e else '%-8s    ' % t) + '     ' for t, e in fils])
        num = state.console_state.screen.mode.width // 20
        while len(output) > 0:
            line = ' '.join(output[:num])
            output = output[num:]
            console.write_line(line)
            # allow to break during dir listing & show names flowing on screen
            backend.check_events()
        console.write_line(' %d Bytes free' % self.get_free())

    def get_free(self):
        """ Return the number of free bytes on the drive. """
        if plat.system == 'Windows':
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(self.path),
                                            None, None, ctypes.pointer(free_bytes))
            return free_bytes.value
        elif plat.system == 'Android':
            return 0
        else:
            st = os.statvfs(self.path)
            return st.f_bavail * st.f_frsize



#################################################################################
# Disk files

def open_diskfile(fhandle, filetype, mode, name='', number=0, access='RW', lock='',
                  reclen=128, seg=0, offset=0, length=0):
    """ Create disk file object of requested type. """
    first = ''
    # determine file type if needed
    if len(filetype) > 1 and mode == 'I':
        # read magic
        first = fhandle.read(1)
        try:
            filetype_found = iolayer.magic_to_type[first]
            if filetype_found not in filetype:
                # bad file mode
                raise error.RunError(54)
            filetype = filetype_found
        except KeyError:
            filetype = 'A'
    if filetype in 'BPM':
        # binary [B]LOAD, [B]SAVE
        return BinaryFile(fhandle, filetype, number, name, mode,
                           seg, offset, length)
    elif filetype == 'A':
        # ascii program file (UTF8 or universal newline if option given)
        return TextFile(fhandle, filetype, number, name,
                         mode, access, lock, first,
                         utf8_files, universal_newline)
    elif filetype == 'D':
        if mode in 'IAO':
            # text data
            return TextFile(fhandle, filetype, number, name,
                             mode, access, lock, first)
        else:
            return RandomFile(fhandle, number, name, mode, access, lock, reclen)
    else:
        # internal error - incorrect file type requested
        logging.debug('Incorrect file type %s requested for mode %s',
                      filetype, mode)
        raise error.RunError(51)


class BinaryFile(iolayer.RawFile):
    """ File class for binary (B, P, M) files on disk device. """

    def __init__(self, fhandle, filetype, number, name, mode,
                       seg, offset, length):
        """ Initialise program file object and write header. """
        iolayer.RawFile.__init__(self, fhandle, filetype, mode)
        self.number = number
        # don't lock binary files
        self.lock = ''
        self.access = 'RW'
        self.seg, self.offset, self.length = 0, 0, 0
        if self.mode == 'O':
            self.write(iolayer.type_to_magic[filetype])
            if self.filetype == 'M':
                self.write(vartypes.value_to_uint(seg) +
                           vartypes.value_to_uint(offset) +
                           vartypes.value_to_uint(length))
                self.seg, self.offset, self.length = seg, offset, length
        else:
            if self.filetype == 'M':
                self.seg = vartypes.uint_to_value(bytearray(self.read(2)))
                self.offset = vartypes.uint_to_value(bytearray(self.read(2)))
                # size gets ignored: even the \x1a at the end is read
                self.length = vartypes.uint_to_value(bytearray(self.read(2)))

    def close(self):
        """ Write EOF and close program file. """
        if self.mode == 'O':
            self.write('\x1a')
        iolayer.RawFile.close(self)
        release_lock(self.number)


class RandomFile(iolayer.RandomBase):
    """ Random-access file on disk device. """

    def __init__(self, fhandle, number, name,
                        mode, access, lock, reclen=128):
        """ Initialise random-access file. """
        iolayer.RandomBase.__init__(self, fhandle, 'D',
                                          state.io_state.fields[number],
                                          mode, reclen)
        self.lock_type = lock
        self.access = access
        self.lock_list = set()
        self.number = number
        self.name = name
        # position at start of file
        self.recpos = 0
        self.fhandle.seek(0)

    def close(self):
        """ Close random-access file. """
        iolayer.RandomBase.close(self)
        release_lock(self.number)

    def get(self, dummy=None):
        """ Read a record. """
        if self.eof():
            self.field.buffer[:] = '\0' * self.reclen
        else:
            self.field.buffer[:] = self.fhandle.read(self.reclen)
        self.field_text_file.fhandle.seek(0)
        self.recpos += 1

    def put(self, dummy=None):
        """ Write a record. """
        current_length = self.lof()
        if self.recpos > current_length:
            self.fhandle.seek(0, 2)
            numrecs = self.recpos-current_length
            self.fhandle.write('\0' * numrecs * self.reclen)
        self.fhandle.write(self.field.buffer)
        self.recpos += 1

    def set_pos(self, newpos):
        """ Set current record number. """
        # first record is newpos number 1
        self.fhandle.seek((newpos-1)*self.reclen)
        self.recpos = newpos - 1

    def loc(self):
        """ Get number of record just past, for LOC. """
        return self.recpos

    def eof(self):
        """ Return whether we're past currentg end-of-file, for EOF. """
        return self.recpos*self.reclen > self.lof()

    def lof(self):
        """ Get length of file, in bytes, for LOF. """
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof

    def lock(self, start, stop, lock_list):
        """ Lock range of records. """
        bstart, bstop = (start-1) * self.reclen, stop*self.reclen - 1
        other_lock_list = set.union(f.lock_list for f in list_locks(self.name))
        for start_1, stop_1 in other_lock_list:
            if (stop_1 == -1 or (bstart >= start_1 and bstart <= stop_1)
                             or (bstop >= start_1 and bstop <= stop_1)):
                raise error.RunError(70)
        self.lock_list.add((bstart, bstop))

    def unlock(self, start, stop, lock_list):
        """ Unlock range of records. """
        bstart, bstop = (start-1) * self.reclen, stop*self.reclen - 1
        # permission denied if the exact record range wasn't given before
        try:
            self.lock_list.remove((bstart, bstop))
        except KeyError:
            raise error.RunError(70)


class TextFile(iolayer.CRLFTextFileBase):
    """ Text file on disk device. """

    def __init__(self, fhandle, filetype, number, name,
                 mode='A', access='RW', lock='', first_char='',
                 utf8=False, universal=False):
        """ Initialise text file object. """
        iolayer.CRLFTextFileBase.__init__(self, fhandle, filetype,
                                          mode, first_char)
        self.lock_list = set()
        self.lock_type = lock
        self.access = access
        self.number = number
        self.name = name
        self.utf8 = utf8
        self.universal = universal
        self.spaces = ''
        if self.mode == 'A':
            self.fhandle.seek(0, 2)
        elif self.mode == 'O' and self.utf8:
            # start UTF-8 files with BOM as many Windows readers expect this
            self.fhandle.write('\xef\xbb\xbf')

    def close(self):
        """ Close text file. """
        if self.mode in ('O', 'A') and not self.utf8:
            # write EOF char
            self.fhandle.write('\x1a')
        iolayer.CRLFTextFileBase.close(self)
        release_lock(self.number)

    def loc(self):
        """ Get file pointer LOC """
        # for LOC(i)
        if self.mode == 'I':
            return max(1, (127+self.fhandle.tell())/128)
        return self.fhandle.tell()/128

    def lof(self):
        """ Get length of file LOF. """
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof

    def write_line(self, s=''):
        """ Write to file in normal or UTF-8 mode. """
        if self.utf8:
            s = unicodepage.UTF8Converter().to_utf8(s)
        iolayer.CRLFTextFileBase.write(self, s + '\r\n')

    def write(self, s):
        """ Write to file in normal or UTF-8 mode. """
        if self.utf8:
            s = unicodepage.UTF8Converter().to_utf8(s)
        iolayer.CRLFTextFileBase.write(self, s)

    def _read_line_universal(self):
        """ Read line from ascii program file with universal newlines. """
        # keep reading until any kind of line break
        # is followed by a line starting with a number
        s, c = self.spaces, ''
        self.spaces = ''
        while len(s) < 255:
            # read converts CRLF to CR
            c = self.read(1)
            if not c or c in ('\r', '\n'):
                # break on CR, CRLF, LF if next line starts with number
                while self.next_char in (' ', '\0'):
                    c = self.read(1)
                    self.spaces += c
                if self.next_char in string.digits:
                    break
                else:
                    s += '\n' + self.spaces
                    self.spaces = ''
            else:
                s += c
        if not c and not s:
            return None
        return s

    def read_line(self):
        """ Read line from text file. """
        if not self.universal:
            s = iolayer.CRLFTextFileBase.read_line(self)
        else:
            s = self._read_line_universal()
        if self.utf8 and s is not None:
            s = unicodepage.str_from_utf8(s)
        return s

    def lock(self, start, stop, lock_list):
        """ Lock the file. """
        if set.union(f.lock_list for f in list_locks(self.name)):
            raise error.RunError(70)
        self.lock_list.add((0, -1))

    def unlock(self, start, stop):
        """ Unlock the file. """
        try:
            self.lock_list.remove((0, -1))
        except KeyError:
            raise error.RunError(70)

prepare()

