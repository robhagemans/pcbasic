"""
PC-BASIC - tokeniser.py
Convert plain-text BASIC code to tokenised form

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string
import struct
import io

from ..base import tokens as tk
from ..base import codestream
from .. import values


class PlainTextStream(codestream.CodeStream):
    """Stream of plain-text BASIC code."""

    end_line = ('\0', '\r')

    def read_line_number(self):
        """Read a line or jump number, return as int."""
        word = bytearray()
        ndigits, nblanks = 0, 0
        # don't read more than 5 digits
        while (ndigits < 5):
            c = self.peek()
            if not c:
                break
            elif c in string.digits:
                word += self.read(1)
                nblanks = 0
                ndigits += 1
                if int(word) > 6552:
                    # note: anything >= 65530 is illegal in GW-BASIC
                    # in loading an ASCII file, GWBASIC would interpret these as
                    # '6553 1' etcetera, generating a syntax error on load.
                    break
            elif c in self.blanks:
                self.read(1)
                nblanks += 1
            else:
                break
        # don't claim trailing w/s
        self.seek(-nblanks, 1)
        if word:
            return int(word)
        return None


class Tokeniser(object):
    """BASIC tokeniser."""

    # keywords than can followed by one or more line numbers
    _linenum_words = (
        tk.KW_GOTO, tk.KW_THEN, tk.KW_ELSE, tk.KW_GOSUB,
        tk.KW_LIST, tk.KW_RENUM, tk.KW_EDIT, tk.KW_LLIST,
        tk.KW_DELETE, tk.KW_RUN, tk.KW_RESUME, tk.KW_AUTO,
        tk.KW_ERL, tk.KW_RESTORE, tk.KW_RETURN)

    # operator symbols
    _ascii_operators = '+-=/\\^*<>'

    def __init__(self, values, keyword_dict):
        """Initialise tokeniser."""
        self._values = values
        self._keyword_to_token = keyword_dict.to_token

    def tokenise_line(self, line):
        """Convert an ascii program line to tokenised form."""
        ins = PlainTextStream(line)
        outs = codestream.TokenisedStream()
        # skip whitespace at start of line
        d = ins.skip_blank()
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
            c = ins.peek()
            # anything after NUL is ignored till EOL
            if c == '\0':
                ins.read(1)
                ins.read_to(('', '\r'))
                break
            # end of line
            elif c in ('', '\r'):
                break
            # handle whitespace
            elif c in ins.blanks:
                ins.read(1)
                outs.write(c)
            # handle string literals
            elif ins.peek() == '"':
                outs.write(ins.read_string())
            # handle jump numbers
            elif allow_number and allow_jumpnum and c in string.digits + '.':
                self._tokenise_jump_number(ins, outs)
            # handle numbers
            # numbers following var names with no operator or token in between
            # should not be parsed, eg OPTION BASE 1
            # note we don't include leading signs, encoded as unary operators
            # number starting with & are always parsed
            elif c in ('&', ) or (allow_number and
                                      not allow_jumpnum and c in string.digits + '.'):
                outs.write(self.tokenise_number(ins))
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
                if word in (tk.KW_REM, "'"):
                    self._tokenise_rem(ins, outs)
                elif word == tk.KW_DATA:
                    self._tokenise_data(ins, outs)
                else:
                    allow_jumpnum = (word in self._linenum_words)
                    # numbers can follow tokenised keywords
                    # (which does not include the word 'AS')
                    allow_number = (word in self._keyword_to_token)
                    if word in (tk.KW_SPC, tk.KW_TAB):
                        spc_or_tab = True
            else:
                ins.read(1)
                if c in (',', '#', ';'):
                    # can separate numbers as well as jumpnums
                    allow_number = True
                elif c in ('(', '['):
                    allow_number = True
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
        outs.write(ins.read_to(('', '\r', '\0')))

    def _tokenise_data(self, ins, outs):
        """Pass DATA as is, till end of statement, except for literals."""
        while True:
            outs.write(ins.read_to(('', '\r', '\0', ':', '"')))
            if ins.peek() == '"':
                # string literal in DATA
                outs.write(ins.read_string())
            else:
                break

    def _tokenise_line_number(self, ins, outs):
        """Convert an ascii line number to tokenised start-of-line."""
        linenum = ins.read_line_number()
        if linenum is not None:
            # NUL terminates last line and fills up the first char in the buffer
            # (that would be the magic number when written to file)
            # in direct mode, we'll know to expect a line number if the output
            # starts with a NUL
            # next two bytes are for internal use and at this point
            # can be anything nonzero; we use this.
            outs.write('\x00\xC0\xDE' + struct.pack('<H', linenum))
            # ignore single whitespace after line number, if any,
            # unless line number is zero (as does GW)
            if ins.peek() == ' ' and linenum != 0:
                ins.read(1)
        else:
            # direct line; internally, we need an anchor for the program pointer,
            # so we encode a ':'
            outs.write(':')

    def _tokenise_jump_number(self, ins, outs):
        """Convert an ascii line number pointer to tokenised form."""
        linum = ins.read_line_number()
        if linum is not None:
            outs.write(tk.T_UINT + struct.pack('<H', linum))
        elif ins.peek() == '.':
            ins.read(1)
            outs.write('.')

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
                if ins.peek(4).upper() == ' SUB':
                    word = tk.KW_GOSUB
                    ins.read(4)
                else:
                    # GOTO allows any number of spaces
                    nxt = ins.skip_blank()
                    if ins.read(2).upper() == 'TO':
                        word = tk.KW_GOTO
                    else:
                        ins.seek(pos)
                if word in (tk.KW_GOTO, tk.KW_GOSUB):
                    nxt = ins.peek()
                    if nxt in tk.NAME_CHARS:
                        ins.seek(pos)
                        word = 'GO'
            if word in self._keyword_to_token:
                # ignore if part of a longer name, except FN, SPC(, TAB(, USR
                if word not in (tk.KW_FN, tk.KW_SPC, tk.KW_TAB, tk.KW_USR):
                    nxt = ins.peek()
                    if nxt in tk.NAME_CHARS:
                        continue
                token = self._keyword_to_token[word]
                # handle special case ELSE -> :ELSE
                if word == tk.KW_ELSE:
                    outs.write(':' + token)
                # handle special case WHILE -> WHILE+
                elif word == tk.KW_WHILE:
                    outs.write(token + tk.O_PLUS)
                else:
                    outs.write(token)
                break
            # allowed names: letter + (letters, numbers, .)
            elif not c:
                outs.write(word)
                break
            elif c not in tk.NAME_CHARS:
                word = word[:-1]
                ins.seek(-1, 1)
                outs.write(word)
                break
        return word

    def tokenise_number(self, ins):
        """Convert Python-string number representation to number token."""
        word = ins.read_number()
        if not word:
            return ''
        elif word[:2] == '&H':
            # hex constant
            return self._values.new_integer().from_hex(word[2:]).to_token_hex()
        elif word[:2] == '&O':
            # octal constant
            # read_number converts &1 into &O1
            return self._values.new_integer().from_oct(word[2:]).to_token_oct()
        elif word[0] in string.digits + '.+-':
            # handle other numbers
            # note GW passes signs separately as a token
            # and only stores positive numbers in the program
            return self._values.from_repr(word, allow_nonnum=False).to_token()
