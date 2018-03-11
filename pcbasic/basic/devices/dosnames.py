
import os
import re
import string
import sys
import ntpath

if sys.platform == 'win32':
    import ctypes
    from ctypes.wintypes import LPCWSTR, LPWSTR, DWORD

    _GetShortPathName = ctypes.windll.kernel32.GetShortPathNameW
    _GetShortPathName.argtypes = [LPCWSTR, LPWSTR, DWORD]

    def GetShortPathName(native_path):
        """Retrieve Windows short path name."""
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

from ..base import error


# allowable characters in DOS file name
# GW-BASIC also allows 0x7F and up, but replaces accented chars with unaccented
# based on CHCP code page, which may differ from display codepage in COUNTRY.SYS
# this is complex and leads to unpredictable results depending on host platform.
ALLOWABLE_CHARS = set(string.ascii_letters + string.digits + b" !#$%&'()-@^_`{}~")


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

def normalise_dosname(dos_name):
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

def is_legal_dosname(dos_name):
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
