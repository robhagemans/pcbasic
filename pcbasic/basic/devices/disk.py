"""
PC-BASIC - devices.disk
Disk Devices

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

##############################################################################
# Disk devices

import os
import re
import io
import sys
import errno
import ntpath
import logging

from ...compat import text_type, add_str
from ...compat import get_short_pathname, get_free_bytes, is_hidden, iterchar, random_id
from ...compat import is_readable_text_stream, is_writable_text_stream

from ..base import error
from ..base.tokens import ALPHANUMERIC
from ..codepage import CONTROL
from .. import values
from . import devicebase
from .diskfiles import BinaryFile, TextFile, RandomFile, Locks


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
ALLOWABLE_CHARS = set(ALPHANUMERIC + b" !#$%&'()-@^_`{}~")

# posix access modes for BASIC modes INPUT, OUTPUT, RANDOM, APPEND
ACCESS_MODES = {b'I': 'r', b'O': 'w', b'R': 'r+', b'A': 'a'}

# aliases for the utf-8 encoding
UTF_8 = ('utf_8', 'utf-8', 'utf', 'u8', 'utf8')


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
        logging.error(u'Unmapped environment exception: %s', e.errno)
        basic_err = error.DEVICE_IO_ERROR
    raise error.BASICError(basic_err)


##############################################################################
# dos path and filename utilities

def dos_splitext(dos_name):
    """Return trunk and extension excluding the dot."""
    # take whatever comes after first dot as extension
    # and whatever comes before first dot as trunk
    # differs from ntpath.splitext:
    # - does not include . in extension; no extension equals ending in .
    # - dotfiles are trunks starting with . in ntpath but extensions here.
    assert isinstance(dos_name, bytes), type(dos_name)
    elements = dos_name.split(b'.', 1)
    if len(elements) == 1:
        trunk, ext = elements[0], b''
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
    assert isinstance(dos_name, bytes), type(dos_name)
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
        uni_name = dosname.decode('ascii')
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
            ascii_name = f.encode('ascii')
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
    regexp = b'\\A'
    for c in iterchar(mask.upper()):
        if c == b'?':
            regexp += b'.'
        elif c == b'*':
            # we won't need to match newlines, so dot is fine
            regexp += b'.*'
        else:
            regexp += re.escape(c)
    regexp += b'\\Z'
    cregexp = re.compile(regexp)
    return cregexp.match(name.upper()) is not None


##############################################################################
# disk device mapped to native filesystem

class DiskDevice(object):
    """Disk device (A:, B:, C:, ...) """

    allowed_modes = b'IOR'

    def __init__(self, letter, path, cwd, codepage, text_mode, soft_linefeed):
        """Initialise a disk device."""
        assert isinstance(cwd, text_type), type(cwd)
        # DOS drive letter
        self.letter = letter
        # mount root: this is a native filesystem path, using os.sep
        self._native_root = path
        # code page for file system names and text file conversion
        self._codepage = codepage
        # current native working directory on this drive
        self._native_cwd = u''
        if self._native_root:
            self._native_cwd = cwd
        # locks are drive-specific
        self._locks = Locks()
        # text file settings
        # use a BOM on input and output, but not append
        if not text_mode:
            text_mode = ''
        if text_mode.lower() in UTF_8:
            text_mode = 'utf-8-sig'
        self._text_mode = text_mode
        self._soft_linefeed = soft_linefeed

    def close(self):
        """Close disk device."""
        pass

    def available(self):
        """Device is available."""
        return True

    @staticmethod
    def _is_text_file(filetype, mode):
        """Determine if a filetype and mode refer to a text file."""
        return filetype in (b'A', b'D') and mode in (b'O', b'A', b'I')

    def _create_file_object(
            self, fhandle, filetype, mode, number=0,
            field=None, reclen=128, seg=0, offset=0, length=0
        ):
        """Create disk file object of requested type."""
        # determine file type if needed
        if len(filetype) > 1:
            assert mode == b'I', 'file type can only be detected on input files'
            # read magic
            first = fhandle.read(1)
            fhandle.seek(0)
            try:
                filetype_found = devicebase.MAGIC_TO_TYPE[first]
                if filetype_found not in filetype:
                    raise error.BASICError(error.BAD_FILE_MODE)
                filetype = filetype_found
            except KeyError:
                filetype = b'A'
        # for text & ascii-program files, not for random-access files
        if self._is_text_file(filetype, mode):
            # access non-raw text files as text stream
            if self._text_mode and (
                    (mode == b'I' and not is_readable_text_stream(fhandle))
                    or (mode in (b'O', b'A') and not is_writable_text_stream(fhandle))
                ):
                # preserve original newlines on reading and writing
                fhandle = io.TextIOWrapper(
                    fhandle, encoding=self._text_mode, errors='replace', newline=''
                )
            # wrap unicode or bytes native stream so that we always read/write codepage bytes
            if mode in (b'O', b'A'):
                # if the input stream is unicode: decode codepage bytes
                fhandle = self._codepage.wrap_output_stream(fhandle, preserve=CONTROL+(b'\x1A',))
            else: #if mode == b'I':
                # if the input stream is unicode: encode codepage bytes
                # replace newlines with \r in text mode
                fhandle = self._codepage.wrap_input_stream(
                    fhandle, replace_newlines=not self._soft_linefeed
                )
            # ascii program file; or data file for input, output, append
            return TextFile(fhandle, filetype, number, mode, self._locks)
        elif filetype in (b'B', b'P', b'M'):
            # binary [B]LOAD, [B]SAVE
            return BinaryFile(fhandle, filetype, number, mode, seg, offset, length, self._locks)
        elif filetype == b'D' and mode == b'R':
            # data file for random
            return RandomFile(fhandle, number, field, reclen, self._locks)
        else:
            # incorrect file type requested
            msg = b'Incorrect file type %s requested for mode %s' % (filetype, mode)
            raise ValueError(msg)

    def open(
            self, number, filespec, filetype, mode, access, lock,
            reclen, seg, offset, length, field
        ):
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
        # whether it's the same file is determined by DOS basename, i.e. excluding directories!
        dos_basename = self._get_dos_name_defext(filespec, defext)
        # obtain a lock
        self._locks.open_file(dos_basename, number, mode, lock, access)
        try:
            # open the underlying stream
            fhandle = self.open_stream(native_name, filetype, mode)
            # apply the BASIC file wrapper
            return self._create_file_object(
                fhandle, filetype, mode, number, field, reclen, seg, offset, length
            )
        except Exception:
            self._locks.close_file(number)
            raise

    def open_stream(self, native_name, filetype, mode):
        """Open a stream on disk by os-native name with BASIC mode and access level."""
        try:
            # create file if in RANDOM or APPEND mode and doesn't exist yet
            # OUTPUT mode files are created anyway since they're opened with wb
            if ((mode == b'A' or mode == b'R') and not os.path.exists(native_name)):
                io.open(native_name, 'wb').close()
            if mode == b'A':
                f = io.open(native_name, 'r+b')
                # APPEND mode is only valid for text files (which are seekable);
                # first cut off EOF byte, if any.
                try:
                    f.seek(-1, 2)
                    if f.read(1) == b'\x1a':
                        f.seek(-1, 1)
                        f.truncate()
                except EnvironmentError:
                    pass
                f.close()
            access_mode = ACCESS_MODES[mode]
            stream = io.open(native_name, access_mode + 'b')
            return stream
        except EnvironmentError as e:
            handle_oserror(e)
        except TypeError:
            # TypeError: stat() argument 1 must be encoded string without null bytes, not str
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
        if dospath and dospath[:1] == b'\\':
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
        root_len = len(self._native_root) + (self._native_root[-1:] != os.sep)
        # find the native matches for each step in the path
        for dos_elem in dospath_elements:
            # find a matching directory for every step in the path;
            native_elem = self._get_native_name(
                path, dos_elem, defext=b'', isdir=True, create=False
            )
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

    def kill(self, dos_pathmask):
        """Remove regular files that match given BASIC path and mask."""
        native_dir, _, dos_mask = self._split_pathmask(dos_pathmask)
        _, files = self._get_dirs_files(native_dir)
        # filter according to mask
        trunkmask, extmask = dos_splitext(dos_mask)
        dos_to_native = {
            self._get_dos_display_name(native_dir, _native_name): _native_name
            for _native_name in files
        }
        to_kill_dos = []
        for dos_name in dos_to_native:
            trunk, ext = dos_splitext(dos_name)
            if dos_name_matches(trunk, trunkmask) and dos_name_matches(ext, extmask):
                to_kill_dos.append(dos_name)
        to_kill = [
            # NOTE that this depends on display names NOT being legal names for overlong names
            # i.e. a + is included at the end of the display name which is not legal
            os.path.join(native_dir, dos_to_native[_dos_name])
            for _dos_name in to_kill_dos
            if (
                dos_is_legal_name(_dos_name) and
                not is_hidden(os.path.join(native_dir, dos_to_native[_dos_name]))
            )
        ]
        if not to_kill:
            raise error.BASICError(error.FILE_NOT_FOUND)
        for dos_path in to_kill_dos:
            # don't delete open files
            self.require_file_not_open(dos_path)
        for native_path in to_kill:
            safe(os.remove, native_path)

    def rename(self, old_dospath, new_dospath):
        """Rename a file or directory."""
        old_native_path = self._get_native_abspath(
            old_dospath, defext=b'', isdir=False, create=False
        )
        new_native_path = self._get_native_abspath(
            new_dospath, defext=b'', isdir=False, create=True
        )
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
        native_path, _, dos_mask = self._split_pathmask(pathmask)
        fils = []
        if dos_mask in (b'.', b'..'):
            # following GW, we just show a single dot if asked for either . or ..
            dirs = [(b'', b'')]
        else:
            dirs, fils = self._get_dirs_files(native_path)
            # remove hidden files
            dirs = [d for d in dirs if not is_hidden(os.path.join(native_path, d))]
            fils = [f for f in fils if not is_hidden(os.path.join(native_path, f))]
            # filter according to mask
            dirs = self._filter_names(native_path, dirs + [u'.', u'..'], dos_mask)
            fils = self._filter_names(native_path, fils, dos_mask)
        # format contents
        return (
            [t.ljust(8) + (b'.' if e or not t else b' ') + e.ljust(3) + b'<DIR>' for t, e in dirs] +
            [t.ljust(8) + (b'.' if e or not t else b' ') + e.ljust(3) + b'     ' for t, e in fils]
        )

    def get_native_cwd(self):
        """Return the current working directory in native format."""
        return os.path.join(self._native_root, self._native_cwd)

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
        return get_free_bytes(self._native_root)

    def require_file_exists(self, dospath):
        """Raise an error if the file is open or does not exist."""
        # this checks for existence with create=False
        self._get_native_abspath(dospath, defext=b'', isdir=False, create=False)

    def require_file_not_open(self, dos_basename):
        """Raise an error if the file is open."""
        if self._locks.list_open(dos_basename):
            raise error.BASICError(error.FILE_ALREADY_OPEN)

    ##########################################################################
    # DOS and native name conversion

    def _get_dos_name_defext(self, dos_name, defext):
        """Strip trailing whitepace and apply default extension to DOS name."""
        # ignore trailing whitespace
        dos_name = dos_name.rstrip()
        if defext and b'.' not in dos_name:
            dos_name += b'.' + defext
        return dos_name

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
        # don't accept leading whitespace (internal whitespace should be preserved)
        # note that DosBox removes internal whitespace, but MS-DOS does not
        name_err = error.PATH_NOT_FOUND if isdir else error.FILE_NOT_FOUND
        if dos_name != dos_name.lstrip():
            raise error.BASICError(name_err)
        dos_name = self._get_dos_name_defext(dos_name, defext)
        if dos_name[-1:] == b'.' and b'.' not in dos_name[:-1]:
            # ends in single dot; first try with dot
            # but if it doesn't exist, base everything off dotless name
            uni_name = self._codepage.bytes_to_unicode(dos_name, box_protect=False)
            if istype(native_path, uni_name, isdir):
                return uni_name
            dos_name = dos_name[:-1]
        # check if the name exists as-is; should also match Windows short names.
        uni_name = self._codepage.bytes_to_unicode(dos_name, box_protect=False)
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
            # we should have only ascii due to dos_is_legal_name check above
            return norm_name.decode('ascii', errors='replace')
        else:
            raise error.BASICError(name_err)

    def _get_dos_display_name(self, native_dirpath, native_name):
        """Convert native name to short name or (not normalised or even legal) dos-style name."""
        native_path = os.path.join(native_dirpath, native_name)
        # get the short name if it exists, keep long name otherwise
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
        cp_name = self._codepage.unicode_to_bytes(native_name, errors='replace')
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
    except (TypeError, ValueError):
        # name == u'\0' - python2 raises TypeError, python3 ValueError
        return False


##############################################################################
# Internal disk and bound files

@add_str
class BoundFile(object):
    """Bound internal file."""

    def __init__(self, device, codepage, file_name_or_object, name):
        """Initialise."""
        assert isinstance(name, bytes)
        self._device = device
        self._codepage = codepage
        self._file = file_name_or_object
        self._name = name

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, *dummies):
        """Context guard."""
        self._device.unbind(self._name)

    def get_stream(self, filetype, mode):
        """Get a native stream for the bound file."""
        try:
            if isinstance(self._file, (bytes, text_type)):
                return self._device.open_stream(self._file, filetype, mode)
            else:
                return self._file
        except EnvironmentError as e:
            handle_oserror(e)

    def __bytes__(self):
        """Get BASIC file name."""
        return b'%s:%s' % (self._device.letter, self._name)

    def __unicode__(self):
        """Get BASIC file name."""
        return self._codepage.bytes_to_unicode(bytes(self), box_protect=False)


@add_str
class NameWrapper(object):
    """Use normal file name as return value from bind_file."""

    def __init__(self, codepage, name):
        """Initialise."""
        if isinstance(name, text_type):
            name = codepage.unicode_to_bytes(name)
        self._file = name
        self._codepage = codepage

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, *dummies):
        """Context guard."""

    def __bytes__(self):
        """Get BASIC file name."""
        return self._file

    def __unicode__(self):
        """Get BASIC file name."""
        return self._codepage.bytes_to_unicode(bytes(self), box_protect=False)


class InternalDiskDevice(DiskDevice):
    """Internal disk device for special operations."""

    def __init__(self, letter, path, cwd, codepage, text_mode, soft_linefeed):
        """Initialise internal disk."""
        self._bound_files = {}
        DiskDevice.__init__(self, letter, path, cwd, codepage, text_mode, soft_linefeed)

    def bind(self, file_name_or_object, name=None):
        """Bind a native file name or object to an internal name."""
        if not name:
            # get unused 7-hexit string eg. #9ABCDEF
            try:
                name = random_id(7, prefix=b'#', exclude=self._bound_files)
            except RuntimeError: # pragma: no cover
                # unlikely
                logging.error('No free internal bound-file names available')
                raise error.BASICError(error.TOO_MANY_FILES)
        elif isinstance(name, text_type):
            name = self._codepage.unicode_to_bytes(name)
        self._bound_files[name] = BoundFile(self, self._codepage, file_name_or_object, name)
        return self._bound_files[name]

    def unbind(self, name):
        """Unbind bound file."""
        if isinstance(name, text_type):
            name = self._codepage.unicode_to_bytes(name)
        del self._bound_files[name]

    def open(
            self, number, filespec, filetype, mode, access, lock,
            reclen, seg, offset, length, field
        ):
        """Open a file on the internal disk drive."""
        if filespec in self._bound_files:
            fhandle = self._bound_files[filespec].get_stream(filetype, mode)
            try:
                return self._create_file_object(fhandle, filetype, mode)
            except EnvironmentError as e:
                raise
                handle_oserror(e)
        else:
            return DiskDevice.open(
                self, number, filespec, filetype, mode, access, lock,
                reclen, seg, offset, length, field
            )

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
