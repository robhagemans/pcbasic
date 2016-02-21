"""
PC-BASIC - disk.py
Disk Devices

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

##############################################################################
# Disk devices

import os
import errno
import logging
import string
import re

import plat
if plat.system == 'Windows':
    import win32api
    import ctypes

from bytestream import ByteStream

import config
import error
import state
# for check_events during FILES
import backend
import console
import vartypes
import devices
# to initialise state.console_state.codepage
import unicodepage
# to be abled to set current-device to CAS1
import cassette


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
    errno.ENOENT: error.FILE_NOT_FOUND,
    errno.EISDIR: error.FILE_NOT_FOUND,
    errno.ENOTDIR: error.FILE_NOT_FOUND,
    # permission denied
    errno.EAGAIN: error.PERMISSION_DENIED,
    errno.EACCES: error.PERMISSION_DENIED,
    errno.EBUSY: error.PERMISSION_DENIED,
    errno.EROFS: error.PERMISSION_DENIED,
    errno.EPERM: error.PERMISSION_DENIED,
    # disk full
    errno.ENOSPC: error.DISK_FULL,
    # disk not ready
    errno.ENXIO: error.DISK_NOT_READY,
    errno.ENODEV: error.DISK_NOT_READY,
    # disk media error
    errno.EIO: error.DISK_MEDIA_ERROR,
    # path/file access error
    errno.EEXIST: error.PATH_FILE_ACCESS_ERROR,
    errno.ENOTEMPTY: error.PATH_FILE_ACCESS_ERROR,
}

# accept CR, LF and CRLF line endings; interpret as CR only if the next line starts with a number
universal_newline = False
# interpret "ascii" program files as UTF-8
utf8_files = False

# allowable drive letters in GW-BASIC are letters or @
drive_letters = '@' + string.ascii_uppercase

# allowable characters in DOS file name
# GW-BASIC also allows 0x7F and up, but replaces accented chars with unaccented
# based on CHCP code page, which may differ from display codepage in COUNTRY.SYS
# this is complex and leads to unpredictable results depending on host platform.
allowable_chars = set(string.ascii_letters + string.digits + " !#$%&'()-@^_`{}~")

#####################

def prepare():
    """ Initialise disk devices. """
    global utf8_files, universal_newline
    utf8_files = config.get('utf8')
    universal_newline = not config.get('strict-newline')
    for letter in drive_letters:
        state.io_state.devices[letter + ':'] = DiskDevice(letter, None, u'')
    current_drive = config.get('current-device').upper()
    if config.get('map-drives'):
        current_drive = _map_drives()
    else:
        state.io_state.devices['Z:'] = DiskDevice('Z', os.getcwdu(), u'')
    _mount_drives(config.get('mount'))
    _set_current_device(current_drive + ':')
    reset_fields()

def override():
    """ Initialise module settings that override --resume. """
    _mount_drives(config.get('mount', False))
    # we always need to reset this or it may be a reference to an old device
    _set_current_device(config.get('current-device', True).upper() + ':')

def _mount_drives(mount_list):
    """ Mount disk drives """
    if not mount_list:
        return
    for a in mount_list:
        try:
            # the last one that's specified will stick
            letter, path = a.decode('utf-8').split(u':', 1)
            letter = letter.encode('ascii', errors='replace').upper()
            path = os.path.realpath(path)
            if not os.path.isdir(path):
                logging.warning(u'Could not mount %s', a)
            else:
                state.io_state.devices[letter + ':'] = DiskDevice(letter, path, u'')
        except (TypeError, ValueError):
            logging.warning('Could not mount %s', a)

def _set_current_device(current_drive, default='Z:'):
    """ Set the current device. """
    try:
        state.io_state.current_device = state.io_state.devices[current_drive]
    except KeyError:
        logging.warning('Could not set current device to %s', current_drive)
        state.io_state.current_device = state.io_state.devices[default]

def reset_fields():
    """ Initialise FIELD buffers. """
    state.io_state.fields = {}
    # fields are indexed by BASIC file number, hence max_files+1
    # file 0 (program/system file) probably doesn't need a field
    for i in range(devices.max_files+1):
        state.io_state.fields[i+1] = devices.Field(i+1)


if plat.system == 'Windows':
    def _map_drives():
        """ Map Windows drive letters to PC-BASIC disk devices. """
        # get all drives in use by windows
        # if started from CMD.EXE, get the 'current working dir' for each drive
        # if not in CMD.EXE, there's only one cwd
        current_drive = os.path.abspath(os.getcwd()).split(':')[0]
        save_current = os.getcwd()
        drives = {}
        for letter in win32api.GetLogicalDriveStrings().split(':\\\0')[:-1]:
            try:
                os.chdir(letter + ':')
                cwd = win32api.GetShortPathName(os.getcwdu())
            except Exception:
                # something went wrong, do not mount this drive
                # this is often a pywintypes.error rather than a WindowsError
                pass
            else:
                # must not start with \\
                path, cwd = cwd[:3], cwd[3:]
                state.io_state.devices[letter + ':'] = DiskDevice(letter, path, cwd)
        os.chdir(save_current)
        return current_drive
else:
    def _map_drives():
        """ Map useful Unix directories to PC-BASIC disk devices. """
        cwd = os.getcwdu()
        # map C to root
        state.io_state.devices['C:'] = DiskDevice('C', u'/', cwd[1:])
        # map Z to cwd
        state.io_state.devices['Z:'] = DiskDevice('Z', cwd, u'')
        # map H to home
        home = os.path.expanduser(u'~')
        # if cwd is in home tree, set it also on H:
        if cwd[:len(home)] == home:
            state.io_state.devices['H:'] = DiskDevice('H', home, cwd[len(home)+1:])
        else:
            state.io_state.devices['H:'] = DiskDevice('H', home, u'')
        # default durrent drive
        return 'Z'


##############################################################################
# Disk file object wrapper

def create_file_object(fhandle, filetype, mode, name='', number=0,
                       access='RW', lock='', reclen=128,
                       seg=0, offset=0, length=0):
    """ Create disk file object of requested type. """
    # determine file type if needed
    if len(filetype) > 1 and mode == 'I':
        # read magic
        first = fhandle.read(1)
        fhandle.seek(-1, 1)
        try:
            filetype_found = devices.magic_to_type[first]
            if filetype_found not in filetype:
                raise error.RunError(error.BAD_FILE_MODE)
            filetype = filetype_found
        except KeyError:
            filetype = 'A'
    if filetype in 'BPM':
        # binary [B]LOAD, [B]SAVE
        return BinaryFile(fhandle, filetype, number, name, mode,
                           seg, offset, length)
    elif filetype == 'A':
        # ascii program file (UTF8 or universal newline if option given)
        return TextFile(fhandle, filetype, number, name, mode, access, lock,
                         utf8_files, universal_newline, split_long_lines=False)
    elif filetype == 'D':
        if mode in 'IAO':
            # text data
            return TextFile(fhandle, filetype, number, name, mode, access, lock)
        else:
            return RandomFile(fhandle, number, name, access, lock, reclen)
    else:
        # internal error - incorrect file type requested
        logging.debug('Incorrect file type %s requested for mode %s',
                      filetype, mode)
        raise error.RunError(error.INTERNAL_ERROR)


##############################################################################
# Locks

# dict of native file names by number, for locking
state.io_state.locks = {}

def _list_locks(name):
    """ Retrieve a list of files open to the same disk stream. """
    return [ state.io_state.files[fnum]
                   for (fnum, fname) in state.io_state.locks.iteritems()
                   if fname == name ]

def _acquire_lock(name, number, lock_type, access):
    """ Try to lock a file. """
    if not number:
        return
    already_open = _list_locks(name)
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
            raise error.RunError(error.PERMISSION_DENIED)
    state.io_state.locks[number] = name


def _release_lock(number):
    """ Release the lock on a file before closing. """
    try:
        del state.io_state.locks[number]
    except KeyError:
        pass

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
        basic_err = error.INTERNAL_ERROR
    raise error.RunError(basic_err)

def get_diskdevice_and_path(path):
    """ Return the disk device and remaining path for given BASIC path. """
    # careful - do not convert path to uppercase, we still need to match
    splits = str(path).split(':', 1)
    if len(splits) == 0:
        return state.io_state.current_device, ''
    elif len(splits) == 1:
        return state.io_state.current_device, splits[0]
    else:
        # must be a disk device
        if len(splits[0]) > 1:
            raise error.RunError(error.DEVICE_UNAVAILABLE)
        try:
            return state.io_state.devices[splits[0].upper() + ':'], splits[1]
        except KeyError:
            raise error.RunError(error.DEVICE_UNAVAILABLE)


##############################################################################
# DOS name translation

if plat.system == 'Windows':
    def short_name(path, longname):
        """ Get Windows short name or fake it. """
        path_and_longname = os.path.join(path, longname)
        try:
            # gets the short name if it exists, keeps long name otherwise
            path_and_name = win32api.GetShortPathName(path_and_longname)
        except Exception:
            # something went wrong - keep long name (happens for swap file)
            # this should be a WindowsError which is an OSError
            # but it often is a pywintypes.error
            path_and_name = path_and_longname
        # last element of path is name
        name = path_and_name.split(os.sep)[-1]
        # if we still have a long name, shorten it now
        return split_dosname(name, mark_shortened=True)
else:
    def short_name(dummy_path, longname):
        """ Get Windows short name or fake it. """
        # path is only needed on Windows
        return split_dosname(longname, mark_shortened=True)

def split_dosname(name, defext='', mark_shortened=False):
    """ Convert unicode name into uppercase 8.3 tuple; apply default extension """
    # convert to all uppercase, no leading or trailing spaces
    name = str(name.encode('ascii', errors='replace')).strip().upper()
    # don't try to split special directory names
    if name == '.':
        return '', ''
    elif name == '..':
        return '', '.'
    # take whatever comes after last dot as extension
    # and whatever comes before first dot as trunk
    elements = name.split('.')
    if len(elements) == 1:
        trunk, ext = elements[0], defext
    else:
        trunk, ext = elements[0], elements[-1]
    strunk, sext = trunk[:8], ext[:3]
    if mark_shortened:
        if strunk != trunk:
            strunk = strunk[:7] + '+'
        if sext != ext:
            sext = sext[:2] + '+'
    return strunk, sext

def join_dosname(trunk, ext):
    """ Join trunk and extension into file name. """
    return trunk + ('.' + ext if ext else '')

def istype(path, native_name, isdir):
    """ Return whether a file exists and is a directory or regular. """
    name = os.path.join(path, native_name)
    try:
        return os.path.isdir(name) if isdir else os.path.isfile(name)
    except TypeError:
        # happens for name = '\0'
        return False

def match_dosname(dosname, path, isdir):
    """ Find a matching native file name for a given 8.3 unicode DOS name. """
    try:
        dosname = dosname.decode('ascii')
    except UnicodeDecodeError:
        # non-ascii characters are not allowable for DOS filenames
        return None
    # check if the dossified name exists as-is
    if istype(path, dosname, isdir):
        return dosname
    # for case-sensitive filenames: find other case combinations, if present
    for f in sorted(os.listdir(path)):
        if f.upper() == dosname and istype(path, f, isdir):
            return f
    return None

def match_filename(name, defext, path, name_err, isdir):
    """ Find or create a matching native file name for a given BASIC name. """
    # check if the name exists as-is; should also match Windows short names.
    # EXCEPT if default extension is not empty, in which case
    # default extension must be found first. Necessary for GW compatibility.
    if not defext and istype(path, name, isdir):
        return name
    # try to match dossified names with default extension
    trunk, ext = split_dosname(name, defext)
    # enforce allowable characters
    if (set(trunk) | set(ext)) - allowable_chars:
        raise error.RunError(error.BAD_FILE_NAME)
    dosname = join_dosname(trunk, ext)
    fullname = match_dosname(dosname, path, isdir)
    if fullname:
        return fullname
    # not found
    if not name_err:
        # create a new filename
        return dosname
    else:
        raise error.RunError(name_err)

def match_wildcard(name, mask):
    """ Whether filename name matches DOS wildcard mask. """
    # convert wildcard mask to regexp
    regexp = '\A'
    for c in mask:
        if c == '?':
            regexp += '.'
        elif c == '*':
            # we won't need to match newlines, so dot is fine
            regexp += '.*'
        else:
            regexp += re.escape(c)
    regexp += '\Z'
    cregexp = re.compile(regexp)
    return cregexp.match(name) is not None

def filename_from_unicode(name):
    """ Replace disallowed characters in filename with ?. """
    name_str = name.encode('ascii', 'replace')
    return ''.join(c if c in allowable_chars | set('.') else '?' for c in name_str)

def filter_names(path, files_list, mask=u'*.*'):
    """ Apply filename filter to short version of names. """
    all_files = [short_name(path, name) for name in files_list]
    # apply mask separately to trunk and extension, dos-style.
    # hide dotfiles
    trunkmask, extmask = split_dosname(mask)
    return sorted([(t, e) for (t, e) in all_files
        if (match_wildcard(t, trunkmask) and match_wildcard(e, extmask) and
            (t or not e or e == '.'))])

################################

class DiskDevice(object):
    """ Disk device (A:, B:, C:, ...) """

    allowed_modes = 'IOR'

    # posix access modes for BASIC modes INPUT, OUTPUT, RANDOM, APPEND
    # and internal LOAD and SAVE modes
    _access_modes = { 'I':'rb', 'O':'wb', 'R':'r+b', 'A':'ab' }
    # posix access modes for BASIC ACCESS mode for RANDOM files only
    _access_access = { 'R': 'rb', 'W': 'wb', 'RW': 'r+b' }

    def __init__(self, letter, path, cwd=u''):
        """ Initialise a disk device. """
        self.letter = letter
        # mount root
        # this is a native path, using os.sep
        self.path = path
        # current working directory on this drive
        # this is a DOS relative path, no drive letter; including leading \\
        # stored with os.sep but given using backslash separators
        self.cwd = os.path.join(*cwd.split(u'\\'))

    def close(self):
        """ Close disk device. """
        pass

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """ Open a file on a disk drive. """
        if not self.path:
            # undefined disk drive: path not found
            raise error.RunError(error.PATH_NOT_FOUND)
        # set default extension for programs
        if set(filetype).intersection(set('MPBA')):
            defext = 'BAS'
        else:
            defext = ''
        # translate the file name to something DOS-ish if necessary
        if mode == 'I':
            name = self._native_path(param, defext)
        else:
            # random files: try to open matching file
            # if it doesn't exist, use an all-caps 8.3 file name
            name = self._native_path(param, defext, name_err=None)
        # don't open output or append files more than once
        if mode in ('O', 'A'):
            self.check_file_not_open(param)
        # obtain a lock
        _acquire_lock(name, number, lock, access)
        try:
            # open the underlying stream
            fhandle = self._open_stream(name, mode, access)
            # apply the BASIC file wrapper
            return create_file_object(fhandle, filetype, mode, name, number,
                                      access, lock, reclen, seg, offset, length)
        except Exception:
            _release_lock(number)
            raise

    def _open_stream(self, native_name, mode, access):
        """ Open a stream on disk by os-native name with BASIC mode and access level. """
        name = native_name
        if (access and mode == 'R'):
            posix_access = self._access_access[access]
        else:
            posix_access = self._access_modes[mode]
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
            raise error.RunError(error.BAD_FILE_NUMBER)

    def check_file_not_open(self, path):
        """ Raise an error if the file is open. """
        for f in state.io_state.files:
            try:
                if self._native_path(path, name_err=None) == state.io_state.files[f].name:
                    raise error.RunError(error.FILE_ALREADY_OPEN)
            except AttributeError:
                # only disk files have a name, so ignore
                pass

    def _native_path_elements(self, path_without_drive, path_err, join_name=False):
        """ Return elements of the native path for a given BASIC path. """
        path_without_drive = state.console_state.codepage.str_to_unicode(
                str(path_without_drive), box_protect=False)
        if u'/' in path_without_drive:
            # bad file number - this is what GW produces here
            raise error.RunError(error.BAD_FILE_NUMBER)
        if not self.path:
            # this drive letter is not available (not mounted)
            raise error.RunError(error.PATH_NOT_FOUND)
        # get path below drive letter
        if path_without_drive and path_without_drive[0] == u'\\':
            # absolute path specified
            elements = path_without_drive.split(u'\\')
        else:
            elements = self.cwd.split(os.sep) + path_without_drive.split(u'\\')
        # strip whitespace
        elements = map(unicode.strip, elements)
        # whatever's after the last \\ is the name of the subject file or dir
        # if the path ends in \\, there's no name
        name = u'' if (join_name or not elements) else elements.pop()
        # parse internal .. and . (like normpath but with \\)
        # drop leading . and .. (this is what GW-BASIC does at drive root)
        i = 0
        while i < len(elements):
            if elements[i] == u'.':
                del elements[i]
            elif elements[i] == u'..':
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
                path = os.path.join(path, match_filename(e, '', path, name_err=path_err, isdir=True))
        # return drive root path, relative path, file name
        return path[:baselen], path[baselen:], name

    def _native_path(self, path_and_name, defext='', name_err=error.FILE_NOT_FOUND,
                    isdir=False):
        """ Find os-native path to match the given BASIC path. """
        # substitute drives and cwds
        # always use Path Not Found error if not found at this stage
        drivepath, relpath, name = self._native_path_elements(path_and_name, path_err=error.PATH_NOT_FOUND)
        # return absolute path to file
        path = os.path.join(drivepath, relpath)
        if name:
            path = os.path.join(path,
                match_filename(name, defext, path, name_err, isdir))
        # get full normalised path
        return os.path.abspath(path)

    def chdir(self, name):
        """ Change working directory to given BASIC path. """
        # get drive path and relative path
        dpath, rpath, _ = self._native_path_elements(name, path_err=error.PATH_NOT_FOUND, join_name=True)
        # set cwd for the specified drive
        self.cwd = rpath
        # set the cwd in the underlying os (really only useful for SHELL)
        if self == state.io_state.current_device:
            safe(os.chdir, os.path.join(dpath, rpath))

    def mkdir(self, name):
        """ Create directory at given BASIC path. """
        safe(os.mkdir, self._native_path(name, name_err=None, isdir=True))

    def rmdir(self, name):
        """ Remove directory at given BASIC path. """
        safe(os.rmdir, self._native_path(name, name_err=error.PATH_NOT_FOUND, isdir=True))

    def kill(self, name):
        """ Remove regular file at given BASIC path. """
        safe(os.remove, self._native_path(name))

    def rename(self, oldname, newname):
        """ Rename a file or directory. """
        # note that we can't rename to another drive: "Rename across disks"
        oldname = self._native_path(str(oldname), name_err=error.FILE_NOT_FOUND, isdir=False)
        newname = self._native_path(str(newname), name_err=None, isdir=False)
        if os.path.exists(newname):
            raise error.RunError(error.FILE_ALREADY_EXISTS)
        safe(os.rename, oldname, newname)

    def files(self, pathmask):
        """ Write directory listing to console. """
        # forward slashes - file not found
        # GW-BASIC sometimes allows leading or trailing slashes
        # and then does weird things I don't understand.
        if '/' in str(pathmask):
            raise error.RunError(error.FILE_NOT_FOUND)
        if not self.path:
            # undefined disk drive: file not found
            raise error.RunError(error.FILE_NOT_FOUND)
        drivepath, relpath, mask = self._native_path_elements(pathmask, path_err=error.FILE_NOT_FOUND)
        path = os.path.join(drivepath, relpath)

        mask = mask.upper() or '*.*'
        # output working dir in DOS format
        # NOTE: this is always the current dir, not the one being listed
        dir_elems = [join_dosname(*short_name(path, e)) for e in self.cwd.split(os.sep)]
        console.write_line(self.letter + ':\\' + '\\'.join(dir_elems))
        fils = ''
        if mask == '.':
            dirs = [split_dosname((os.sep+relpath).split(os.sep)[-1:][0])]
        elif mask == '..':
            dirs = [split_dosname((os.sep+relpath).split(os.sep)[-2:][0])]
        else:
            all_names = safe(os.listdir, path)
            dirs = [filename_from_unicode(n) for n in all_names if os.path.isdir(os.path.join(path, n))]
            fils = [filename_from_unicode(n) for n in all_names if not os.path.isdir(os.path.join(path, n))]
            # filter according to mask
            dirs = filter_names(path, dirs + ['.', '..'], mask)
            fils = filter_names(path, fils, mask)
        if not dirs and not fils:
            raise error.RunError(error.FILE_NOT_FOUND)
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

class BinaryFile(devices.RawFile):
    """ File class for binary (B, P, M) files on disk device. """

    def __init__(self, fhandle, filetype, number, name, mode,
                       seg, offset, length):
        """ Initialise program file object and write header. """
        devices.RawFile.__init__(self, fhandle, filetype, mode)
        self.number = number
        # don't lock binary files
        self.lock = ''
        self.access = 'RW'
        self.seg, self.offset, self.length = 0, 0, 0
        if self.mode == 'O':
            self.write(devices.type_to_magic[filetype])
            if self.filetype == 'M':
                self.write(vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(seg)) +
                           vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(offset)) +
                           vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(length)))
                self.seg, self.offset, self.length = seg, offset, length
        else:
            # drop magic byte
            self.read_raw(1)
            if self.filetype == 'M':
                self.seg = vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(self.read(2)))
                self.offset = vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(self.read(2)))
                # size gets ignored: even the \x1a at the end is read
                self.length = vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(self.read(2)))

    def close(self):
        """ Write EOF and close program file. """
        if self.mode == 'O':
            self.write('\x1a')
        devices.RawFile.close(self)
        _release_lock(self.number)


class RandomFile(devices.CRLFTextFileBase):
    """ Random-access file on disk device. """

    def __init__(self, output_stream, number, name,
                        access, lock, reclen=128):
        """ Initialise random-access file. """
        # all text-file operations on a RANDOM file (PRINT, WRITE, INPUT, ...)
        # actually work on the FIELD buffer; the file stream itself is not
        # touched until PUT or GET.
        self.reclen = reclen
        # replace with empty field if already exists
        self.field = state.io_state.fields[number]
        self.field.reset(self.reclen)
        devices.CRLFTextFileBase.__init__(self, ByteStream(self.field.buffer), 'D', 'R')
        self.operating_mode = 'I'
        # note that for random files, output_stream must be a seekable stream.
        self.output_stream = output_stream
        self.lock_type = lock
        self.access = access
        self.lock_list = set()
        self.number = number
        self.name = name
        # position at start of file
        self.recpos = 0
        self.output_stream.seek(0)

    def _check_overflow(self):
        """ Check for FIELD OVERFLOW. """
        write = self.operating_mode == 'O'
        # FIELD overflow happens if last byte in record has been read or written
        if self.fhandle.tell() > self.reclen + write - 1:
            raise error.RunError(error.FIELD_OVERFLOW)

    def read_raw(self, num=-1):
        """ Read num characters from the field. """
        # switch to reading mode and fix readahead buffer
        if self.operating_mode == 'O':
            self.flush()
            self.next_char = self.fhandle.read(1)
            self.operating_mode = 'I'
        s = devices.CRLFTextFileBase.read_raw(self, num)
        self._check_overflow()
        return s

    def write(self, s):
        """ Write the string s to the field, taking care of width settings. """
        # switch to writing mode and fix readahead buffer
        if self.operating_mode == 'I':
            self.fhandle.seek(-1, 1)
            self.operating_mode = 'O'
        devices.CRLFTextFileBase.write(self, s)
        self._check_overflow()

    def close(self):
        """ Close random-access file. """
        devices.CRLFTextFileBase.close(self)
        self.output_stream.close()
        _release_lock(self.number)

    def get(self, dummy=None):
        """ Read a record. """
        if self.eof():
            contents = '\0' * self.reclen
        else:
            contents = self.output_stream.read(self.reclen)
        # take contents and pad with NULL to required size
        self.field.buffer[:] = contents + '\0' * (self.reclen - len(contents))
        # reset field text file loc
        self.fhandle.seek(0)
        self.recpos += 1

    def put(self, dummy=None):
        """ Write a record. """
        current_length = self.lof()
        if self.recpos > current_length:
            self.output_stream.seek(0, 2)
            numrecs = self.recpos-current_length
            self.output_stream.write('\0' * numrecs * self.reclen)
        self.output_stream.write(self.field.buffer)
        self.recpos += 1

    def set_pos(self, newpos):
        """ Set current record number. """
        # first record is newpos number 1
        self.output_stream.seek((newpos-1)*self.reclen)
        self.recpos = newpos - 1

    def loc(self):
        """ Get number of record just past, for LOC. """
        return self.recpos

    def eof(self):
        """ Return whether we're past currentg end-of-file, for EOF. """
        return self.recpos*self.reclen > self.lof()

    def lof(self):
        """ Get length of file, in bytes, for LOF. """
        current = self.output_stream.tell()
        self.output_stream.seek(0, 2)
        lof = self.output_stream.tell()
        self.output_stream.seek(current)
        return lof

    def lock(self, start, stop, lock_list):
        """ Lock range of records. """
        bstart, bstop = (start-1) * self.reclen, stop*self.reclen - 1
        other_lock_list = set.union(f.lock_list for f in _list_locks(self.name))
        for start_1, stop_1 in other_lock_list:
            if (stop_1 == -1 or (bstart >= start_1 and bstart <= stop_1)
                             or (bstop >= start_1 and bstop <= stop_1)):
                raise error.RunError(error.PERMISSION_DENIED)
        self.lock_list.add((bstart, bstop))

    def unlock(self, start, stop, lock_list):
        """ Unlock range of records. """
        bstart, bstop = (start-1) * self.reclen, stop*self.reclen - 1
        # permission denied if the exact record range wasn't given before
        try:
            self.lock_list.remove((bstart, bstop))
        except KeyError:
            raise error.RunError(error.PERMISSION_DENIED)


class TextFile(devices.CRLFTextFileBase):
    """ Text file on disk device. """

    def __init__(self, fhandle, filetype, number, name,
                 mode='A', access='RW', lock='',
                 utf8=False, universal=False, split_long_lines=True):
        """ Initialise text file object. """
        devices.CRLFTextFileBase.__init__(self, fhandle, filetype, mode,
                                          '', split_long_lines)
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
        devices.CRLFTextFileBase.close(self)
        _release_lock(self.number)

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
            s = (state.console_state.codepage
                .str_to_unicode(s).encode('utf-8', 'replace'))
        devices.CRLFTextFileBase.write(self, s + '\r\n')

    def write(self, s):
        """ Write to file in normal or UTF-8 mode. """
        if self.utf8:
            s = (state.console_state.codepage
                .str_to_unicode(s).encode('utf-8', 'replace'))
        devices.CRLFTextFileBase.write(self, s)

    def _read_line_universal(self):
        """ Read line from ascii program file with universal newlines. """
        # keep reading until any kind of line break
        # is followed by a line starting with a number
        s, c = self.spaces, ''
        self.spaces = ''
        while not self._check_long_line(s):
            # read converts CRLF to CR
            c = self.read(1)
            if not c:
                break
            elif c in ('\r', '\n'):
                # break on CR, CRLF, LF if next line starts with number or eof
                while self.next_char in (' ', '\0'):
                    c = self.read(1)
                    self.spaces += c
                if self.next_char in string.digits or self.next_char in ('', '\x1a'):
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
            s = devices.CRLFTextFileBase.read_line(self)
        else:
            s = self._read_line_universal()
        if self.utf8 and s is not None:
            s = state.console_state.codepage.str_from_unicode(s.decode('utf-8'))
        return s

    def lock(self, start, stop, lock_list):
        """ Lock the file. """
        if set.union(f.lock_list for f in _list_locks(self.name)):
            raise error.RunError(error.PERMISSION_DENIED)
        self.lock_list.add((0, -1))

    def unlock(self, start, stop):
        """ Unlock the file. """
        try:
            self.lock_list.remove((0, -1))
        except KeyError:
            raise error.RunError(error.PERMISSION_DENIED)

prepare()
