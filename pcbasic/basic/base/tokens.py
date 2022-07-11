"""
PC-BASIC - tokens.py
BASIC keyword tokens

(c) 2014--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ...compat import iteritems


# ascii constants in bytes form
# note that strings module equivanets are unicode in python 3
DIGITS = b'0123456789'
UPPERCASE = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWERCASE = UPPERCASE.lower()
LETTERS = UPPERCASE + LOWERCASE
ALPHANUMERIC = LETTERS + DIGITS
HEXDIGITS = DIGITS + b'abcdefABCDEF'
OCTDIGITS = b'01234567'


# allowable as chars 2.. in a variable name (first char must be a letter)
NAME_CHARS = ALPHANUMERIC + b'.'
# type characters
SIGILS = (b'#', b'!', b'%', b'$')

# indirect line number references
T_UINT_PROC = b'\x0d'
T_UINT = b'\x0e'
# number type tokens
T_OCT = b'\x0b'
T_HEX = b'\x0c'
T_BYTE = b'\x0f'
T_INT = b'\x1c'
T_SINGLE = b'\x1d'
T_DOUBLE = b'\x1f'
# number constants
C_0 = b'\x11'
C_1 = b'\x12'
C_2 = b'\x13'
C_3 = b'\x14'
C_4 = b'\x15'
C_5 = b'\x16'
C_6 = b'\x17'
C_7 = b'\x18'
C_8 = b'\x19'
C_9 = b'\x1a'
C_10 = b'\x1b'
# keyword tokens recognised by PC-BASIC
END = b'\x81'
FOR = b'\x82'
NEXT = b'\x83'
DATA = b'\x84'
INPUT = b'\x85'
DIM = b'\x86'
READ = b'\x87'
LET = b'\x88'
GOTO = b'\x89'
RUN = b'\x8a'
IF = b'\x8b'
RESTORE = b'\x8c'
GOSUB = b'\x8d'
RETURN = b'\x8e'
REM = b'\x8f'
STOP = b'\x90'
PRINT = b'\x91'
CLEAR = b'\x92'
LIST = b'\x93'
NEW = b'\x94'
ON = b'\x95'
WAIT = b'\x96'
DEF = b'\x97'
POKE = b'\x98'
CONT = b'\x99'
OUT = b'\x9c'
LPRINT = b'\x9d'
LLIST = b'\x9e'
WIDTH = b'\xa0'
ELSE = b'\xa1'
TRON = b'\xa2'
TROFF = b'\xa3'
SWAP = b'\xa4'
ERASE = b'\xa5'
EDIT = b'\xa6'
ERROR = b'\xa7'
RESUME = b'\xa8'
DELETE = b'\xa9'
AUTO = b'\xaa'
RENUM = b'\xab'
DEFSTR = b'\xac'
DEFINT = b'\xad'
DEFSNG = b'\xae'
DEFDBL = b'\xaf'
LINE = b'\xb0'
WHILE = b'\xb1'
WEND = b'\xb2'
CALL = b'\xb3'
WRITE = b'\xb7'
OPTION = b'\xb8'
RANDOMIZE = b'\xb9'
OPEN = b'\xba'
CLOSE = b'\xbb'
LOAD = b'\xbc'
MERGE = b'\xbd'
SAVE = b'\xbe'
COLOR = b'\xbf'
CLS = b'\xc0'
MOTOR = b'\xc1'
BSAVE = b'\xc2'
BLOAD = b'\xc3'
SOUND = b'\xc4'
BEEP = b'\xc5'
PSET = b'\xc6'
PRESET = b'\xc7'
SCREEN = b'\xc8'
KEY = b'\xc9'
LOCATE = b'\xca'
TO = b'\xcc'
THEN = b'\xcd'
TAB = b'\xce'
STEP = b'\xcf'
USR = b'\xd0'
FN = b'\xd1'
SPC = b'\xd2'
NOT = b'\xd3'
ERL = b'\xd4'
ERR = b'\xd5'
STRING = b'\xd6'
USING = b'\xd7'
INSTR = b'\xd8'
O_REM = b'\xd9'
VARPTR = b'\xda'
CSRLIN = b'\xdb'
POINT = b'\xdc'
OFF = b'\xdd'
INKEY = b'\xde'
O_GT = b'\xe6'
O_EQ = b'\xe7'
O_LT = b'\xe8'
O_PLUS = b'\xe9'
O_MINUS = b'\xea'
O_TIMES = b'\xeb'
O_DIV = b'\xec'
O_CARET = b'\xed'
AND = b'\xee'
OR = b'\xef'
XOR = b'\xf0'
EQV = b'\xf1'
IMP = b'\xf2'
MOD = b'\xf3'
O_INTDIV = b'\xf4'
CVI = b'\xfd\x81'
CVS = b'\xfd\x82'
CVD = b'\xfd\x83'
MKI = b'\xfd\x84'
MKS = b'\xfd\x85'
MKD = b'\xfd\x86'
EXTERR = b'\xfd\x8b'
FILES = b'\xfe\x81'
FIELD = b'\xfe\x82'
SYSTEM = b'\xfe\x83'
NAME = b'\xfe\x84'
LSET = b'\xfe\x85'
RSET = b'\xfe\x86'
KILL = b'\xfe\x87'
PUT = b'\xfe\x88'
GET = b'\xfe\x89'
RESET = b'\xfe\x8a'
COMMON = b'\xfe\x8b'
CHAIN = b'\xfe\x8c'
DATE = b'\xfe\x8d'
TIME = b'\xfe\x8e'
PAINT = b'\xfe\x8f'
COM = b'\xfe\x90'
CIRCLE = b'\xfe\x91'
DRAW = b'\xfe\x92'
PLAY = b'\xfe\x93'
TIMER = b'\xfe\x94'
ERDEV = b'\xfe\x95'
IOCTL = b'\xfe\x96'
CHDIR = b'\xfe\x97'
MKDIR = b'\xfe\x98'
RMDIR = b'\xfe\x99'
SHELL = b'\xfe\x9a'
ENVIRON = b'\xfe\x9b'
VIEW = b'\xfe\x9c'
WINDOW = b'\xfe\x9d'
PMAP = b'\xfe\x9e'
PALETTE = b'\xfe\x9f'
LCOPY = b'\xfe\xa0'
CALLS = b'\xfe\xa1'
PCOPY = b'\xfe\xa5'
LOCK = b'\xfe\xa7'
UNLOCK = b'\xfe\xa8'
LEFT = b'\xff\x81'
RIGHT = b'\xff\x82'
MID = b'\xff\x83'
SGN = b'\xff\x84'
INT = b'\xff\x85'
ABS = b'\xff\x86'
SQR = b'\xff\x87'
RND = b'\xff\x88'
SIN = b'\xff\x89'
LOG = b'\xff\x8a'
EXP = b'\xff\x8b'
COS = b'\xff\x8c'
TAN = b'\xff\x8d'
ATN = b'\xff\x8e'
FRE = b'\xff\x8f'
INP = b'\xff\x90'
POS = b'\xff\x91'
LEN = b'\xff\x92'
STR = b'\xff\x93'
VAL = b'\xff\x94'
ASC = b'\xff\x95'
CHR = b'\xff\x96'
PEEK = b'\xff\x97'
SPACE = b'\xff\x98'
OCT = b'\xff\x99'
HEX = b'\xff\x9a'
LPOS = b'\xff\x9b'
CINT = b'\xff\x9c'
CSNG = b'\xff\x9d'
CDBL = b'\xff\x9e'
FIX = b'\xff\x9f'
PEN = b'\xff\xa0'
STICK = b'\xff\xa1'
STRIG = b'\xff\xa2'
EOF = b'\xff\xa3'
LOC = b'\xff\xa4'
LOF = b'\xff\xa5'
# PCjr and Tandy only
NOISE = b'\xfe\xa4'
TERM = b'\xfe\xa6'

KW_END = b'END'
KW_FOR = b'FOR'
KW_NEXT = b'NEXT'
KW_DATA = b'DATA'
KW_INPUT = b'INPUT'
KW_DIM = b'DIM'
KW_READ = b'READ'
KW_LET = b'LET'
KW_GOTO = b'GOTO'
KW_RUN = b'RUN'
KW_IF = b'IF'
KW_RESTORE = b'RESTORE'
KW_GOSUB = b'GOSUB'
KW_RETURN = b'RETURN'
KW_REM = b'REM'
KW_STOP = b'STOP'
KW_PRINT = b'PRINT'
KW_CLEAR = b'CLEAR'
KW_LIST = b'LIST'
KW_NEW = b'NEW'
KW_ON = b'ON'
KW_WAIT = b'WAIT'
KW_DEF = b'DEF'
KW_POKE = b'POKE'
KW_CONT = b'CONT'
KW_OUT = b'OUT'
KW_LPRINT = b'LPRINT'
KW_LLIST = b'LLIST'
KW_WIDTH = b'WIDTH'
KW_ELSE = b'ELSE'
KW_TRON = b'TRON'
KW_TROFF = b'TROFF'
KW_SWAP = b'SWAP'
KW_ERASE = b'ERASE'
KW_EDIT = b'EDIT'
KW_ERROR = b'ERROR'
KW_RESUME = b'RESUME'
KW_DELETE = b'DELETE'
KW_AUTO = b'AUTO'
KW_RENUM = b'RENUM'
KW_DEFSTR = b'DEFSTR'
KW_DEFINT = b'DEFINT'
KW_DEFSNG = b'DEFSNG'
KW_DEFDBL = b'DEFDBL'
KW_LINE = b'LINE'
KW_WHILE = b'WHILE'
KW_WEND = b'WEND'
KW_CALL = b'CALL'
KW_WRITE = b'WRITE'
KW_OPTION = b'OPTION'
KW_RANDOMIZE = b'RANDOMIZE'
KW_OPEN = b'OPEN'
KW_CLOSE = b'CLOSE'
KW_LOAD = b'LOAD'
KW_MERGE = b'MERGE'
KW_SAVE = b'SAVE'
KW_COLOR = b'COLOR'
KW_CLS = b'CLS'
KW_MOTOR = b'MOTOR'
KW_BSAVE = b'BSAVE'
KW_BLOAD = b'BLOAD'
KW_SOUND = b'SOUND'
KW_BEEP = b'BEEP'
KW_PSET = b'PSET'
KW_PRESET = b'PRESET'
KW_SCREEN = b'SCREEN'
KW_KEY = b'KEY'
KW_LOCATE = b'LOCATE'
KW_TO = b'TO'
KW_THEN = b'THEN'
KW_TAB = b'TAB('
KW_STEP = b'STEP'
KW_USR = b'USR'
KW_FN = b'FN'
KW_SPC = b'SPC('
KW_NOT = b'NOT'
KW_ERL = b'ERL'
KW_ERR = b'ERR'
KW_STRING = b'STRING$'
KW_USING = b'USING'
KW_INSTR = b'INSTR'
KW_O_REM = b"'"
KW_VARPTR = b'VARPTR'
KW_CSRLIN = b'CSRLIN'
KW_POINT = b'POINT'
KW_OFF = b'OFF'
KW_INKEY = b'INKEY$'
KW_O_GT = b'>'
KW_O_EQ = b'='
KW_O_LT = b'<'
KW_O_PLUS = b'+'
KW_O_MINUS = b'-'
KW_O_TIMES = b'*'
KW_O_DIV = b'/'
KW_O_CARET = b'^'
KW_AND = b'AND'
KW_OR = b'OR'
KW_XOR = b'XOR'
KW_EQV = b'EQV'
KW_IMP = b'IMP'
KW_MOD = b'MOD'
KW_O_INTDIV = b'\\'
KW_CVI = b'CVI'
KW_CVS = b'CVS'
KW_CVD = b'CVD'
KW_MKI = b'MKI$'
KW_MKS = b'MKS$'
KW_MKD = b'MKD$'
KW_EXTERR = b'EXTERR'
KW_FILES = b'FILES'
KW_FIELD = b'FIELD'
KW_SYSTEM = b'SYSTEM'
KW_NAME = b'NAME'
KW_LSET = b'LSET'
KW_RSET = b'RSET'
KW_KILL = b'KILL'
KW_PUT = b'PUT'
KW_GET = b'GET'
KW_RESET = b'RESET'
KW_COMMON = b'COMMON'
KW_CHAIN = b'CHAIN'
KW_DATE = b'DATE$'
KW_TIME = b'TIME$'
KW_PAINT = b'PAINT'
KW_COM = b'COM'
KW_CIRCLE = b'CIRCLE'
KW_DRAW = b'DRAW'
KW_PLAY = b'PLAY'
KW_TIMER = b'TIMER'
KW_ERDEV = b'ERDEV'
KW_IOCTL = b'IOCTL'
KW_CHDIR = b'CHDIR'
KW_MKDIR = b'MKDIR'
KW_RMDIR = b'RMDIR'
KW_SHELL = b'SHELL'
KW_ENVIRON = b'ENVIRON'
KW_VIEW = b'VIEW'
KW_WINDOW = b'WINDOW'
KW_PMAP = b'PMAP'
KW_PALETTE = b'PALETTE'
KW_LCOPY = b'LCOPY'
KW_CALLS = b'CALLS'
KW_PCOPY = b'PCOPY'
KW_LOCK = b'LOCK'
KW_UNLOCK = b'UNLOCK'
KW_LEFT = b'LEFT$'
KW_RIGHT = b'RIGHT$'
KW_MID = b'MID$'
KW_SGN = b'SGN'
KW_INT = b'INT'
KW_ABS = b'ABS'
KW_SQR = b'SQR'
KW_RND = b'RND'
KW_SIN = b'SIN'
KW_LOG = b'LOG'
KW_EXP = b'EXP'
KW_COS = b'COS'
KW_TAN = b'TAN'
KW_ATN = b'ATN'
KW_FRE = b'FRE'
KW_INP = b'INP'
KW_POS = b'POS'
KW_LEN = b'LEN'
KW_STR = b'STR$'
KW_VAL = b'VAL'
KW_ASC = b'ASC'
KW_CHR = b'CHR$'
KW_PEEK = b'PEEK'
KW_SPACE = b'SPACE$'
KW_OCT = b'OCT$'
KW_HEX = b'HEX$'
KW_LPOS = b'LPOS'
KW_CINT = b'CINT'
KW_CSNG = b'CSNG'
KW_CDBL = b'CDBL'
KW_FIX = b'FIX'
KW_PEN = b'PEN'
KW_STICK = b'STICK'
KW_STRIG = b'STRIG'
KW_EOF = b'EOF'
KW_LOC = b'LOC'
KW_LOF = b'LOF'

KW_NOISE = b'NOISE'
KW_TERM = b'TERM'

# non-keywords that appear as syntax elements
W_AS = b'AS'
W_SHARED = b'SHARED'
W_ACCESS = b'ACCESS'
W_RANDOM = b'RANDOM'
W_OUTPUT = b'OUTPUT'
W_APPEND = b'APPEND'
W_BASE = b'BASE'
W_SEG = b'SEG'
W_ALL = b'ALL'

# other keywords on http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html :
# Sperry PC only:
#   0xFEA4: b'DEBUG' (conflicts with PCjr/Tandy NOISE)
# Undefined tokens:
#   0x9A,  0x9B,  0x9F,  0xB4,  0xB5,  0xB6,  0xCB,  0xDF,  0xE0,  0xE1,  0xE2
#   0xE3,  0xE4,  0xE5,  0xF5,  0xF6,  0xF7,  0xF8,  0xF9,  0xFA,  0xFB,  0xFC
DIGIT = (C_0, C_1, C_2, C_3, C_4, C_5, C_6, C_7, C_8, C_9)
NUMBER = (
    T_OCT, T_HEX, T_BYTE, T_INT, T_SINGLE, T_DOUBLE,
    C_0, C_1, C_2, C_3, C_4, C_5, C_6, C_7, C_8, C_9, C_10
)
LINE_NUMBER = (T_UINT, T_UINT_PROC)
OPERATOR = (
    O_GT, O_EQ, O_LT, O_PLUS, O_MINUS,
    O_TIMES, O_DIV, O_CARET, O_INTDIV
)
# comment tokens
COMMENT = (O_REM, REM)

# line ending tokens
END_LINE = (b'\0', b'')
# statement ending tokens
END_STATEMENT = END_LINE + (b':',)
# expression ending tokens
END_EXPRESSION = END_STATEMENT + (b')', b']', b',', b';')
## tokens followed by one or more bytes to be skipped
PLUS_BYTES = {
    T_BYTE: 1, b'\xff': 1 , b'\xfe': 1, b'\xfd': 1, T_OCT: 2, T_HEX: 2,
    T_UINT_PROC: 2, T_UINT: 2, T_INT: 2, T_SINGLE: 4, T_DOUBLE: 8, b'\0': 4
}

# keyword dictionary
KEYWORDS = {
    END: KW_END, FOR: KW_FOR, NEXT: KW_NEXT, DATA: KW_DATA, INPUT: KW_INPUT,
    DIM: KW_DIM, READ: KW_READ, LET: KW_LET, GOTO: KW_GOTO, RUN: KW_RUN, IF: KW_IF,
    RESTORE: KW_RESTORE, GOSUB: KW_GOSUB, RETURN: KW_RETURN, REM: KW_REM,
    STOP: KW_STOP, PRINT: KW_PRINT, CLEAR: KW_CLEAR, LIST: KW_LIST, NEW: KW_NEW,
    ON: KW_ON, WAIT: KW_WAIT, DEF: KW_DEF, POKE: KW_POKE, CONT: KW_CONT, OUT: KW_OUT,
    LPRINT: KW_LPRINT, LLIST: KW_LLIST, WIDTH: KW_WIDTH, ELSE: KW_ELSE,
    TRON: KW_TRON, TROFF: KW_TROFF, SWAP: KW_SWAP, ERASE: KW_ERASE, EDIT: KW_EDIT,
    ERROR: KW_ERROR, RESUME: KW_RESUME, DELETE: KW_DELETE, AUTO: KW_AUTO,
    RENUM: KW_RENUM, DEFSTR: KW_DEFSTR, DEFINT: KW_DEFINT, DEFSNG: KW_DEFSNG,
    DEFDBL: KW_DEFDBL, LINE: KW_LINE, WHILE: KW_WHILE, WEND: KW_WEND, CALL: KW_CALL,
    WRITE: KW_WRITE, OPTION: KW_OPTION, RANDOMIZE: KW_RANDOMIZE, OPEN: KW_OPEN,
    CLOSE: KW_CLOSE, LOAD: KW_LOAD, MERGE: KW_MERGE, SAVE: KW_SAVE, COLOR: KW_COLOR,
    CLS: KW_CLS, MOTOR: KW_MOTOR, BSAVE: KW_BSAVE, BLOAD: KW_BLOAD, SOUND: KW_SOUND,
    BEEP: KW_BEEP, PSET: KW_PSET, PRESET: KW_PRESET, SCREEN: KW_SCREEN, KEY: KW_KEY,
    LOCATE: KW_LOCATE, TO: KW_TO, THEN: KW_THEN, TAB: KW_TAB, STEP: KW_STEP,
    USR: KW_USR, FN: KW_FN, SPC: KW_SPC, NOT: KW_NOT, ERL: KW_ERL, ERR: KW_ERR,
    STRING: KW_STRING, USING: KW_USING, INSTR: KW_INSTR, O_REM: KW_O_REM,
    VARPTR: KW_VARPTR, CSRLIN: KW_CSRLIN, POINT: KW_POINT, OFF: KW_OFF,
    INKEY: KW_INKEY, O_GT: KW_O_GT, O_EQ: KW_O_EQ, O_LT: KW_O_LT,
    O_PLUS: KW_O_PLUS, O_MINUS: KW_O_MINUS, O_TIMES: KW_O_TIMES, O_DIV: KW_O_DIV,
    O_CARET: KW_O_CARET, AND: KW_AND, OR: KW_OR, XOR: KW_XOR, EQV: KW_EQV, IMP: KW_IMP,
    MOD: KW_MOD, O_INTDIV: KW_O_INTDIV, CVI: KW_CVI, CVS: KW_CVS, CVD: KW_CVD, MKI: KW_MKI,
    MKS: KW_MKS, MKD: KW_MKD, EXTERR: KW_EXTERR, FILES: KW_FILES, FIELD: KW_FIELD,
    SYSTEM: KW_SYSTEM, NAME: KW_NAME, LSET: KW_LSET, RSET: KW_RSET, KILL: KW_KILL,
    PUT: KW_PUT, GET: KW_GET, RESET: KW_RESET, COMMON: KW_COMMON, CHAIN: KW_CHAIN,
    DATE: KW_DATE, TIME: KW_TIME, PAINT: KW_PAINT, COM: KW_COM, CIRCLE: KW_CIRCLE,
    DRAW: KW_DRAW, PLAY: KW_PLAY, TIMER: KW_TIMER, ERDEV: KW_ERDEV, IOCTL: KW_IOCTL,
    CHDIR: KW_CHDIR, MKDIR: KW_MKDIR, RMDIR: KW_RMDIR, SHELL: KW_SHELL,
    ENVIRON: KW_ENVIRON, VIEW: KW_VIEW, WINDOW: KW_WINDOW, PMAP: KW_PMAP,
    PALETTE: KW_PALETTE, LCOPY: KW_LCOPY, CALLS: KW_CALLS, PCOPY: KW_PCOPY,
    LOCK: KW_LOCK, UNLOCK: KW_UNLOCK, LEFT: KW_LEFT, RIGHT: KW_RIGHT, MID: KW_MID,
    SGN: KW_SGN, INT: KW_INT, ABS: KW_ABS, SQR: KW_SQR, RND: KW_RND, SIN: KW_SIN,
    LOG: KW_LOG, EXP: KW_EXP, COS: KW_COS, TAN: KW_TAN, ATN: KW_ATN, FRE: KW_FRE,
    INP: KW_INP, POS: KW_POS, LEN: KW_LEN, STR: KW_STR, VAL: KW_VAL, ASC: KW_ASC,
    CHR: KW_CHR, PEEK: KW_PEEK, SPACE: KW_SPACE, OCT: KW_OCT, HEX: KW_HEX,
    LPOS: KW_LPOS, CINT: KW_CINT, CSNG: KW_CSNG, CDBL: KW_CDBL, FIX: KW_FIX,
    PEN: KW_PEN, STICK: KW_STICK, STRIG: KW_STRIG, EOF: KW_EOF, LOC: KW_LOC,
    LOF: KW_LOF,
}


class TokenKeywordDict(object):
    """Token to keyword conversion for given BASIC syntax."""

    def __init__(self, syntax):
        """Build dictionaries."""
        self.to_keyword = dict(KEYWORDS)
        if syntax in ('pcjr', 'tandy'):
            # pcjr, tandy; incompatible with Sperry PC.
            self.to_keyword[NOISE] = KW_NOISE
            self.to_keyword[TERM] = KW_TERM
        self.to_token = dict((reversed(item) for item in iteritems(self.to_keyword)))
