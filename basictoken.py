"""
PC-BASIC - basictoken.py
BASIC keyword tokens

(c) 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

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
# PC-BASIC only; not a GW-BASIC token
DEBUG = '\xff\xff'

# keyword dictionary
to_keyword = {
    END: 'END', FOR: 'FOR', NEXT: 'NEXT', DATA: 'DATA', INPUT: 'INPUT',
    DIM: 'DIM', READ: 'READ', LET: 'LET', GOTO: 'GOTO', RUN: 'RUN', IF: 'IF',
    RESTORE: 'RESTORE', GOSUB: 'GOSUB', RETURN: 'RETURN', REM: 'REM',
    STOP: 'STOP', PRINT: 'PRINT', CLEAR: 'CLEAR', LIST: 'LIST', NEW: 'NEW',
    ON: 'ON', WAIT: 'WAIT', DEF: 'DEF', POKE: 'POKE', CONT: 'CONT', OUT: 'OUT',
    LPRINT: 'LPRINT', LLIST: 'LLIST', WIDTH: 'WIDTH', ELSE: 'ELSE',
    TRON: 'TRON', TROFF: 'TROFF', SWAP: 'SWAP', ERASE: 'ERASE', EDIT: 'EDIT',
    ERROR: 'ERROR', RESUME: 'RESUME', DELETE: 'DELETE', AUTO: 'AUTO',
    RENUM: 'RENUM', DEFSTR: 'DEFSTR', DEFINT: 'DEFINT', DEFSNG: 'DEFSNG',
    DEFDBL: 'DEFDBL', LINE: 'LINE', WHILE: 'WHILE', WEND: 'WEND', CALL: 'CALL',
    WRITE: 'WRITE', OPTION: 'OPTION', RANDOMIZE: 'RANDOMIZE', OPEN: 'OPEN',
    CLOSE: 'CLOSE', LOAD: 'LOAD', MERGE: 'MERGE', SAVE: 'SAVE', COLOR: 'COLOR',
    CLS: 'CLS', MOTOR: 'MOTOR', BSAVE: 'BSAVE', BLOAD: 'BLOAD', SOUND: 'SOUND',
    BEEP: 'BEEP', PSET: 'PSET', PRESET: 'PRESET', SCREEN: 'SCREEN', KEY: 'KEY',
    LOCATE: 'LOCATE', TO: 'TO', THEN: 'THEN', TAB: 'TAB(', STEP: 'STEP',
    USR: 'USR', FN: 'FN', SPC: 'SPC(', NOT: 'NOT', ERL: 'ERL', ERR: 'ERR',
    STRING: 'STRING$', USING: 'USING', INSTR: 'INSTR', O_REM: "'",
    VARPTR: 'VARPTR', CSRLIN: 'CSRLIN', POINT: 'POINT', OFF: 'OFF',
    INKEY: 'INKEY$', O_GT: '>', O_EQ: '=', O_LT: '<',
    O_PLUS: '+', O_MINUS: '-', O_TIMES: '*', O_DIV: '/',
    O_CARET: '^', AND: 'AND', OR: 'OR', XOR: 'XOR', EQV: 'EQV', IMP: 'IMP',
    MOD: 'MOD', O_INTDIV: '\\', CVI: 'CVI', CVS: 'CVS', CVD: 'CVD', MKI: 'MKI$',
    MKS: 'MKS$', MKD: 'MKD$', EXTERR: 'EXTERR', FILES: 'FILES', FIELD: 'FIELD',
    SYSTEM: 'SYSTEM', NAME: 'NAME', LSET: 'LSET', RSET: 'RSET', KILL: 'KILL',
    PUT: 'PUT', GET: 'GET', RESET: 'RESET', COMMON: 'COMMON', CHAIN: 'CHAIN',
    DATE: 'DATE$', TIME: 'TIME$', PAINT: 'PAINT', COM: 'COM', CIRCLE: 'CIRCLE',
    DRAW: 'DRAW', PLAY: 'PLAY', TIMER: 'TIMER', ERDEV: 'ERDEV', IOCTL: 'IOCTL',
    CHDIR: 'CHDIR', MKDIR: 'MKDIR', RMDIR: 'RMDIR', SHELL: 'SHELL',
    ENVIRON: 'ENVIRON', VIEW: 'VIEW', WINDOW: 'WINDOW', PMAP: 'PMAP',
    PALETTE: 'PALETTE', LCOPY: 'LCOPY', CALLS: 'CALLS', PCOPY: 'PCOPY',
    LOCK: 'LOCK', UNLOCK: 'UNLOCK', LEFT: 'LEFT$', RIGHT: 'RIGHT$', MID: 'MID$',
    SGN: 'SGN', INT: 'INT', ABS: 'ABS', SQR: 'SQR', RND: 'RND', SIN: 'SIN',
    LOG: 'LOG', EXP: 'EXP', COS: 'COS', TAN: 'TAN', ATN: 'ATN', FRE: 'FRE',
    INP: 'INP', POS: 'POS', LEN: 'LEN', STR: 'STR$', VAL: 'VAL', ASC: 'ASC',
    CHR: 'CHR$', PEEK: 'PEEK', SPACE: 'SPACE$', OCT: 'OCT$', HEX: 'HEX$',
    LPOS: 'LPOS',  CINT: 'CINT', CSNG: 'CSNG', CDBL: 'CDBL', FIX: 'FIX',
    PEN: 'PEN', STICK: 'STICK', STRIG: 'STRIG', EOF: 'EOF', LOC: 'LOC',
    LOF: 'LOF',}

# other keywords on http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html :
# Sperry PC only:
#   0xFEA4: 'DEBUG' (conflicts with PCjr/Tandy NOISE)
# Undefined tokens:
#   0x9A,  0x9B,  0x9F,  0xB4,  0xB5,  0xB6,  0xCB,  0xDF,  0xE0,  0xE1,  0xE2
#   0xE3,  0xE4,  0xE5,  0xF5,  0xF6,  0xF7,  0xF8,  0xF9,  0xFA,  0xFB,  0xFC
digit = (C_0, C_1, C_2, C_3, C_4, C_5, C_6, C_7, C_8, C_9)
number = (T_OCT, T_HEX, T_BYTE, T_INT, T_SINGLE, T_DOUBLE,
          C_0, C_1, C_2, C_3, C_4, C_5, C_6, C_7, C_8, C_9, C_10)
linenum = (T_UINT, T_UINT_PROC)
operator = (O_GT, O_EQ, O_LT, O_PLUS, O_MINUS,
            O_TIMES, O_DIV, O_CARET, O_INTDIV)
with_bracket = (SPC, TAB)

# LF is just whitespace if not preceded by CR
whitespace = (' ', '\t', '\n')
# line ending tokens
end_line = ('\0', '')
# statement ending tokens
end_statement = end_line + (':',)
# expression ending tokens
# \xCC is TO, \x89 is GOTO, \x8D is GOSUB, \xCF is STEP, \xCD is THEN
end_expression = end_statement + (')', ']', ',', ';', TO, GOTO, GOSUB, STEP, THEN)
## tokens followed by one or more bytes to be skipped
plus_bytes = {
    T_BYTE:1, '\xff':1 , '\xfe':1, '\xfd':1, T_OCT:2, T_HEX:2,
    T_UINT_PROC:2, T_UINT:2, T_INT:2, T_SINGLE:4, T_DOUBLE:8, '\0':4}
