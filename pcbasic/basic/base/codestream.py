"""
PC-BASIC - codestream.py
Code stream utilities

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from functools import partial
import io

from . import error
from . import tokens as tk
from .tokens import DIGITS, HEXDIGITS, OCTDIGITS, LETTERS
from ...compat import StreamWrapper


class CodeStream(StreamWrapper):
    """Stream of various kinds of code."""

    # whitespace
    blanks = b' \t\n'
    # line end characters for ths stream type
    end_line = None

    def __init__(self, bytesbuffer):
        """Initialise the stream."""
        self._buffer = bytesbuffer
        # we need delegation rather than inheritance to allow pickling under Python 2
        StreamWrapper.__init__(self, io.BytesIO(bytesbuffer))

    def peek(self, n=1):
        """Peek next char in stream."""
        d = self.read(n)
        self.seek(-len(d), 1)
        return d

    def skip_read(self, skip_range, n=1):
        """Skip chars in skip_range, then read next."""
        while True:
            d = self.read(1)
            # skip_range must not include ''
            if d == b'' or d not in skip_range:
                return d + self.read(n-1)

    def skip_blank_read(self, n=1):
        """Skip whitespace, then read next."""
        return self.skip_read(self.blanks, n)

    def skip_blank(self, n=1):
        """Skip whitespace, then peek next."""
        d = self.skip_read(self.blanks, n)
        self.seek(-len(d), 1)
        return d

    def backskip_blank(self):
        """Skip whitespace backwards, then peek next."""
        while True:
            self.seek(-1, 1)
            d = self.peek()
            # skip_range must not include ''
            if d == b'' or d not in self.blanks:
                return d

    def read_if(self, d, in_range):
        """Read if next char is not empty and in range."""
        if d != b'' and d in in_range:
            self.read(len(d))
            return d
        return None

    def skip_blank_read_if(self, in_range, n=1):
        """Skip whitespace, then read if next char is in range."""
        return self.read_if(self.skip_blank(n=n), in_range)

    def read_to(self, findrange):
        """Read until a character from a given range is found."""
        out = b''
        while True:
            d = self.read(1)
            if d == b'':
                break
            if d in findrange:
                break
            out += d
        self.seek(-len(d), 1)
        return out

    def require_read(self, in_range, err=error.STX):
        """Skip whitespace, read and raise error if not in range."""
        d = self.read(1)
        while d and d in self.blanks:
            d = self.read(1)
        c = d + self.read(len(in_range[0])-1)
        if not c or c not in in_range:
            self.seek(-len(c), 1)
            raise error.BASICError(err)
        return c

    # read specialised items
    # these are used for both plaintext and tokenised streams:
    # tokenised streams may contain plaintext literals and names are always plaintext

    def read_name(self):
        """Read a variable name."""
        d = self.skip_blank_read()
        if not d or d not in LETTERS:
            # variable name must start with a letter
            self.seek(-len(d), 1)
            return b''
        name = b''
        while d and d in tk.NAME_CHARS:
            name += d
            d = self.read(1)
        # only the first 40 chars are relevant in GW-BASIC, rest is discarded
        name = name[:40]
        if d in tk.SIGILS:
            name += d
        else:
            self.seek(-len(d), 1)
        # names are not case sensitive
        return name.upper()

    def read_number(self):
        """Read numeric literal."""
        c = self.peek()
        if c == b'&':
            # handle hex or oct constants
            self.read(1)
            if self.peek().upper() == b'H':
                # hex literal
                return b'&H' + self._read_hex()
            else:
                # octal literal
                return b'&O' + self._read_oct()
        elif c and c in DIGITS + b'.+-':
            # decimal literal
            return self._read_dec()
        return b''

    def _read_dec(self):
        """Read decimal literal."""
        have_exp = False
        have_point = False
        word = b''
        while True:
            c = self.read(1).upper()
            if not c:
                break
            elif c == b'.' and not have_point and not have_exp:
                have_point = True
                word += c
            elif c in b'ED' and not have_exp:
                # there's a special exception for number followed by EL or EQ
                # presumably meant to protect ELSE and maybe EQV ?
                if c == b'E' and self.peek().upper() in (b'L', b'Q'):
                    self.seek(-1, 1)
                    break
                else:
                    have_exp = True
                    word += c
            elif c in b'-+' and (not word or word[-1:] in b'ED'):
                # must be first character or in exponent
                word += c
            elif c in DIGITS + self.blanks + b'\x1c\x1d\x1f':
                # '\x1c\x1d\x1f' are ASCII separators
                # - these cause string representations to evaluate to zero
                # we'll remove blanks later but need to keep it for now
                # so we can reposition the stream on removing trailing whitespace
                word += c
            elif c in b'!#' and not have_exp:
                word += c
                # must be last character
                break
            elif c == b'%':
                # swallow a %, but break parsing
                break
            else:
                self.seek(-1, 1)
                break
        # don't claim trailing whitespace
        trimword = word.rstrip(self.blanks)
        self.seek(-len(word) + len(trimword), 1)
        # remove all internal whitespace
        word = trimword.strip(self.blanks)
        return word

    def _read_hex(self):
        """Read hexadecimal literal."""
        # pass the H in &H
        self.read(1)
        word = b''
        while True:
            c = self.peek()
            # hex literals must not be interrupted by whitespace
            if c and c in HEXDIGITS:
                word += self.read(1)
            else:
                break
        return word

    def _read_oct(self):
        """Read octal literal."""
        # O is optional, could also be &777 instead of &O777
        if self.peek().upper() == b'O':
            self.read(1)
        word = b''
        while True:
            c = self.peek()
            # oct literals may be interrupted by whitespace
            if c and c in OCTDIGITS + self.blanks:
                word += self.read(1)
            else:
                break
        return word

    def read_string(self):
        """Read a string literal."""
        word = self.read(1)
        if not word or word != b'"':
            self.seek(-len(word), 1)
            return b''
        # while tokenised numbers inside a string literal will be printed as tokenised numbers,
        # they don't actually execute as such:
        # a \00 character, even if inside a tokenised number, will break a string literal
        # and make the parser expect a line number afterwards, etc. We follow this.
        word += self.read_to((b'"',) + self.end_line)
        delim = self.read(1)
        if delim == b'"':
            word += delim
        else:
            self.seek(-len(delim), 1)
        return word


class TokenisedStream(CodeStream):
    """Stream of tokenised BASIC code."""

    end_line = tk.END_LINE

    def __init__(self, addr=None):
        """Initialise tokenised stream."""
        # memory address, if any
        self._addr = addr
        CodeStream.__init__(self, b'')

    def tell_address(self):
        """Get memory address for current stream position."""
        if self._addr is not None:
            return self._addr + self.tell()
        return None

    def skip_to(self, findrange, break_on_first_char=True):
        """Skip until character is in findrange."""
        literal = False
        rem = False
        nchars = len(findrange[0])
        while True:
            c = self.read(1)
            if c == b'':
                break
            elif c == b'"':
                literal = not literal
            elif c == tk.REM:
                rem = True
            elif c == b'\0':
                literal = False
                rem = False
            if literal or rem:
                continue
            if c + self.peek(nchars-1) in findrange:
                if break_on_first_char:
                    self.seek(-1, 1)
                    break
            break_on_first_char = True
            # not elif! if not break_on_first_char, c needs to be properly processed.
            if c == b'\0':
                # offset and line number follow
                literal = False
                off = self.read(2)
                if len(off) < 2 or off == b'\0\0':
                    break
                self.read(2)
            elif c in tk.PLUS_BYTES:
                self.read(tk.PLUS_BYTES[c])

    def skip_to_read(self, findrange):
        """Skip until character is in findrange, then read."""
        self.skip_to(findrange)
        return self.read(len(findrange[0]))

    def read_keyword_token(self):
        """Read full keyword token."""
        token = self.read(1)
        if token in (b'\xff', b'\xfe', b'\xfd'):
            token += self.read(1)
        return token

    def read_number_token(self):
        """Read full token, including trailing bytes."""
        lead = self.read(1)
        if lead not in tk.NUMBER:
            self.seek(-len(lead), 1)
            return b''
        trail = self.read(tk.PLUS_BYTES.get(lead, 0))
        return lead + trail

    def require_end(self, err=error.STX):
        """Skip whitespace, peek and raise error if not at end of statement."""
        d = self.read(1)
        while d and d in self.blanks:
            d = self.read(1)
        self.seek(-len(d), 1)
        if d not in tk.END_STATEMENT:
            raise error.BASICError(err)

    def skip_to_token(self, requested_token):
        """
        Skip over bytecode until particular token on statement start;
        this excludes statements in THEN or ELSE clauses.
        """
        while True:
            separator = self.skip_to_read(tk.END_STATEMENT)
            # skip line number, if there
            if separator == b'\0':
                # break on end of stream
                trail = self.read(4)
                if len(trail) < 4 or trail[:2] == b'\0\0':
                    return None
            # get first keyword in statement
            self.skip_blank()
            token = self.read_keyword_token()
            self.seek(-len(token), 1)
            if not token:
                return None
            elif token == requested_token:
                return token

    def skip_block(self, for_char, next_char, allow_comma=False):
        """Skip over bytecode until block end token."""
        stack = 0
        while True:
            c = self.skip_to_read(tk.END_STATEMENT + (tk.THEN, tk.ELSE))
            # skip line number, if there
            if c == b'\0':
                # break on end of stream
                trail = self.read(4)
                if len(trail) < 4 or trail[:2] == b'\0\0':
                    break
            # get first keyword in statement
            d = self.skip_blank()
            if d == b'':
                break
            elif d == for_char:
                self.read(1)
                stack += 1
            elif d == next_char:
                if stack <= 0:
                    break
                else:
                    self.read(1)
                    stack -= 1
                    # NEXT I, J
                    if allow_comma:
                        while (self.skip_blank() not in tk.END_STATEMENT):
                            self.skip_to(tk.END_STATEMENT + (b',',))
                            if self.peek() == b',':
                                if stack > 0:
                                    self.read(1)
                                    stack -= 1
                                else:
                                    return
