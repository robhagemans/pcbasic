"""
PC-BASIC - error.py
Error constants and exceptions

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# error constants
NEXT_WITHOUT_FOR = 1
SYNTAX_ERROR = 2
RETURN_WITHOUT_GOSUB = 3
OUT_OF_DATA = 4
ILLEGAL_FUNCTION_CALL = 5
OVERFLOW = 6
OUT_OF_MEMORY = 7
UNDEFINED_LINE_NUMBER = 8
SUBSCRIPT_OUT_OF_RANGE = 9
DUPLICATE_DEFINITION = 10
DIVISION_BY_ZERO = 11
ILLEGAL_DIRECT = 12
TYPE_MISMATCH = 13
OUT_OF_STRING_SPACE = 14
STRING_TOO_LONG = 15
STRING_FORMULA_TOO_COMPLEX = 16
CANT_CONTINUE = 17
UNDEFINED_USER_FUNCTION = 18
NO_RESUME = 19
RESUME_WITHOUT_ERROR = 20
# 21
MISSING_OPERAND = 22
LINE_BUFFER_OVERFLOW = 23
DEVICE_TIMEOUT = 24
DEVICE_FAULT = 25
FOR_WITHOUT_NEXT = 26
OUT_OF_PAPER = 27
# 28
WHILE_WITHOUT_WEND = 29
WEND_WITHOUT_WHILE = 30
# 31--49
FIELD_OVERFLOW = 50
INTERNAL_ERROR = 51
BAD_FILE_NUMBER = 52
FILE_NOT_FOUND = 53
BAD_FILE_MODE = 54
FILE_ALREADY_OPEN = 55
# 56
DEVICE_IO_ERROR = 57
FILE_ALREADY_EXISTS = 58
# 59--60
DISK_FULL = 61
INPUT_PAST_END = 62
BAD_RECORD_NUMBER = 63
BAD_FILE_NAME = 64
# 65
DIRECT_STATEMENT_IN_FILE = 66
TOO_MANY_FILES = 67
DEVICE_UNAVAILABLE = 68
COMMUNICATION_BUFFER_OVERFLOW = 69
PERMISSION_DENIED = 70
DISK_NOT_READY = 71
DISK_MEDIA_ERROR = 72
ADVANCED_FEATURE = 73
RENAME_ACROSS_DISKS = 74
PATH_FILE_ACCESS_ERROR = 75
PATH_NOT_FOUND = 76
DEADLOCK = 77

# shorthand
STX = SYNTAX_ERROR
IFC = ILLEGAL_FUNCTION_CALL


class Interrupt(Exception):
    """Base type for exceptions."""

    message = b''

    def __repr__(self):
        """String representation of exception."""
        return self.message.decode('ascii', 'replace')

    def get_message(self, line_number=None):
        """Error message."""
        if line_number is not None and 0 <= line_number < 65535:
            return b'%s in %i\xFF\r' % (self.message, line_number)
        else:
            return b'%s\xFF\r' % (self.message,)


class Exit(Interrupt):
    """Exit emulator."""
    message = b'Exit'


class Reset(Exit):
    """Reset emulator."""
    message = b'Reset'


class Break(Interrupt):
    """Program interrupt."""

    message = b'Break'

    def __init__(self, stop=False, pos=None):
        """Initialise break."""
        Interrupt.__init__(self)
        self.stop = stop
        self.pos = pos
        self.trapped_error_num = None
        self.trapped_error_pos = None


class BASICError(Interrupt):
    """Runtime error."""

    default_message = b'Unprintable error'
    messages = {
        1: b'NEXT without FOR',
        2: b'Syntax error',
        3: b'RETURN without GOSUB',
        4: b'Out of DATA',
        5: b'Illegal function call',
        6: b'Overflow',
        7: b'Out of memory',
        8: b'Undefined line number',
        9: b'Subscript out of range',
        10: b'Duplicate Definition',
        11: b'Division by zero',
        12: b'Illegal direct',
        13: b'Type mismatch',
        14: b'Out of string space',
        15: b'String too long',
        16: b'String formula too complex',
        17: b"Can't continue",
        18: b'Undefined user function',
        19: b'No RESUME',
        20: b'RESUME without error',
        # 21
        22: b'Missing operand',
        23: b'Line buffer overflow',
        24: b'Device Timeout',
        25: b'Device Fault',
        26: b'FOR without NEXT',
        27: b'Out of paper',
        # 28
        29: b'WHILE without WEND',
        30: b'WEND without WHILE',
        # 31--49
        50: b'FIELD overflow',
        51: b'Internal error',
        52: b'Bad file number',
        53: b'File not found',
        54: b'Bad file mode',
        55: b'File already open',
        # 56
        57: b'Device I/O error',
        58: b'File already exists',
        # 59--60
        61: b'Disk full',
        62: b'Input past end',
        63: b'Bad record number',
        64: b'Bad file name',
        # 65
        66: b'Direct statement in file',
        67: b'Too many files',
        68: b'Device Unavailable',
        69: b'Communication buffer overflow',
        70: b'Permission Denied',
        71: b'Disk not Ready',
        72: b'Disk media error',
        73: b'Advanced Feature',
        74: b'Rename across disks',
        75: b'Path/File access error',
        76: b'Path not found',
        77: b'Deadlock',
    }

    def __init__(self, value, pos=None):
        """Initialise error."""
        Interrupt.__init__(self)
        self.err = value
        self.pos = pos
        try:
            self.message = self.messages[self.err]
        except KeyError:
            self.message = self.default_message


def range_check(lower, upper, *allvars):
    """Check if all variables in list are within the given inclusive range."""
    for v in allvars:
        if v is not None and not (lower <= v <= upper):
            raise BASICError(IFC)

def throw_if(bool, err=IFC):
    """Raise IFC if condition is met."""
    if bool:
        raise BASICError(err)

def range_check_err(lower, upper, v, err=IFC):
    """Check if variable is within the given inclusive range."""
    if v is not None and not (lower <= v <= upper):
        raise BASICError(err)
