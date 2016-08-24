"""
PC-BASIC - tokeniser.py
Convert between tokenised and plain-text formats of a GW-BASIC program file

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string
import struct

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from . import basictoken as tk
from . import util
from . import values


def ascii_read_to(ins, findrange):
    """Read until a character from a given range is found."""
    out = ''
    while True:
        d = ins.read(1)
        if d == '':
            break
        if d in findrange:
            break
        out += d
    ins.seek(-len(d),1)
    return out


class Tokeniser(object):
    """BASIC tokeniser."""

    # keywords than can followed by one or more line numbers
    _linenum_words = (
        tk.KW_GOTO, tk.KW_THEN, tk.KW_ELSE, tk.KW_GOSUB,
        tk.KW_LIST, tk.KW_RENUM, tk.KW_EDIT, tk.KW_LLIST,
        tk.KW_DELETE, tk.KW_RUN, tk.KW_RESUME, tk.KW_AUTO,
        tk.KW_ERL, tk.KW_RESTORE, tk.KW_RETURN)

    # newline is considered whitespace: ' ', '\t', '\n'
    _ascii_whitespace = ' \t\n'
    # operator symbols
    _ascii_operators = '+-=/\\^*<>'

    def __init__(self, values, keyword_dict):
        """Initialise tokeniser."""
        self._values = values
        self._keyword_to_token = keyword_dict.to_token

    def tokenise_line(self, line):
        """Convert an ascii program line to tokenised form."""
        ins = StringIO(line)
        outs = StringIO()
        # skip whitespace at start of line
        d = util.skip(ins, self._ascii_whitespace)
        if d == '':
            # empty line at EOF
            return outs
        # read the line number
        self._tokenise_line_number(ins, outs)
        # expect line number
        allow_jumpnum = False
        # expect number (6553 6 -> the 6 is encoded as \x17)
        allow_number = True
        # flag for SPC( or TAB( as numbers can follow the closing bracket
        spc_or_tab = False
        # parse through elements of line
        while True:
            # peek next character
            c = util.peek(ins)
            # anything after NUL is ignored till EOL
            if c == '\0':
                ins.read(1)
                ascii_read_to(ins, ('', '\r'))
                break
            # end of line
            elif c in ('', '\r'):
                break
            # handle whitespace
            elif c in self._ascii_whitespace:
                ins.read(1)
                outs.write(c)
            # handle string literals
            elif util.peek(ins) == '"':
                self._tokenise_literal(ins, outs)
            # handle jump numbers
            elif allow_number and allow_jumpnum and c in string.digits + '.':
                self._tokenise_jump_number(ins, outs)
            # handle numbers
            # numbers following var names with no operator or token in between
            # should not be parsed, eg OPTION BASE 1
            # note we don't include leading signs, encoded as unary operators
            # number starting with . or & are always parsed
            elif c in ('&', '.') or (allow_number and
                                      not allow_jumpnum and c in string.digits):
                outs.write(self._values.tokenise_number(ins))
            # operator keywords ('+', '-', '=', '/', '\\', '^', '*', '<', '>'):
            elif c in self._ascii_operators:
                ins.read(1)
                # operators don't affect line number mode - can do line number
                # arithmetic and RENUM will do the strangest things
                # this allows for 'LIST 100-200' etc.
                outs.write(self._keyword_to_token[c])
                allow_number = True
            # special case ' -> :REM'
            elif c == "'":
                ins.read(1)
                outs.write(':' + tk.REM + tk.O_REM)
                self._tokenise_rem(ins, outs)
            # special case ? -> PRINT
            elif c == '?':
                ins.read(1)
                outs.write(tk.PRINT)
                allow_number = True
            # keywords & variable names
            elif c in string.ascii_letters:
                word = self._tokenise_word(ins, outs)
                # handle non-parsing modes
                if (word in ('REM', "'") or
                            (word == 'DEBUG' and word in self._keyword_to_token)):
                    self._tokenise_rem(ins, outs)
                elif word == "DATA":
                    self._tokenise_data(ins, outs)
                else:
                    allow_jumpnum = (word in self._linenum_words)
                    # numbers can follow tokenised keywords
                    # (which does not include the word 'AS')
                    allow_number = (word in self._keyword_to_token)
                    if word in ('SPC(', 'TAB('):
                        spc_or_tab = True
            else:
                ins.read(1)
                if c in (',', '#', ';'):
                    # can separate numbers as well as jumpnums
                    allow_number = True
                elif c in ('(', '['):
                    allow_jumpnum, allow_number = False, True
                elif c == ')' and spc_or_tab:
                    spc_or_tab = False
                    allow_jumpnum, allow_number = False, True
                else:
                    allow_jumpnum, allow_number = False, False
                # replace all other nonprinting chars by spaces;
                # HOUSE 0x7f is allowed.
                outs.write(c if ord(c) >= 32 and ord(c) <= 127 else ' ')
        outs.seek(0)
        return outs

    def _tokenise_rem(self, ins, outs):
        """Pass anything after REM as is till EOL."""
        outs.write(ascii_read_to(ins, ('', '\r', '\0')))

    def _tokenise_data(self, ins, outs):
        """Pass DATA as is, till end of statement, except for literals."""
        while True:
            outs.write(ascii_read_to(ins, ('', '\r', '\0', ':', '"')))
            if util.peek(ins) == '"':
                # string literal in DATA
                self._tokenise_literal(ins, outs)
            else:
                break

    def _tokenise_literal(self, ins, outs):
        """Pass a string literal."""
        outs.write(ins.read(1))
        outs.write(ascii_read_to(ins, ('', '\r', '\0', '"') ))
        if util.peek(ins)=='"':
            outs.write(ins.read(1))

    def _tokenise_line_number(self, ins, outs):
        """Convert an ascii line number to tokenised start-of-line."""
        linenum = self._tokenise_uint(ins)
        if linenum != '':
            # terminates last line and fills up the first char in the buffer
            # (that would be the magic number when written to file)
            # in direct mode, we'll know to expect a line number if the output
            # starts with a  00
            outs.write('\0')
            # write line number. first two bytes are for internal use
            # & can be anything nonzero; we use this.
            outs.write('\xC0\xDE' + linenum)
            # ignore single whitespace after line number, if any,
            # unless line number is zero (as does GW)
            if util.peek(ins) == ' ' and linenum != '\0\0' :
                ins.read(1)
        else:
            # direct line; internally, we need an anchor for the program pointer,
            # so we encode a ':'
            outs.write(':')

    def _tokenise_jump_number(self, ins, outs):
        """Convert an ascii line number pointer to tokenised form."""
        word = self._tokenise_uint(ins)
        if word != '':
            outs.write(tk.T_UINT + word)
        elif util.peek(ins) == '.':
            ins.read(1)
            outs.write('.')

    def _tokenise_uint(self, ins):
        """Convert an unsigned int (line number) to tokenised form."""
        word = bytearray()
        while True:
            c = ins.read(1)
            if c and c in string.digits + self._ascii_whitespace:
                word += c
            else:
                ins.seek(-len(c), 1)
                break
        # don't claim trailing w/s
        while len(word)>0 and chr(word[-1]) in self._ascii_whitespace:
            del word[-1]
            ins.seek(-1, 1)
        # remove all whitespace
        trimword = bytearray()
        for c in word:
            if chr(c) not in self._ascii_whitespace:
                trimword += chr(c)
        word = trimword
        # line number (jump)
        if len(word) > 0:
            if int(word) >= 65530:
                # note: anything >= 65530 is illegal in GW-BASIC
                # in loading an ASCII file, GWBASIC would interpret these as
                # '6553 1' etcetera, generating a syntax error on load.
                # keep 6553 as line number and push back the last number:
                ins.seek(4-len(word), 1)
                word = word[:4]
            return struct.pack('<H', int(word))
        return ''

    def _tokenise_word(self, ins, outs):
        """Convert a keyword to tokenised form."""
        word = ''
        while True:
            c = ins.read(1)
            word += c.upper()
            # special cases 'GO     TO' -> 'GOTO', 'GO SUB' -> 'GOSUB'
            if word == 'GO':
                pos = ins.tell()
                # GO SUB allows 1 space
                if util.peek(ins, 4).upper() == ' SUB':
                    word = 'GOSUB'
                    ins.read(4)
                else:
                    # GOTO allows any number of spaces
                    nxt = util.skip(ins, self._ascii_whitespace)
                    if ins.read(2).upper() == 'TO':
                        word = 'GOTO'
                    else:
                        ins.seek(pos)
                if word in ('GOTO', 'GOSUB'):
                    nxt = util.peek(ins)
                    if nxt and nxt in tk.name_chars:
                        ins.seek(pos)
                        word = 'GO'
            if word in self._keyword_to_token:
                # ignore if part of a longer name, except FN, SPC(, TAB(, USR
                if word not in ('FN', 'SPC(', 'TAB(', 'USR'):
                    nxt = util.peek(ins)
                    if nxt and nxt in tk.name_chars:
                        continue
                token = self._keyword_to_token[word]
                # handle special case ELSE -> :ELSE
                if word == 'ELSE':
                    outs.write(':' + token)
                # handle special case WHILE -> WHILE+
                elif word == 'WHILE':
                    outs.write(token + tk.O_PLUS)
                else:
                    outs.write(token)
                break
            # allowed names: letter + (letters, numbers, .)
            elif not c:
                outs.write(word)
                break
            elif c not in tk.name_chars:
                word = word[:-1]
                ins.seek(-1, 1)
                outs.write(word)
                break
        return word
