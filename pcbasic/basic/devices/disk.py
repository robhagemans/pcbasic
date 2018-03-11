"""
PC-BASIC - disk.py
Disk Devices

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

##############################################################################
# Disk devices

import os
import re
import sys
import errno
import string
import locale
import struct
import random
import ntpath
import logging

if sys.platform == 'win32':
    import ctypes
    from ctypes.wintypes import LPCWSTR, LPWSTR, DWORD

from ..base.bytestream import ByteStream
from ..base import error
from .. import values
from . import devicebase


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


# translate os error codes to BASIC error codes
OS_ERROR = {
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
    # device io error
    errno.EIO: error.DEVICE_IO_ERROR,
    # path/file access error
    errno.EEXIST: error.PATH_FILE_ACCESS_ERROR,
    errno.ENOTEMPTY: error.PATH_FILE_ACCESS_ERROR,
}

# allowable characters in DOS file name
# GW-BASIC also allows 0x7F and up, but replaces accented chars with unaccented
# based on CHCP code page, which may differ from display codepage in COUNTRY.SYS
# this is complex and leads to unpredictable results depending on host platform.
ALLOWABLE_CHARS = set(string.ascii_letters + string.digits + b" !#$%&'()-@^_`{}~")


##############################################################################
# exception handling

def safe(fnname, *fnargs):
    """Execute OS function and handle errors."""
    try:
        return fnname(*fnargs)
    except EnvironmentError as e:
        handle_oserror(e)

def handle_oserror(e):
    """Translate OS and I/O exceptions to BASIC errors."""
    try:
        basic_err = OS_ERROR[e.errno]
    except KeyError:
        logging.error(u'Unmapped environment exception: %d', e.errno)
        basic_err = error.DEVICE_IO_ERROR
    raise error.BASICError(basic_err)


##############################################################################
# short filenames

if sys.platform == 'win32':
    _GetShortPathName = ctypes.windll.kernel32.GetShortPathNameW
    _GetShortPathName.argtypes = [LPCWSTR, LPWSTR, DWORD]

    def get_short_pathname(native_path):
        """Return Windows short path name or None if not available."""
        try:
            length = _GetShortPathName(native_path, LPWSTR(0), DWORD(0))
            wbuffer = ctypes.create_unicode_buffer(length)
            _GetShortPathName(native_path, wbuffer, DWORD(length))
        except Exception as e:
            # something went wrong - this should be a WindowsError which is an OSError
            # but not clear
            return None
        else:
            # can also be None in wbuffer.value if error
            return wbuffer.value

else:
    def get_short_pathname(native_path):
        """Return Windows short path name or None if not available."""
        return None


##############################################################################
# dos path and filename utilities

def dos_splitext(dos_name):
    """Return trunk and extension excluding the dot."""
    # take whatever comes after first dot as extension
    # and whatever comes before first dot as trunk
    # differs from ntpath.splitext:
    # - does not include . in extension; no extension equals ending in .
    # - dotfiles are trunks starting with . in ntpath but extensions here.
    elements = dos_name.split(b'.', 1)
    if len(elements) == 1:
        trunk, ext = elements[0], ''
    else:
        trunk, ext = elements
    return trunk, ext

def dos_normalise_name(dos_name):
    """Convert dosname into bytes uppercase 8.3."""
    # a normalised DOS-name is all-uppercase, no leading or trailing spaces, and
    # 1) . or ..; or
    # 2) 0--8 allowable characters followed by one dot followed by 0--3 allowable characters; or
    # 3) 1--8 allowable characters with no dots
    #
    # don't try to split special directory names
    if dos_name in (b'.', b'..'):
        return dos_name
    # convert to all uppercase
    dos_name = dos_name.upper()
    # split into trunk and extension
    trunk, ext = dos_splitext(dos_name)
    # truncate to 8.3
    trunk, ext = trunk[:8], ext[:3]
    if ext:
        ext = b'.' + ext
    norm_name = trunk + ext
    return norm_name

def dos_is_legal_name(dos_name):
    """Check if a (bytes) name is a legal DOS name."""
    if dos_name in (b'.', b'..'):
        return True
    trunk, ext = dos_splitext(dos_name)
    return (
            # enforce lengths
            (len(trunk) <= 8 and len(ext) <= 3) and
            # no leading or trailing spaces
            (trunk == trunk.strip() and ext == ext.strip()) and
            # enforce allowable characters
            ((set(trunk) | set(ext)) <= ALLOWABLE_CHARS)
        )

def dos_to_native_name(native_path, dosname, isdir):
    """Find a matching native file name for a given normalised DOS name."""
    try:
        uni_name = dosname.decode(b'ascii')
    except UnicodeDecodeError:
        # non-ascii characters are not allowable for DOS filenames, no match
        return None
    # check if the 8.3 uppercase exists, prefer if so
    if istype(native_path, uni_name, isdir):
        return uni_name
    # otherwise try in lexicographic order
    try:
        all_names = os.listdir(native_path)
    except EnvironmentError:
        # report no match if listdir fails
        return None
    for f in sorted(all_names):
        # we won't match non-ascii anyway
        try:
            ascii_name = f.encode(b'ascii')
        except UnicodeEncodeError:
            continue
        # don't match long names or non-legal dos names
        if dos_is_legal_name(ascii_name):
            try_name = dos_normalise_name(ascii_name)
            if try_name == dosname and istype(native_path, f, isdir):
                return f
    return None

def dos_name_matches(name, mask):
    """Whether native name element matches DOS wildcard mask."""
    # convert wildcard mask to regexp
    regexp = '\A'
    for c in mask.upper():
        if c == '?':
            regexp += '.'
        elif c == '*':
            # we won't need to match newlines, so dot is fine
            regexp += '.*'
        else:
            regexp += re.escape(c)
    regexp += '\Z'
    cregexp = re.compile(regexp)
    return cregexp.match(name.upper()) is not None


##############################################################################
# disk device mapped to native filesystem

class DiskDevice(object):
    """Disk device (A:, B:, C:, ...) """

    allowed_modes = b'IOR'

    # posix access modes for BASIC modes INPUT, OUTPUT, RANDOM, APPEND
    access_modes = {b'I': b'rb', b'O': b'wb', b'R': b'r+b', b'A': b'ab'}
    # posix access modes for BASIC ACCESS mode for RANDOM files only
    access_access = {b'R': b'rb', b'W': b'wb', b'RW': b'r+b'}

    def __init__(self, letter, path, dos_cwd, locks, codepage, utf8, universal):
        """Initialise a disk device."""
        # DOS drive letter
        self.letter = letter
        # mount root: this is a native filesystem path, using os.sep
        self._native_root = path
        # code page for file system names and text file conversion
        self._codepage = codepage
        # current DOS working directory on this drive
        # this is a DOS relative path, no drive letter; including leading \\
        # stored with os.sep but given using backslash separators
        self._native_cwd = u''
        if self._native_root:
            try:
                self._native_cwd = self._get_native_reldir(dos_cwd)
            except error.BASICError:
                logging.warning(
                    'Could not open working directory %s on drive %s:. Using drive root instead.',
                    dos_cwd, letter)
        self._locks = locks
        # text file settings
        self._utf8 = utf8
        self._universal = universal

    def close(self):
        """Close disk device."""
        pass

    def available(self):
        """Device is available."""
        return True

    def _create_file_object(self, fhandle, filetype, mode, native_name=u'', number=0,
                           access=b'RW', lock=b'', field=None, reclen=128,
                           seg=0, offset=0, length=0):
        """Create disk file object of requested type."""
        # determine file type if needed
        if len(filetype) > 1 and mode == b'I':
            # read magic
            first = fhandle.read(1)
            fhandle.seek(-len(first), 1)
            try:
                filetype_found = devicebase.MAGIC_TO_TYPE[first]
                if filetype_found not in filetype:
                    raise error.BASICError(error.BAD_FILE_MODE)
                filetype = filetype_found
            except KeyError:
                filetype = b'A'
        if filetype in b'BPM':
            # binary [B]LOAD, [B]SAVE
            return BinaryFile(fhandle, filetype, number, native_name, mode,
                               seg, offset, length, locks=self._locks)
        elif filetype == b'A':
            # ascii program file (UTF8 or universal newline if option given)
            return TextFile(fhandle, filetype, number, native_name, mode, access, lock,
                             codepage=None if not self._utf8 else self._codepage,
                             universal=self._universal,
                             split_long_lines=False, locks=self._locks)
        elif filetype == b'D':
            if mode in b'IAO':
                # text data
                return TextFile(fhandle, filetype, number, native_name, mode, access, lock, locks=self._locks)
            else:
                return RandomFile(fhandle, number, native_name, access, lock, field, reclen, locks=self._locks)
        else:
            # incorrect file type requested
            msg = b'Incorrect file type %s requested for mode %s' % (filetype, mode)
            raise ValueError(msg)

    def open(self, number, filespec, filetype, mode, access, lock,
                   reclen, seg, offset, length, field):
        """Open a file on a disk drive."""
        # parse the file spec to a definite native name
        if not self._native_root:
            # undefined disk drive: path not found
            raise error.BASICError(error.PATH_NOT_FOUND)
        # set default extension for programs
        if set(filetype).intersection(set(b'MPBA')):
            defext = b'BAS'
        else:
            defext = b''
        # translate the file name to something DOS-ish if necessary
        if mode == b'I':
            native_name = self._get_native_abspath(filespec, defext, isdir=False, create=False)
        else:
            # random files: try to open matching file
            # if it doesn't exist, use an all-caps 8.3 file name
            native_name = self._get_native_abspath(filespec, defext, isdir=False, create=True)
        # handle locks, open stream and create file object
        # don't open output or append files more than once
        if mode in (b'O', b'A'):
            self._check_file_not_open(native_name)
        # obtain a lock
        if filetype == b'D':
            self._locks.acquire(native_name, number, lock, access)
        try:
            # open the underlying stream
            fhandle = self._open_stream(native_name, mode, access)
            # apply the BASIC file wrapper
            f = self._create_file_object(
                    fhandle, filetype, mode, native_name, number,
                    access, lock, field, reclen, seg, offset, length)
            # register file as open
            self._locks.open_file(number, f)
            return f
        except Exception:
            if filetype == b'D':
                self._locks.release(number)
            self._locks.close_file(number)
            raise

    def _open_stream(self, native_name, mode, access):
        """Open a stream on disk by os-native name with BASIC mode and access level."""
        name = native_name
        if (access and mode == b'R'):
            posix_access = self.access_access[access]
        else:
            posix_access = self.access_modes[mode]
        try:
            # create file if in RANDOM or APPEND mode and doesn't exist yet
            # OUTPUT mode files are created anyway since they're opened with wb
            if ((mode == b'A' or (mode == b'R' and access in (b'RW', b'R'))) and
                    not os.path.exists(name)):
                open(name, 'wb').close()
            if mode == b'A':
                # APPEND mode is only valid for text files (which are seekable);
                # first cut off EOF byte, if any.
                f = open(name, 'r+b')
                try:
                    f.seek(-1, 2)
                    if f.read(1) == b'\x1a':
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
            raise error.BASICError(error.BAD_FILE_NUMBER)

    def _get_native_reldir(self, dospath):
        """Return the native dir path for a given BASIC dir path, relative to the root."""
        if b'/' in dospath:
            # bad file number - this is what GW produces here
            raise error.BASICError(error.BAD_FILE_NUMBER)
        if not self._native_root:
            # this drive letter is not available (not mounted)
            raise error.BASICError(error.PATH_NOT_FOUND)
        # find starting directory
        if dospath and dospath[0] == b'\\':
            # absolute path specified
            cwd = []
        else:
            cwd = self._native_cwd.split(os.sep)
        # parse internal .. and . and double slashes
        dospath = ntpath.normpath(dospath)
        # parse leading . and .. and double slashes in relative path
        # if at root, just drop leading dots (this is what GW-BASIC does at drive root)
        dospath_elements = dospath.split(b'\\')
        while dospath_elements and dospath_elements[0] in (b'', b'.', b'..'):
            if dospath_elements[0] == b'..':
                cwd = cwd[:-1]
            dospath_elements = dospath_elements[1:]
        # prepend drive root path to allow filename matching
        path = os.path.join(self._native_root, *cwd)
        root_len = len(self._native_root) + (self._native_root[-1] != os.sep)
        # find the native matches for each step in the path
        for dos_elem in dospath_elements:
            # find a matching directory for every step in the path;
            native_elem = self._get_native_name(
                    path, dos_elem, defext=b'', isdir=True, create=False)
            # append found name to path
            path = os.path.join(path, native_elem)
        # return relative path only
        return path[root_len:]

    def _get_native_abspath(self, path, defext, isdir, create):
        """\
            Find os-native path to match the given BASIC path; apply default extension.
            path: bytes             requested DOS path to file on this device
            defext: bytes           default extension, to apply if no dot in basename
            create: bool            allow creating a new name for the proposed DOS name
                                    if not, throw if matched basename does not exist
            isdir: bool             basename should refer to a directory
        """
        # substitute drives and cwds
        # always use Path Not Found error if not found at this stage
        dos_dirname, name = ntpath.split(path)
        native_relpath = self._get_native_reldir(dos_dirname)
        # return absolute path to file
        path = os.path.join(self._native_root, native_relpath)
        if name:
            path = os.path.join(path, self._get_native_name(path, name, defext, isdir, create))
        # get full normalised path
        return os.path.abspath(path)

    def chdir(self, dos_path):
        """Change working directory to given BASIC path."""
        # get drive path and relative path
        native_relpath = self._get_native_reldir(dos_path)
        # set cwd for the specified drive
        self._native_cwd = native_relpath

    def mkdir(self, dos_path):
        """Create directory at given BASIC path."""
        safe(os.mkdir, self._get_native_abspath(dos_path, defext=b'', isdir=True, create=True))

    def rmdir(self, dos_path):
        """Remove directory at given BASIC path."""
        safe(os.rmdir, self._get_native_abspath(dos_path, defext=b'', isdir=True, create=False))

    def kill(self, dos_path):
        """Remove regular file at given native path."""
        native_path = self._get_native_abspath(dos_path, defext=b'', isdir=False, create=False)
        # don't delete open files
        self._check_file_not_open(native_path)
        safe(os.remove, native_path)

    def rename(self, old_dospath, new_dospath):
        """Rename a file or directory."""
        old_native_path = self._get_native_abspath(
                old_dospath, defext=b'', isdir=False, create=False)
        new_native_path = self._get_native_abspath(
                new_dospath, defext=b'', isdir=False, create=True)
        if os.path.exists(new_native_path):
            raise error.BASICError(error.FILE_ALREADY_EXISTS)
        safe(os.rename, old_native_path, new_native_path)

    def _split_pathmask(self, dos_pathmask):
        """Split pathmask into path and mask."""
        # forward slashes - file not found
        # GW-BASIC sometimes allows leading or trailing slashes
        # and then does weird things I don't understand.
        if b'/' in dos_pathmask:
            raise error.BASICError(error.FILE_NOT_FOUND)
        # note that ntpath would otherwise accept / as \\
        dos_path, dos_mask = ntpath.split(dos_pathmask)
        try:
            native_relpath = self._get_native_reldir(dos_path)
        except error.BASICError as e:
            # any path name problem in FILES: GW-BASIC throws file not found
            raise error.BASICError(error.FILE_NOT_FOUND)
        native_path = os.path.join(self._native_root, native_relpath)
        return native_path, native_relpath, dos_mask

    def _get_dirs_files(self, native_path):
        """Get native filenames for native path."""
        all_names = safe(os.listdir, native_path)
        dirs = [n for n in all_names if os.path.isdir(os.path.join(native_path, n))]
        fils = [n for n in all_names if not os.path.isdir(os.path.join(native_path, n))]
        return dirs, fils

    def listdir(self, pathmask):
        """Get directory listing."""
        native_path, native_relpath, dos_mask = self._split_pathmask(pathmask)
        fils = []
        if dos_mask in (b'.', b'..'):
            # following GW, we just show a single dot if asked for either . or ..
            dirs = [(u'', u'')]
        else:
            dirs, fils = self._get_dirs_files(native_path)
            # filter according to mask
            dirs = self._filter_names(native_path, dirs + [u'.', u'..'], dos_mask)
            fils = self._filter_names(native_path, fils, dos_mask)
        # format contents
        return (
            [t.ljust(8) + (b'.' if e or not t else b' ') + e.ljust(3) + b'<DIR>' for t, e in dirs] +
            [t.ljust(8) + (b'.' if e or not t else b' ') + e.ljust(3) + b'     ' for t, e in fils]
        )

    def get_cwd(self):
        """Return the current working directory in DOS format."""
        native_path = self._native_root
        dir_elems = []
        if self._native_cwd:
            for e in self._native_cwd.split(os.sep):
                dir_elems.append(self._get_dos_display_name(native_path, e))
                native_path += os.sep + e
        return self.letter + b':\\' + b'\\'.join(dir_elems)

    def get_free(self):
        """Return the number of free bytes on the drive."""
        if sys.platform == 'win32':
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(self._native_root), None, None, ctypes.pointer(free_bytes))
            return free_bytes.value
        else:
            st = os.statvfs(self._native_root.encode(locale.getpreferredencoding()))
            return st.f_bavail * st.f_frsize

    def require_file_exists_and_not_open(self, dospath):
        """Raise an error if the file is open or does not exist."""
        # this checks for existence if name_err is set
        native_name = self._get_native_abspath(dospath, defext=b'', isdir=False, create=False)
        return self._check_file_not_open(native_name)

    def _check_file_not_open(self, native_path):
        """Raise an error if the file is open."""
        for f in self._locks.open_files.values():
            try:
                if native_path == f.name:
                    raise error.BASICError(error.FILE_ALREADY_OPEN)
            except AttributeError as e:
                # only disk files have a name, so ignore
                pass

    ##########################################################################
    # DOS and native name conversion

    def _get_native_name(self, native_path, dos_name, defext, isdir, create):
        """Find or create a matching native file name for a given BASIC name."""
        # if the name contains a dot, do not apply the default extension
        # to maintain GW-BASIC compatibility, a trailing single dot matches the name
        # with no dots as well as the name with a single dot.
        # file names with more than one dot are not affected.
        # file spec         attempted matches
        # LongFileName      (1) LongFileName.BAS (2) LONGFILE.BAS
        # LongFileName.bas  (1) LongFileName.bas (2) LONGFILE.BAS
        # LongFileName.     (1) LongFileName. (2) LongFileName (3) LONGFILE
        # LongFileName..    (1) LongFileName.. (2) [does not try LONGFILE.. - not allowable]
        # Long.FileName.    (1) Long.FileName. (2) LONG.FIL
        #
        # don't accept leading or trailing whitespace (internal whitespace should be preserved)
        # note that DosBox removes internal whitespace, but MS-DOS does not
        name_err = error.PATH_NOT_FOUND if isdir else error.FILE_NOT_FOUND
        if dos_name != dos_name.strip():
            raise error.BASICError(name_err)
        if defext and b'.' not in dos_name:
            dos_name += b'.' + defext
        elif dos_name[-1] == b'.' and b'.' not in dos_name[:-1]:
            # ends in single dot; first try with dot
            # but if it doesn't exist, base everything off dotless name
            uni_name = self._codepage.str_to_unicode(dos_name, box_protect=False)
            if istype(native_path, uni_name, isdir):
                return uni_name
            dos_name = dos_name[:-1]
        # check if the name exists as-is; should also match Windows short names.
        uni_name = self._codepage.str_to_unicode(dos_name, box_protect=False)
        if istype(native_path, uni_name, isdir):
            return uni_name
        # original name does not exist; try matching dos-names or create one
        # normalise to 8.3
        norm_name = dos_normalise_name(dos_name)
        # check for non-legal characters & spaces (but clip off overlong names)
        if not dos_is_legal_name(norm_name):
            raise error.BASICError(error.BAD_FILE_NAME)
        fullname = dos_to_native_name(native_path, norm_name, isdir)
        if fullname:
            return fullname
        # not found
        if create:
            # create a new filename
            return norm_name.decode(b'ascii')
        else:
            raise error.BASICError(name_err)

    def _get_dos_display_name(self, native_dirpath, native_name):
        """Convert native name to short name or (not normalised or even legal) dos-style name."""
        native_path = os.path.join(native_dirpath, native_name)
        # get the short name if it exists, keep long name otherwise
        if sys.platform == 'win32':
            native_path = get_short_pathname(native_path) or native_path
        native_name = os.path.basename(native_path)
        # see if we have a legal dos name that matches
        try:
            ascii_name = native_name.encode('ascii')
        except UnicodeEncodeError:
            pass
        else:
            if dos_is_legal_name(ascii_name):
                return dos_normalise_name(ascii_name)
        # convert to codepage
        cp_name = self._codepage.str_from_unicode(native_name, errors='replace')
        # clip overlong & mark as shortened
        trunk, ext = dos_splitext(cp_name)
        if len(trunk) > 8:
            trunk = trunk[:7] + b'+'
        if len(ext) > 3:
            ext = ext[:2] + b'+'
        return trunk + (b'.' if ext or not trunk else b'') + ext

    def _filter_names(self, native_dirpath, native_names, dos_mask):
        """Apply case-insensitive filename filter to display names."""
        dos_mask = dos_mask or b'*.*'
        trunkmask, extmask = dos_splitext(dos_mask)
        all_files = (self._get_dos_display_name(native_dirpath, name) for name in native_names)
        split = [dos_splitext(dos_name) for dos_name in all_files]
        return sorted(
                (trunk, ext) for (trunk, ext) in split
                if dos_name_matches(trunk, trunkmask) and dos_name_matches(ext, extmask)
            )


##############################################################################
# Native path utilities

def istype(native_path, native_name, isdir):
    """Return whether a file exists and is a directory or regular."""
    name = os.path.join(native_path, native_name)
    try:
        return os.path.isdir(name) if isdir else os.path.isfile(name)
    except TypeError:
        # happens for name == u'\0'
        return False


##############################################################################
# Internal disk and bound files

class BoundFile(object):
    """Bound internal file."""

    def __init__(self, device, file_name_or_object, name):
        self._device = device
        self._file = file_name_or_object
        self._name = name

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, *dummies):
        """Context guard."""
        self._device.unbind(self._name)

    def get_stream(self, mode):
        """Get a native stream for the bound file."""
        try:
            if isinstance(self._file, basestring):
                return open(self._file, self._device.access_modes[mode])
            else:
                return self._file
        except EnvironmentError as e:
            handle_oserror(e)

    def __str__(self):
        """Get BASIC file name."""
        return b'%s:%s' % (self._device.letter, self._name)


class InternalDiskDevice(DiskDevice):
    """Internal disk device for special operations."""

    def __init__(self, letter, path, cwd, locks, codepage, utf8, universal):
        """Initialise internal disk."""
        self._bound_files = {}
        DiskDevice.__init__(self, letter, path, cwd, locks, codepage, utf8, universal)

    def bind(self, file_name_or_object, name=None):
        """Bind a native file name or object to an internal name."""
        if not name:
            # get unused 7-hexit string
            num_ids = 0x10000000
            for _ in xrange(num_ids):
                name = (b'#%07x' % random.randint(0, num_ids)).upper()
                if name not in self._bound_files:
                    break
            else:
                # unlikely
                logging.error('No internal bound-file names available')
                raise error.BASICError(error.TOO_MANY_FILES)
        self._bound_files[name] = BoundFile(self, file_name_or_object, name)
        return self._bound_files[name]

    def unbind(self, name):
        """Unbind bound file."""
        del self._bound_files[name]

    def open(self, number, filespec, filetype, mode, access, lock,
                   reclen, seg, offset, length, field):
        """Open a file on the internal disk drive."""
        if filespec in self._bound_files:
            fhandle = self._bound_files[filespec].get_stream(mode)
            try:
                return self._create_file_object(fhandle, filetype, mode)
            except EnvironmentError as e:
                handle_oserror(e)
        else:
            return DiskDevice.open(
                    self, number, filespec, filetype, mode, access, lock,
                    reclen, seg, offset, length, field)

    def _split_pathmask(self, pathmask):
        """Split pathmask into path and mask."""
        if self._native_root:
            return DiskDevice._split_pathmask(self, pathmask)
        else:
            return u'', u'', pathmask.upper() or b'*.*'

    def _get_dirs_files(self, path):
        """get native filenames for native path."""
        if self._native_root:
            dirs, files = DiskDevice._get_dirs_files(self, path)
        else:
            dirs, files = [], []
        files += self._bound_files.keys()
        return dirs, files

    def get_cwd(self):
        """Return the current working directory in DOS format."""
        if self._native_root:
            return DiskDevice.get_cwd(self)
        else:
            return self.letter + b':\\'

    def get_free(self):
        """Return the number of free bytes on the drive."""
        if self._native_root:
            return DiskDevice.get_free(self)
        else:
            return 0


###############################################################################
# Locks

class Locks(object):
    """Lock management."""

    def __init__(self):
        """Initialise locks."""
        # dict of native file names by number, for locking
        self._locks = {}
        # dict of disk files
        self.open_files = {}

    def list(self, name):
        """Retrieve a list of files open to the same disk stream."""
        return [ self.open_files[fnum]
                       for (fnum, fname) in self._locks.iteritems()
                       if fname == name ]

    def acquire(self, name, number, lock_type, access):
        """Try to lock a file."""
        if not number:
            return
        already_open = self.list(name)
        for f in already_open:
            if (
                    # default mode: don't accept if SHARED/LOCK present
                    ((not lock_type) and f.lock_type) or
                    # LOCK READ WRITE: don't accept if already open
                    (lock_type == b'RW') or
                    # SHARED: don't accept if open in default mode
                    (lock_type == b'SHARED' and not f.lock_type) or
                    # LOCK READ or LOCK WRITE: accept base on ACCESS of open file
                    (lock_type in f.access) or (f.lock_type in access)):
                raise error.BASICError(error.PERMISSION_DENIED)
        self._locks[number] = name

    def release(self, number):
        """Release the lock on a file before closing."""
        try:
            del self._locks[number]
        except KeyError:
            pass

    def open_file(self, number, f):
        """Register disk file as open."""
        self.open_files[number] = f

    def close_file(self, number):
        """Deregister disk file."""
        try:
            del self.open_files[number]
        except KeyError:
            pass


#################################################################################
# Disk files

class BinaryFile(devicebase.RawFile):
    """File class for binary (B, P, M) files on disk device."""

    def __init__(self, fhandle, filetype, number, name, mode,
                       seg, offset, length, locks=None):
        """Initialise program file object and write header."""
        devicebase.RawFile.__init__(self, fhandle, filetype, mode)
        self.number = number
        # don't lock binary files
        self.lock = b''
        # we need the Locks object to register file as open
        self._locks = locks
        self.access = b'RW'
        self.seg, self.offset, self.length = 0, 0, 0
        if self.mode == b'O':
            self.write(devicebase.TYPE_TO_MAGIC[filetype])
            if self.filetype == b'M':
                self.write(struct.pack(b'<HHH', seg, offset, length))
                self.seg, self.offset, self.length = seg, offset, length
        else:
            # drop magic byte
            self.read_raw(1)
            if self.filetype == b'M':
                # self.length gets ignored: even the \x1a at the end is read
                header = self.read(6)
                if len(header) == 6:
                    self.seg, self.offset, self.length = struct.unpack(b'<HHH', header)
                else:
                    # truncated header
                    raise error.BASICError(error.BAD_FILE_MODE)

    def close(self):
        """Write EOF and close program file."""
        if self.mode == b'O':
            self.write(b'\x1a')
        devicebase.RawFile.close(self)
        if self._locks is not None:
            # no locking for binary files, but we do need to register it closed
            self._locks.close_file(self.number)


class CRLFTextFileBase(devicebase.TextFileBase):
    """Text file with CRLF line endings, on disk device or field buffer."""

    def read(self, num=-1):
        """Read num characters, replacing CR LF with CR."""
        s = ''
        while len(s) < num:
            c = self.read_raw(1)
            if not c:
                break
            s += c
            # report CRLF as CR
            # but LFCR, LFCRLF, LFCRLFCR etc pass unmodified
            if (c == '\r' and self.last != '\n') and self.next_char == '\n':
                last, char = self.last, self.char
                self.read_raw(1)
                self.last, self.char = last, char
        return s

    def read_line(self):
        """Read line from text file, break on CR or CRLF (not LF)."""
        s = ''
        while not self._check_long_line(s):
            c = self.read(1)
            if not c or (c == '\r' and self.last != '\n'):
                # break on CR, CRLF but allow LF, LFCR to pass
                break
            else:
                s += c
        if not c and not s:
            return None
        return s

    def write_line(self, s=''):
        """Write string or bytearray and newline to file."""
        self.write(str(s) + '\r\n')


class RandomFile(CRLFTextFileBase):
    """Random-access file on disk device."""

    def __init__(self, output_stream, number, name,
                        access, lock, field, reclen=128, locks=None):
        """Initialise random-access file."""
        # all text-file operations on a RANDOM file (PRINT, WRITE, INPUT, ...)
        # actually work on the FIELD buffer; the file stream itself is not
        # touched until PUT or GET.
        self.reclen = reclen
        # replace with empty field if already exists
        self._field = field
        CRLFTextFileBase.__init__(self, ByteStream(self._field.buffer), b'D', b'R')
        self.operating_mode = b'I'
        # note that for random files, output_stream must be a seekable stream.
        self.output_stream = output_stream
        self.lock_type = lock
        self.access = access
        self.lock_list = set()
        self._locks = locks
        self.number = number
        self.name = name
        # position at start of file
        self.recpos = 0
        self.output_stream.seek(0)

    def switch_mode(self, new_mode):
        """Switch to input or output mode"""
        if new_mode == b'I' and self.operating_mode == b'O':
            self.flush()
            self.next_char = self.fhandle.read(1)
            self.operating_mode = b'I'
        elif new_mode == b'O' and self.operating_mode == b'I':
            self.fhandle.seek(-1, 1)
            self.operating_mode = b'O'

    def _check_overflow(self):
        """Check for FIELD OVERFLOW."""
        write = self.operating_mode == b'O'
        # FIELD overflow happens if last byte in record has been read or written
        if self.fhandle.tell() > self.reclen + write - 1:
            raise error.BASICError(error.FIELD_OVERFLOW)

    def read_raw(self, num=-1):
        """Read num characters from the field."""
        # switch to reading mode and fix readahead buffer
        self.switch_mode('I')
        s = CRLFTextFileBase.read_raw(self, num)
        self._check_overflow()
        return s

    def write(self, s, can_break=True):
        """Write the string s to the field, taking care of width settings."""
        # switch to writing mode and fix readahead buffer
        self.switch_mode(b'O')
        CRLFTextFileBase.write(self, s, can_break)
        self._check_overflow()

    def close(self):
        """Close random-access file."""
        CRLFTextFileBase.close(self)
        self.output_stream.close()
        if self._locks is not None:
            self._locks.release(self.number)
            self._locks.close_file(self.number)

    def get(self, dummy=None):
        """Read a record."""
        if self.eof():
            contents = b'\0' * self.reclen
        else:
            contents = self.output_stream.read(self.reclen)
        # take contents and pad with NULL to required size
        self._field.buffer[:] = contents + b'\0' * (self.reclen - len(contents))
        # reset field text file loc
        self.fhandle.seek(0)
        self.recpos += 1

    def put(self, dummy=None):
        """Write a record."""
        current_length = self.lof()
        if self.recpos > current_length:
            self.output_stream.seek(0, 2)
            numrecs = self.recpos-current_length
            self.output_stream.write(b'\0' * numrecs * self.reclen)
        self.output_stream.write(self._field.buffer)
        self.recpos += 1

    def set_pos(self, newpos):
        """Set current record number."""
        # first record is newpos number 1
        self.output_stream.seek((newpos-1)*self.reclen)
        self.recpos = newpos - 1

    def loc(self):
        """Get number of record just past, for LOC."""
        return self.recpos

    def eof(self):
        """Return whether we're past currentg end-of-file, for EOF."""
        return self.recpos*self.reclen > self.lof()

    def lof(self):
        """Get length of file, in bytes, for LOF."""
        current = self.output_stream.tell()
        self.output_stream.seek(0, 2)
        lof = self.output_stream.tell()
        self.output_stream.seek(current)
        return lof

    def lock(self, start, stop):
        """Lock range of records."""
        other_lock_list = set.union(*(f.lock_list for f in self._locks.list(self.name)))
        for start_1, stop_1 in other_lock_list:
            if (stop_1 is None and start_1 is None
                        or (start >= start_1 and start <= stop_1)
                        or (stop >= start_1 and stop <= stop_1)):
                raise error.BASICError(error.PERMISSION_DENIED)
        self.lock_list.add((start, stop))

    def unlock(self, start, stop):
        """Unlock range of records."""
        # permission denied if the exact record range wasn't given before
        try:
            self.lock_list.remove((start, stop))
        except KeyError:
            raise error.BASICError(error.PERMISSION_DENIED)


class TextFile(CRLFTextFileBase):
    """Text file on disk device."""

    def __init__(self, fhandle, filetype, number, name,
                 mode=b'A', access=b'RW', lock=b'',
                 codepage=None, universal=False, split_long_lines=True, locks=None):
        """Initialise text file object."""
        CRLFTextFileBase.__init__(self, fhandle, filetype, mode,
                                          b'', split_long_lines)
        self.lock_list = set()
        self.lock_type = lock
        self._locks = locks
        self.access = access
        self.number = number
        self.name = name
        # if a codepage is supplied, text is converted to utf8
        # otherwise, it is read/written as raw bytes
        self._codepage = codepage
        self._universal = universal
        self.spaces = b''
        if self.mode == b'A':
            self.fhandle.seek(0, 2)
        elif self.mode == b'O' and self._codepage is not None:
            # start UTF-8 files with BOM as many Windows readers expect this
            self.fhandle.write(b'\xef\xbb\xbf')

    def close(self):
        """Close text file."""
        if self.mode in (b'O', b'A') and self._codepage is None:
            # write EOF char
            self.fhandle.write(b'\x1a')
        CRLFTextFileBase.close(self)
        if self._locks is not None:
            self._locks.release(self.number)
            self._locks.close_file(self.number)

    def loc(self):
        """Get file pointer LOC """
        # for LOC(i)
        if self.mode == b'I':
            return max(1, (127+self.fhandle.tell())/128)
        return self.fhandle.tell()/128

    def lof(self):
        """Get length of file LOF."""
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof

    def write_line(self, s=''):
        """Write to file in normal or UTF-8 mode."""
        if self._codepage is not None:
            s = (self._codepage.str_to_unicode(s).encode(b'utf-8', b'replace'))
        CRLFTextFileBase.write(self, s + '\r\n')

    def write(self, s, can_break=True):
        """Write to file in normal or UTF-8 mode."""
        if self._codepage is not None:
            s = (self._codepage.str_to_unicode(s).encode(b'utf-8', b'replace'))
        CRLFTextFileBase.write(self, s, can_break)

    def _read_line_universal(self):
        """Read line from ascii program file with universal newlines."""
        # keep reading until any kind of line break
        # is followed by a line starting with a number
        s, c = self.spaces, b''
        self.spaces = b''
        while not self._check_long_line(s):
            # read converts CRLF to CR
            c = self.read(1)
            if not c:
                break
            elif c in (b'\r', b'\n'):
                # break on CR, CRLF, LF if next line starts with number or eof
                while self.next_char in (b' ', b'\0'):
                    c = self.read(1)
                    self.spaces += c
                if self.next_char in string.digits or self.next_char in (b'', b'\x1a'):
                    break
                else:
                    s += b'\n' + self.spaces
                    self.spaces = b''
            else:
                s += c
        if not c and not s:
            return None
        return s

    def read_line(self):
        """Read line from text file."""
        if not self._universal:
            s = CRLFTextFileBase.read_line(self)
        else:
            s = self._read_line_universal()
        if self._codepage is not None and s is not None:
            s = self._codepage.str_from_unicode(s.decode(b'utf-8'))
        return s

    def lock(self, start, stop):
        """Lock the file."""
        if set.union(*(f.lock_list for f in self._locks.list(self.name))):
            raise error.BASICError(error.PERMISSION_DENIED)
        self.lock_list.add(True)

    def unlock(self, start, stop):
        """Unlock the file."""
        try:
            self.lock_list.remove(True)
        except KeyError:
            raise error.BASICError(error.PERMISSION_DENIED)
