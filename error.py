"""
PC-BASIC - error.py
Error handling

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import state

# number and line number of last error
state.basic_state.errn = -1
state.basic_state.errp = -1

# jump line number
state.basic_state.on_error = None
state.basic_state.error_handle_mode = False
state.basic_state.error_resume = None

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

default_msg = 'Unprintable error'
errors = {
    1: 'NEXT without FOR',
    2: 'Syntax error',
    3: 'RETURN without GOSUB',
    4: 'Out of DATA',
    5: 'Illegal function call',
    6: 'Overflow',
    7: 'Out of memory',
    8: 'Undefined line number',
    9: 'Subscript out of range',
    10: 'Duplicate Definition',
    11: 'Division by zero',
    12: 'Illegal direct',
    13: 'Type mismatch',
    14: 'Out of string space',
    15: 'String too long',
    16: 'String formula too complex',
    17: "Can't continue",
    18: 'Undefined user function',
    19: 'No RESUME',
    20: 'RESUME without error',
    # 21
    22: 'Missing operand',
    23: 'Line buffer overflow',
    24: 'Device Timeout',
    25: 'Device Fault',
    26: 'FOR without NEXT',
    27: 'Out of paper',
    # 28
    29: 'WHILE without WEND',
    30: 'WEND without WHILE',
    # 31--49
    50: 'FIELD overflow',
    51: 'Internal error',
    52: 'Bad file number',
    53: 'File not found',
    54: 'Bad file mode',
    55: 'File already open',
    # 56
    57: 'Device I/O error',
    58: 'File already exists',
    # 59--60
    61: 'Disk full',
    62: 'Input past end',
    63: 'Bad record number',
    64: 'Bad file name',
    # 65
    66: 'Direct statement in file',
    67: 'Too many files',
    68: 'Device Unavailable',
    69: 'Communication buffer overflow',
    70: 'Permission Denied',
    71: 'Disk not Ready',
    72: 'Disk media error',
    73: 'Advanced Feature',
    74: 'Rename across disks',
    75: 'Path/File access error',
    76: 'Path not found',
    77: 'Deadlock',
}


class Error(Exception):
    """ Base type for exceptions. """
    pass

class Break(Error):
    """ Program interrupt. """
    def __init__(self, stop=False):
        Error.__init__(self)
        if not state.basic_state.run_mode:
            self.pos = -1
        else:
            self.pos = state.basic_state.current_statement
        self.stop = stop

class Reset(Error):
    """ Reset emulator. """
    def __init__(self):
        Error.__init__(self)

class Exit(Error):
    """ Exit emulator. """
    def __init__(self):
        Error.__init__(self)

class RunError(Error):
    """ Runtime error. """
    def __init__(self, value, pos=-1):
        Error.__init__(self)
        self.err = value
        if not state.basic_state.run_mode or pos != -1:
            self.pos = pos
        else:
            self.pos = state.basic_state.current_statement

def set_err(e):
    """ Set the ERR and ERL values. """
    # set ERR and ERL
    state.basic_state.errn = e.err
    state.basic_state.errp = e.pos

def get_message(errnum):
    """ Get error message for error code. """
    try:
        return errors[errnum]
    except KeyError:
        return default_msg
