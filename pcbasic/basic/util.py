"""
PC-BASIC - util.py
Token stream utilities

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from functools import partial
import string
import io

from . import error
from . import tokens as tk


class CodeStream(io.BytesIO):

    blanks = None

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
            if d == '' or d not in skip_range:
                return d + self.read(n-1)

    def skip(self, skip_range, n=1):
        """Skip chars in skip_range, then peek next."""
        d = skip_read(self, skip_range, n)
        self.seek(-len(d), 1)
        return d

    def skip_blank_read(self, n=1):
        """Skip whitespace, then read next."""
        return self.skip_read(self.blanks, n)

    def skip_blank(self, n=1):
        """Skip whitespace, then peek next."""
        d = skip_read(self, self.blanks, n)
        self.seek(-len(d), 1)
        return d

    def backskip_blank(self):
        """Skip whitespace backwards, then peek next."""
        while True:
            self.seek(-1, 1)
            d = peek(self)
            # skip_range must not include ''
            if d == '' or d not in self.blanks:
                return d

    def read_if(self, d, in_range):
        """Read if next char is in range."""
        if d != '' and d in in_range:
            self.read(len(d))
            return True
        return False

    def skip_blank_read_if(self, in_range):
        """Skip whitespace, then read if next char is in range."""
        return read_if(self, self.skip_blank(n=len(in_range[0])), in_range)

    def read_name(self, allow_empty=False):
        """Read a variable name """
        name = ''
        d = self.skip_blank_read()
        if not d:
            pass
        elif d not in string.ascii_letters:
            # variable name must start with a letter
            self.seek(-len(d), 1)
        else:
            while d and d in tk.name_chars:
                name += d
                d = self.read(1)
            if d in tk.sigils:
                name += d
            else:
                self.seek(-len(d), 1)
        if not name and not allow_empty:
            raise error.RunError(error.STX)
        return name


class TokenisedStream(CodeStream):

    blanks = tk.whitespace

    def skip_to(self, findrange, break_on_first_char=True):
        """Skip until character is in findrange."""
        literal = False
        rem = False
        while True:
            c = self.read(1)
            if c == '':
                break
            elif c == '"':
                literal = not literal
            elif c == tk.REM:
                rem = True
            elif c == '\0':
                literal = False
                rem = False
            if literal or rem:
                continue
            if c in findrange:
                if break_on_first_char:
                    self.seek(-1, 1)
                    break
                else:
                    break_on_first_char = True
            # not elif! if not break_on_first_char, c needs to be properly processed.
            if c == '\0':  # offset and line number follow
                literal = False
                off = self.read(2)
                if len(off) < 2 or off == '\0\0':
                    break
                self.read(2)
            elif c in tk.plus_bytes:
                self.read(tk.plus_bytes[c])

    def skip_to_read(self, findrange):
        """Skip until character is in findrange, then read."""
        self.skip_to(findrange)
        return self.read(1)

    def read_token(self):
        """Read full token, including trailing bytes."""
        lead = self.read(1)
        try:
            length = tk.plus_bytes[lead]
        except KeyError:
            length = 0
        trail = self.read(length)
        if len(trail) < length:
            # truncated stream
            raise error.RunError(error.STX)
        return lead + trail


    def require_read(self, in_range, err=error.STX):
        """Skip whitespace, read and raise error if not in range."""
        if not self.skip_blank_read_if(in_range):
            raise error.RunError(err)

    def require(self, rnge, err=error.STX):
        """Skip whitespace, peek and raise error if not in range."""
        if self.skip_blank(n=len(rnge[0])) not in rnge:
            raise error.RunError(err)



###############################################################################
# stream utilities

def peek(ins, n=1):
    """Peek next char in stream."""
    d = ins.read(n)
    ins.seek(-len(d), 1)
    return d

def skip_read(ins, skip_range, n=1):
    """Skip chars in skip_range, then read next."""
    while True:
        d = ins.read(1)
        # skip_range must not include ''
        if d == '' or d not in skip_range:
            return d + ins.read(n-1)

def skip(ins, skip_range, n=1):
    """Skip chars in skip_range, then peek next."""
    d = skip_read(ins, skip_range, n)
    ins.seek(-len(d), 1)
    return d

def backskip_white(ins):
    """Skip whitespace backwards, then peek next."""
    while True:
        ins.seek(-1, 1)
        d = peek(ins)
        # skip_range must not include ''
        if d == '' or d not in tk.whitespace:
            return d

# skip whitespace, then read next
skip_white_read = partial(skip_read, skip_range=tk.whitespace)
# skip whitespace, then peek next
skip_white = partial(skip, skip_range=tk.whitespace)

def skip_white_read_if(ins, in_range):
    """Skip whitespace, then read if next char is in range."""
    return read_if(ins, skip_white(ins, n=len(in_range[0])), in_range)

def read_if(ins, d, in_range):
    """Read if next char is in range."""
    if d != '' and d in in_range:
        ins.read(len(d))
        return True
    return False


def skip_to(ins, findrange, break_on_first_char=True):
    """Skip until character is in findrange."""
    literal = False
    rem = False
    while True:
        c = ins.read(1)
        if c == '':
            break
        elif c == '"':
            literal = not literal
        elif c == tk.REM:
            rem = True
        elif c == '\0':
            literal = False
            rem = False
        if literal or rem:
            continue
        if c in findrange:
            if break_on_first_char:
                ins.seek(-1, 1)
                break
            else:
                break_on_first_char = True
        # not elif! if not break_on_first_char, c needs to be properly processed.
        if c == '\0':  # offset and line number follow
            literal = False
            off = ins.read(2)
            if len(off) < 2 or off == '\0\0':
                break
            ins.read(2)
        elif c in tk.plus_bytes:
            ins.read(tk.plus_bytes[c])

def skip_to_read(ins, findrange):
    """Skip until character is in findrange, then read."""
    skip_to(ins, findrange)
    return ins.read(1)

def read_token(ins):
    """Read full token, including trailing bytes."""
    lead = ins.read(1)
    try:
        length = tk.plus_bytes[lead]
    except KeyError:
        length = 0
    trail = ins.read(length)
    if len(trail) < length:
        # truncated stream
        raise error.RunError(error.STX)
    return lead + trail

###############################################################################
# parsing utilities

def require_read(ins, in_range, err=error.STX):
    """Skip whitespace, read and raise error if not in range."""
    if not skip_white_read_if(ins, in_range):
        raise error.RunError(err)

def require(ins, rnge, err=error.STX):
    """Skip whitespace, peek and raise error if not in range."""
    if skip_white(ins, n=len(rnge[0])) not in rnge:
        raise error.RunError(err)

def read_name(ins, allow_empty=False):
    """Read a variable name """
    name = ''
    d = skip_white_read(ins)
    if not d:
        pass
    elif d not in string.ascii_letters:
        # variable name must start with a letter
        ins.seek(-len(d), 1)
    else:
        while d and d in tk.name_chars:
            name += d
            d = ins.read(1)
        if d in tk.sigils:
            name += d
        else:
            ins.seek(-len(d), 1)
    if not name and not allow_empty:
        raise error.RunError(error.STX)
    return name
