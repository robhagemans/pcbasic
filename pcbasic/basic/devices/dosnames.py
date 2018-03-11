
import os
import re
import string
import sys
import ntpath

from ..base import error


# allowable characters in DOS file name
# GW-BASIC also allows 0x7F and up, but replaces accented chars with unaccented
# based on CHCP code page, which may differ from display codepage in COUNTRY.SYS
# this is complex and leads to unpredictable results depending on host platform.
ALLOWABLE_CHARS = set(string.ascii_letters + string.digits + b" !#$%&'()-@^_`{}~")


##############################################################################
# DOS name translation

class NameConverter(object):
    """Converter between (bytes) DOS names and (unicode) native filenames."""

    def __init__(self, codepage):
        """Initialise converter."""
        self._codepage = codepage

    def get_native_name(self, native_path, dos_name, defext, isdir, create):
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
        norm_name = normalise_dosname(dos_name)
        # check for non-legal characters & spaces (but clip off overlong names)
        if not is_legal_dosname(norm_name):
            raise error.BASICError(error.BAD_FILE_NAME)
        fullname = match_dosname(native_path, norm_name, isdir)
        if fullname:
            return fullname
        # not found
        if create:
            # create a new filename
            return norm_name.decode(b'ascii')
        else:
            raise error.BASICError(name_err)

    def get_dos_display_name(self, native_dirpath, native_name):
        """Convert native name to short name or (not normalised or even legal) dos-style name."""
        native_path = os.path.join(native_dirpath, native_name)
        # get the short name if it exists, keep long name otherwise
        if sys.platform == 'win32':
            try:
                native_path = win32api.GetShortPathName(native_path)
            except Exception:
                # something went wrong - keep long name (happens for swap file or non-Windows)
                # this should be a WindowsError which is an OSError
                # but it often is a pywintypes.error
                pass
        native_name = os.path.basename(native_path)
        # see if we have a legal dos name that matches
        try:
            ascii_name = native_name.encode('ascii')
        except UnicodeEncodeError:
            pass
        else:
            if is_legal_dosname(ascii_name):
                return normalise_dosname(ascii_name)
        # convert to codepage
        cp_name = self._codepage.str_from_unicode(native_name)
        # clip overlong & mark as shortened
        trunk, ext_inc_dot = ntpath.splitext(cp_name)
        if len(trunk) > 8:
            trunk = trunk[:7] + b'+'
        if len(ext_inc_dot) > 4:
            ext_inc_dot = ext_inc_dot[:3] + b'+'
        return trunk + ext_inc_dot

    def filter_names(self, native_dirpath, native_names, dos_mask):
        """Apply case-insensitive filename filter to display names."""
        dos_mask = dos_mask or b'*.*'
        trunkmask, extmask = dos_splitext(dos_mask)
        all_files = (self.get_dos_display_name(native_dirpath, name) for name in native_names)
        split = [dos_splitext(dos_name) for dos_name in all_files]
        return sorted(
                (trunk, ext) for (trunk, ext) in split
                if (match_wildcard(trunk, trunkmask) and match_wildcard(ext, extmask) and
                        # this matches . and ..
                        (trunk or not ext or ext == b'.')
                )
            )


def dos_splitext(dos_name):
    """Return trunk and extension excluding the dot."""
    trunk, ext = ntpath.splitext(dos_name)
    # ntpath.splitext includes the leading dot
    if ext.startswith(b'.'):
        ext = ext[1:]
    return trunk, ext

def normalise_dosname(dos_name):
    """Convert dosname into bytes uppercase 8.3."""
    # a normalised DOS-name is all-uppercase, no leading or trailing spaces, and
    # 1) . or ..; or
    # 2) 1--8 allowable characters followed by one dot followed by 1--3 characters; or
    # 3) 1--8 allowable characters with no dots
    #
    # don't try to split special directory names
    if dos_name in (b'.', b'..'):
        return dos_name
    # convert to all uppercase
    dos_name = dos_name.upper()
    # take whatever comes after first dot as extension
    # and whatever comes before first dot as trunk
    elements = dos_name.split(b'.', 1)
    if len(elements) == 1:
        trunk, ext = elements[0], ''
    else:
        trunk, ext = elements
    # truncate to 8.3
    trunk, ext = trunk[:8], ext[:3]
    if ext:
        ext = b'.' + ext
    norm_name = trunk + ext
    return norm_name

def is_legal_dosname(dos_name):
    """Check if a (bytes) name is a legal DOS name."""
    if dos_name in (b'.', b'..'):
        return True
    trunk, ext = dos_splitext(dos_name)
    return (
            # enforce lengths
            (trunk and len(trunk) <= 8 and len(ext) <= 3) and
            # no leading or trailing spaces
            (trunk == trunk.strip() and ext == ext.strip()) and
            # enforce allowable characters
            ((set(trunk) | set(ext)) <= ALLOWABLE_CHARS)
        )

def match_dosname(native_path, dosname, isdir):
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
        if is_legal_dosname(ascii_name):
            try_name = normalise_dosname(ascii_name)
            if try_name == dosname and istype(native_path, f, isdir):
                return f
    return None

def join_dosname(trunk, ext, padding=False):
    """Join trunk and extension into (bytes) file name."""
    if ext or not trunk:
        ext = b'.' + ext
    if padding:
        return trunk.ljust(8) + ext.ljust(4)
    else:
        return trunk + ext

def match_wildcard(name, mask):
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
# native path operations

def istype(native_path, native_name, isdir):
    """Return whether a file exists and is a directory or regular."""
    name = os.path.join(native_path, native_name)
    try:
        return os.path.isdir(name) if isdir else os.path.isfile(name)
    except TypeError:
        # happens for name == u'\0'
        return False
