"""
PC-BASIC - lister.py
Convert tokenised to plain-text format

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from ...compat import int2byte

from ..base import tokens as tk
from ..base.tokens import DIGITS, ALPHANUMERIC
from .. import values


class Lister(object):
    """BASIC detokeniser."""

    def __init__(self, values, token_dict):
        """Initialise tokeniser."""
        self._values = values
        self._token_to_keyword = token_dict.to_keyword

    def detokenise_line(self, ins, bytepos=None):
        """Convert a tokenised program line to ascii text."""
        current_line = self.detokenise_line_number(ins)
        if current_line < 0:
            # detokenise_line_number has returned -1 and left us at: .. 00 | _00_ 00 1A
            # stream ends or end of file sequence \x00\x00\x1A
            return -1, b'', 0
        elif current_line == 0 and ins.peek() == b' ':
            # ignore up to one space after line number 0
            ins.read(1)
        linum = bytearray(b'%d' % (current_line,))
        # write one extra whitespace character after line number
        # unless first char is TAB
        if ins.peek() != b'\t':
            linum += bytearray(b' ')
        find_textpos = bytepos is not None and ins.tell() < bytepos
        line, found_textpos = self.detokenise_compound_statement(ins, bytepos)
        if find_textpos:
            textpos = found_textpos + len(linum) + 1
        else:
            textpos = 0
        return current_line, linum + line, textpos

    def detokenise_line_number(self, ins):
        """Parse line number and leave pointer at first char of line."""
        trail = ins.read(4)
        linum = self.token_to_line_number(trail)
        # if end of program or truncated, leave pointer at start of line number C0 DE or 00 00
        if linum == -1:
            ins.seek(-len(trail), 1)
        return linum

    def token_to_line_number(self, trail):
        """Unpack a line number token trail, -1 if end of program."""
        if len(trail) < 4 or trail[:2] == b'\0\0':
            return -1
        return struct.unpack_from('<H', trail, 2)[0]

    def detokenise_compound_statement(self, ins, bytepos=None):
        """Detokenise tokens until end of line."""
        litstring, comment = False, False
        textpos = 0
        output = bytearray()
        while True:
            s = ins.read(1)
            if not textpos and bytepos is not None and ins.tell() >= bytepos:
                textpos = len(output)
            if s in tk.END_LINE:
                # \x00 ends lines and comments when listed,
                # if not inside a number constant
                # stream ended or end of line
                break
            elif s == b'"':
                # start of literal string, passed verbatim
                # until a closing quote or EOL comes by
                # however number codes are *printed* as the corresponding numbers,
                # even inside comments & literals
                output += s
                litstring = not litstring
            elif s in tk.NUMBER or s in tk.LINE_NUMBER:
                output += self._detokenise_number(ins, s)
            elif comment or litstring or (b'\x20' <= s <= b'\x7E'):
                # honest ASCII
                output += s
            elif s == b'\x0A':
                # LF becomes LF CR
                output += b'\x0A\x0D'
            elif s <= b'\x09':
                # controls that do not double as tokens
                output += s
            else:
                token = self._detokenise_keyword_into(ins, s, output)
                comment = token in tk.COMMENT
        return output[:255], textpos

    def _detokenise_keyword_into(self, ins, lead, output):
        """Convert a one- or two-byte keyword token to ascii."""
        # try for single-byte token or two-byte token
        # if no match, first char is passed unchanged
        token = lead
        try:
            keyword = self._token_to_keyword[token]
        except KeyError:
            token += ins.peek()
            try:
                keyword = self._token_to_keyword[token]
                ins.read(1)
            except KeyError:
                output += token[:1]
                return False
        # letter or number followed by token is separated by a space
        if (
                token not in tk.OPERATOR
                and output and bytes(output[-1:]) in ALPHANUMERIC
                # we need to check again for FN and USR, but not SPC( and TAB(
                # because we check the converted output, not the previous token
                and not (len(output) >= 2 and bytes(output[-2:]) == tk.KW_FN)
                and not (len(output) >= 3 and bytes(output[-3:]) == tk.KW_USR)
            ):
            output += b' '
        # check for special cases
        #   [:REM']   ->  [']
        # we need to read one ahead at REM, or tk_O_REM would be transcribed as part of the comment
        # and the replacement code would not work
        next_char = ins.peek(1)
        if token == tk.REM and next_char == tk.O_REM and output and bytes(output[-1:]) == b':':
            ins.read(1)
            output[:] = output[:-1] + tk.KW_O_REM
        #   [WHILE+]  ->  [WHILE]
        elif token == tk.O_PLUS and len(output) >= 5 and bytes(output[-5:]) == tk.KW_WHILE:
            # ignore the +
            pass
        #   [:ELSE]  ->  [ELSE]
        # note that anything before ELSE gets cut off,
        # e.g. if we have 1ELSE instead of :ELSE it also becomes ELSE
        elif token == tk.ELSE:
            if not output:
                # special case at start of line, lone ELSE (not :ELSE) becomes LSE
                output += keyword[1:]
            else:
                output[:] = output[:-1] + keyword
        else:
            output += keyword
        # token followed by token or number is separated by a space,
        # except operator tokens, comment tokens and SPC(, TAB(, FN, USR
        if (
                token not in tk.OPERATOR + tk.COMMENT + (tk.TAB, tk.SPC, tk.USR, tk.FN)
                and next_char not in tk.END_LINE + tk.OPERATOR + (
                    tk.O_REM, b'"', b',', b';', b' ', b':', b'(', b')', b'$',
                    b'%', b'!', b'#', b'_', b'@', b'~', b'|', b'`'
                )
            ):
            # excluding TAB( SPC( and FN. \xD9 is ', \xD1 is FN, \xD0 is USR.
            output += b' '
        return token

    def _detokenise_number(self, ins, lead):
        """Convert number token to Python string."""
        ntrail = tk.PLUS_BYTES.get(lead, 0)
        trail = ins.read(ntrail)
        if lead == tk.T_OCT:
            return b'&O' + self._values.from_bytes(trail).to_oct()
        elif lead == tk.T_HEX:
            return b'&H' + self._values.from_bytes(trail).to_hex()
        elif lead == tk.T_BYTE:
            return b'%d' % (ord(trail),)
        elif tk.C_0 <= lead <= tk.C_10:
            return b'%d' % (ord(lead) - ord(tk.C_0),)
        elif lead in tk.LINE_NUMBER:
            # 0D: line pointer (unsigned int) - this token should not be here;
            #     interpret as line number and carry on
            # 0E: line number (unsigned int)
            return b'%d' % (struct.unpack('<H', trail)[0],)
        elif lead in (tk.T_SINGLE, tk.T_DOUBLE, tk.T_INT):
            return self._values.from_bytes(trail).to_str(leading_space=False, type_sign=True)
        return b''
