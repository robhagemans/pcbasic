"""
PC-BASIC - tokens.py
BASIC keyword tokens

(c) 2014--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string

# allowable as chars 2.. in a variable name (first char must be a letter)
NAME_CHARS = tuple(string.ascii_letters + string.digits + '.')
# type characters
SIGILS = ('#', '!', '%', '$')

# indirect line number references
T_UINT_PROC = '\x0d'
T_UINT = '\x0e'
# number type tokens
T_OCT = '\x0b'
T_HEX = '\x0c'
T_BYTE = '\x0f'
T_INT = '\x1c'
T_SINGLE = '\x1d'
T_DOUBLE = '\x1f'
# number constants
C_0 = '\x11'
C_1 = '\x12'
C_2 = '\x13'
C_3 = '\x14'
C_4 = '\x15'
C_5 = '\x16'
C_6 = '\x17'
C_7 = '\x18'
C_8 = '\x19'
C_9 = '\x1a'
C_10 = '\x1b'
# keyword tokens recognised by PC-BASIC
END = '\x81'
FOR = '\x82'
NEXT = '\x83'
DATA = '\x84'
INPUT = '\x85'
DIM = '\x86'
READ = '\x87'
LET = '\x88'
GOTO = '\x89'
RUN = '\x8a'
IF = '\x8b'
RESTORE = '\x8c'
GOSUB = '\x8d'
RETURN = '\x8e'
REM = '\x8f'
STOP = '\x90'
PRINT = '\x91'
CLEAR = '\x92'
LIST = '\x93'
NEW = '\x94'
ON = '\x95'
WAIT = '\x96'
DEF = '\x97'
POKE = '\x98'
CONT = '\x99'
OUT = '\x9c'
LPRINT = '\x9d'
LLIST = '\x9e'
WIDTH = '\xa0'
ELSE = '\xa1'
TRON = '\xa2'
TROFF = '\xa3'
SWAP = '\xa4'
ERASE = '\xa5'
EDIT = '\xa6'
ERROR = '\xa7'
RESUME = '\xa8'
DELETE = '\xa9'
AUTO = '\xaa'
RENUM = '\xab'
DEFSTR = '\xac'
DEFINT = '\xad'
DEFSNG = '\xae'
DEFDBL = '\xaf'
LINE = '\xb0'
WHILE = '\xb1'
WEND = '\xb2'
CALL = '\xb3'
WRITE = '\xb7'
OPTION = '\xb8'
RANDOMIZE = '\xb9'
OPEN = '\xba'
CLOSE = '\xbb'
LOAD = '\xbc'
MERGE = '\xbd'
SAVE = '\xbe'
COLOR = '\xbf'
CLS = '\xc0'
MOTOR = '\xc1'
BSAVE = '\xc2'
BLOAD = '\xc3'
SOUND = '\xc4'
BEEP = '\xc5'
PSET = '\xc6'
PRESET = '\xc7'
SCREEN = '\xc8'
KEY = '\xc9'
LOCATE = '\xca'
TO = '\xcc'
THEN = '\xcd'
TAB = '\xce'
STEP = '\xcf'
USR = '\xd0'
FN = '\xd1'
SPC = '\xd2'
NOT = '\xd3'
ERL = '\xd4'
ERR = '\xd5'
STRING = '\xd6'
USING = '\xd7'
INSTR = '\xd8'
O_REM = '\xd9'
VARPTR = '\xda'
CSRLIN = '\xdb'
POINT = '\xdc'
OFF = '\xdd'
INKEY = '\xde'
O_GT = '\xe6'
O_EQ = '\xe7'
O_LT = '\xe8'
O_PLUS = '\xe9'
O_MINUS = '\xea'
O_TIMES = '\xeb'
O_DIV = '\xec'
O_CARET = '\xed'
AND = '\xee'
OR = '\xef'
XOR = '\xf0'
EQV = '\xf1'
IMP = '\xf2'
MOD = '\xf3'
O_INTDIV = '\xf4'
CVI = '\xfd\x81'
CVS = '\xfd\x82'
CVD = '\xfd\x83'
MKI = '\xfd\x84'
MKS = '\xfd\x85'
MKD = '\xfd\x86'
EXTERR = '\xfd\x8b'
FILES = '\xfe\x81'
FIELD = '\xfe\x82'
SYSTEM = '\xfe\x83'
NAME = '\xfe\x84'
LSET = '\xfe\x85'
RSET = '\xfe\x86'
KILL = '\xfe\x87'
PUT = '\xfe\x88'
GET = '\xfe\x89'
RESET = '\xfe\x8a'
COMMON = '\xfe\x8b'
CHAIN = '\xfe\x8c'
DATE = '\xfe\x8d'
TIME = '\xfe\x8e'
PAINT = '\xfe\x8f'
COM = '\xfe\x90'
CIRCLE = '\xfe\x91'
DRAW = '\xfe\x92'
PLAY = '\xfe\x93'
TIMER = '\xfe\x94'
ERDEV = '\xfe\x95'
IOCTL = '\xfe\x96'
CHDIR = '\xfe\x97'
MKDIR = '\xfe\x98'
RMDIR = '\xfe\x99'
SHELL = '\xfe\x9a'
ENVIRON = '\xfe\x9b'
VIEW = '\xfe\x9c'
WINDOW = '\xfe\x9d'
PMAP = '\xfe\x9e'
PALETTE = '\xfe\x9f'
LCOPY = '\xfe\xa0'
CALLS = '\xfe\xa1'
PCOPY = '\xfe\xa5'
LOCK = '\xfe\xa7'
UNLOCK = '\xfe\xa8'
LEFT = '\xff\x81'
RIGHT = '\xff\x82'
MID = '\xff\x83'
SGN = '\xff\x84'
INT = '\xff\x85'
ABS = '\xff\x86'
SQR = '\xff\x87'
RND = '\xff\x88'
SIN = '\xff\x89'
LOG = '\xff\x8a'
EXP = '\xff\x8b'
COS = '\xff\x8c'
TAN = '\xff\x8d'
ATN = '\xff\x8e'
FRE = '\xff\x8f'
INP = '\xff\x90'
POS = '\xff\x91'
LEN = '\xff\x92'
STR = '\xff\x93'
VAL = '\xff\x94'
ASC = '\xff\x95'
CHR = '\xff\x96'
PEEK = '\xff\x97'
SPACE = '\xff\x98'
OCT = '\xff\x99'
HEX = '\xff\x9a'
LPOS = '\xff\x9b'
CINT = '\xff\x9c'
CSNG = '\xff\x9d'
CDBL = '\xff\x9e'
FIX = '\xff\x9f'
PEN = '\xff\xa0'
STICK = '\xff\xa1'
STRIG = '\xff\xa2'
EOF = '\xff\xa3'
LOC = '\xff\xa4'
LOF = '\xff\xa5'
# PCjr and Tandy only
NOISE = '\xfe\xa4'
TERM = '\xfe\xa6'

KW_END = 'END'
KW_FOR = 'FOR'
KW_NEXT = 'NEXT'
KW_DATA = 'DATA'
KW_INPUT = 'INPUT'
KW_DIM = 'DIM'
KW_READ = 'READ'
KW_LET = 'LET'
KW_GOTO = 'GOTO'
KW_RUN = 'RUN'
KW_IF = 'IF'
KW_RESTORE = 'RESTORE'
KW_GOSUB = 'GOSUB'
KW_RETURN = 'RETURN'
KW_REM = 'REM'
KW_STOP = 'STOP'
KW_PRINT = 'PRINT'
KW_CLEAR = 'CLEAR'
KW_LIST = 'LIST'
KW_NEW = 'NEW'
KW_ON = 'ON'
KW_WAIT = 'WAIT'
KW_DEF = 'DEF'
KW_POKE = 'POKE'
KW_CONT = 'CONT'
KW_OUT = 'OUT'
KW_LPRINT = 'LPRINT'
KW_LLIST = 'LLIST'
KW_WIDTH = 'WIDTH'
KW_ELSE = 'ELSE'
KW_TRON = 'TRON'
KW_TROFF = 'TROFF'
KW_SWAP = 'SWAP'
KW_ERASE = 'ERASE'
KW_EDIT = 'EDIT'
KW_ERROR = 'ERROR'
KW_RESUME = 'RESUME'
KW_DELETE = 'DELETE'
KW_AUTO = 'AUTO'
KW_RENUM = 'RENUM'
KW_DEFSTR = 'DEFSTR'
KW_DEFINT = 'DEFINT'
KW_DEFSNG = 'DEFSNG'
KW_DEFDBL = 'DEFDBL'
KW_LINE = 'LINE'
KW_WHILE = 'WHILE'
KW_WEND = 'WEND'
KW_CALL = 'CALL'
KW_WRITE = 'WRITE'
KW_OPTION = 'OPTION'
KW_RANDOMIZE = 'RANDOMIZE'
KW_OPEN = 'OPEN'
KW_CLOSE = 'CLOSE'
KW_LOAD = 'LOAD'
KW_MERGE = 'MERGE'
KW_SAVE = 'SAVE'
KW_COLOR = 'COLOR'
KW_CLS = 'CLS'
KW_MOTOR = 'MOTOR'
KW_BSAVE = 'BSAVE'
KW_BLOAD = 'BLOAD'
KW_SOUND = 'SOUND'
KW_BEEP = 'BEEP'
KW_PSET = 'PSET'
KW_PRESET = 'PRESET'
KW_SCREEN = 'SCREEN'
KW_KEY = 'KEY'
KW_LOCATE = 'LOCATE'
KW_TO = 'TO'
KW_THEN = 'THEN'
KW_TAB = 'TAB('
KW_STEP = 'STEP'
KW_USR = 'USR'
KW_FN = 'FN'
KW_SPC = 'SPC('
KW_NOT = 'NOT'
KW_ERL = 'ERL'
KW_ERR = 'ERR'
KW_STRING = 'STRING$'
KW_USING = 'USING'
KW_INSTR = 'INSTR'
KW_O_REM = "'"
KW_VARPTR = 'VARPTR'
KW_CSRLIN = 'CSRLIN'
KW_POINT = 'POINT'
KW_OFF = 'OFF'
KW_INKEY = 'INKEY$'
KW_O_GT = '>'
KW_O_EQ = '='
KW_O_LT = '<'
KW_O_PLUS = '+'
KW_O_MINUS = '-'
KW_O_TIMES = '*'
KW_O_DIV = '/'
KW_O_CARET = '^'
KW_AND = 'AND'
KW_OR = 'OR'
KW_XOR = 'XOR'
KW_EQV = 'EQV'
KW_IMP = 'IMP'
KW_MOD = 'MOD'
KW_O_INTDIV = '\\'
KW_CVI = 'CVI'
KW_CVS = 'CVS'
KW_CVD = 'CVD'
KW_MKI = 'MKI$'
KW_MKS = 'MKS$'
KW_MKD = 'MKD$'
KW_EXTERR = 'EXTERR'
KW_FILES = 'FILES'
KW_FIELD = 'FIELD'
KW_SYSTEM = 'SYSTEM'
KW_NAME = 'NAME'
KW_LSET = 'LSET'
KW_RSET = 'RSET'
KW_KILL = 'KILL'
KW_PUT = 'PUT'
KW_GET = 'GET'
KW_RESET = 'RESET'
KW_COMMON = 'COMMON'
KW_CHAIN = 'CHAIN'
KW_DATE = 'DATE$'
KW_TIME = 'TIME$'
KW_PAINT = 'PAINT'
KW_COM = 'COM'
KW_CIRCLE = 'CIRCLE'
KW_DRAW = 'DRAW'
KW_PLAY = 'PLAY'
KW_TIMER = 'TIMER'
KW_ERDEV = 'ERDEV'
KW_IOCTL = 'IOCTL'
KW_CHDIR = 'CHDIR'
KW_MKDIR = 'MKDIR'
KW_RMDIR = 'RMDIR'
KW_SHELL = 'SHELL'
KW_ENVIRON = 'ENVIRON'
KW_VIEW = 'VIEW'
KW_WINDOW = 'WINDOW'
KW_PMAP = 'PMAP'
KW_PALETTE = 'PALETTE'
KW_LCOPY = 'LCOPY'
KW_CALLS = 'CALLS'
KW_PCOPY = 'PCOPY'
KW_LOCK = 'LOCK'
KW_UNLOCK = 'UNLOCK'
KW_LEFT = 'LEFT$'
KW_RIGHT = 'RIGHT$'
KW_MID = 'MID$'
KW_SGN = 'SGN'
KW_INT = 'INT'
KW_ABS = 'ABS'
KW_SQR = 'SQR'
KW_RND = 'RND'
KW_SIN = 'SIN'
KW_LOG = 'LOG'
KW_EXP = 'EXP'
KW_COS = 'COS'
KW_TAN = 'TAN'
KW_ATN = 'ATN'
KW_FRE = 'FRE'
KW_INP = 'INP'
KW_POS = 'POS'
KW_LEN = 'LEN'
KW_STR = 'STR$'
KW_VAL = 'VAL'
KW_ASC = 'ASC'
KW_CHR = 'CHR$'
KW_PEEK = 'PEEK'
KW_SPACE = 'SPACE$'
KW_OCT = 'OCT$'
KW_HEX = 'HEX$'
KW_LPOS = 'LPOS'
KW_CINT = 'CINT'
KW_CSNG = 'CSNG'
KW_CDBL = 'CDBL'
KW_FIX = 'FIX'
KW_PEN = 'PEN'
KW_STICK = 'STICK'
KW_STRIG = 'STRIG'
KW_EOF = 'EOF'
KW_LOC = 'LOC'
KW_LOF = 'LOF'

KW_NOISE = 'NOISE'
KW_TERM = 'TERM'

# non-keywords that appear as syntax elements
W_AS = 'AS'
W_SHARED = 'SHARED'
W_ACCESS = 'ACCESS'
W_RANDOM = 'RANDOM'
W_OUTPUT = 'OUTPUT'
W_APPEND = 'APPEND'
W_BASE = 'BASE'
W_SEG = 'SEG'
W_ALL = 'ALL'

# other keywords on http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html :
# Sperry PC only:
#   0xFEA4: 'DEBUG' (conflicts with PCjr/Tandy NOISE)
# Undefined tokens:
#   0x9A,  0x9B,  0x9F,  0xB4,  0xB5,  0xB6,  0xCB,  0xDF,  0xE0,  0xE1,  0xE2
#   0xE3,  0xE4,  0xE5,  0xF5,  0xF6,  0xF7,  0xF8,  0xF9,  0xFA,  0xFB,  0xFC
DIGIT = (C_0, C_1, C_2, C_3, C_4, C_5, C_6, C_7, C_8, C_9)
NUMBER = (T_OCT, T_HEX, T_BYTE, T_INT, T_SINGLE, T_DOUBLE,
          C_0, C_1, C_2, C_3, C_4, C_5, C_6, C_7, C_8, C_9, C_10)
LINE_NUMBER = (T_UINT, T_UINT_PROC)
OPERATOR = (O_GT, O_EQ, O_LT, O_PLUS, O_MINUS,
            O_TIMES, O_DIV, O_CARET, O_INTDIV)

# line ending tokens
END_LINE = ('\0', '')
# statement ending tokens
END_STATEMENT = END_LINE + (':',)
# expression ending tokens
END_EXPRESSION = END_STATEMENT + (')', ']', ',', ';')
## tokens followed by one or more bytes to be skipped
PLUS_BYTES = {
    T_BYTE:1, '\xff':1 , '\xfe':1, '\xfd':1, T_OCT:2, T_HEX:2,
    T_UINT_PROC:2, T_UINT:2, T_INT:2, T_SINGLE:4, T_DOUBLE:8, '\0':4}

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
        self.to_token = dict((reversed(item) for item in self.to_keyword.items()))
