"""
PC-BASIC - lister.py
Convert tokenised to plain-text format

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string
import struct

from . import basictoken as tk
from . import util
from . import values


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
            return -1, '', 0
        elif current_line == 0 and util.peek(ins) == ' ':
            # ignore up to one space after line number 0
            ins.read(1)
        linum = bytearray(str(current_line))
        # write one extra whitespace character after line number
        # unless first char is TAB
        if util.peek(ins) != '\t':
            linum += bytearray(' ')
        line, textpos = self.detokenise_compound_statement(ins, bytepos)
        return current_line, linum + line, textpos + len(linum) + 1

    def detokenise_line_number(self, ins):
        """Parse line number and leave pointer at first char of line."""
        # if end of program or truncated, leave pointer at start of line number C0 DE or 00 00
        off = ins.read(2)
        if off == '\0\0' or len(off) < 2:
            ins.seek(-len(off), 1)
            return -1
        off = ins.read(2)
        if len(off) < 2:
            ins.seek(-len(off)-2, 1)
            return -1
        else:
            return struct.unpack('<H', off)[0]

    def detokenise_compound_statement(self, ins, bytepos=None):
        """Detokenise tokens until end of line."""
        litstring, comment = False, False
        textpos = 0
        output = bytearray()
        while True:
            s = ins.read(1)
            if not textpos and ins.tell() >= bytepos:
                textpos = len(output)
            if s in tk.end_line:
                # \x00 ends lines and comments when listed,
                # if not inside a number constant
                # stream ended or end of line
                break
            elif s == '"':
                # start of literal string, passed verbatim
                # until a closing quote or EOL comes by
                # however number codes are *printed* as the corresponding numbers,
                # even inside comments & literals
                output += s
                litstring = not litstring
            elif s in tk.number:
                self._detokenise_number(ins, s, output)
            elif s in tk.linenum:
                # 0D: line pointer (unsigned int) - this token should not be here;
                #     interpret as line number and carry on
                # 0E: line number (unsigned int)
                output += struct.unpack('<H', s)[0]
            elif comment or litstring or ('\x20' <= s <= '\x7E'):
                # honest ASCII
                output += s
            elif s == '\x0A':
                # LF becomes LF CR
                output += '\x0A\x0D'
            elif s <= '\x09':
                # controls that do not double as tokens
                output += s
            else:
                ins.seek(-1, 1)
                comment = self._detokenise_keyword(ins, output)
        return output, textpos

    def _detokenise_keyword(self, ins, output):
        """Convert a one- or two-byte keyword token to ascii."""
        # try for single-byte token or two-byte token
        # if no match, first char is passed unchanged
        s = ins.read(1)
        try:
            keyword = self._token_to_keyword[s]
        except KeyError:
            s += util.peek(ins)
            try:
                keyword = self._token_to_keyword[s]
                ins.read(1)
            except KeyError:
                output += s[0]
                return False
        # when we're here, s is an actual keyword token.
        # letter or number followed by token is separated by a space
        if (output and chr(output[-1]) in (string.digits + string.ascii_letters) and s not in tk.operator):
            output += ' '
        output += keyword
        comment = False
        if keyword == "'":
            comment = True
        elif keyword == tk.KW_REM:
            nxt = ins.read(1)
            if nxt == '':
                pass
            elif nxt == tk.O_REM: # '
                # if next char is token('), we have the special value REM'
                # -- replaced by ' below.
                output += "'"
            else:
                # otherwise, it's part of the comment or an EOL or whatever,
                # pass back to stream so it can be processed
                ins.seek(-1, 1)
            comment = True
        # check for special cases
        #   [:REM']   ->  [']
        if len(output) > 4 and str(output[-5:]) == ":REM'":
            output[:] = output[:-5] + "'"
        #   [WHILE+]  ->  [WHILE]
        elif len(output) > 5 and str(output[-6:]) == 'WHILE+':
            output[:] = output[:-1]
        #   [:ELSE]  ->  [ELSE]
        # note that anything before ELSE gets cut off,
        # e.g. if we have 1ELSE instead of :ELSE it also becomes ELSE
        # SIC: len(output) > 4 and str(output[-4:])
        elif len(output) > 4 and str(output[-4:]) == tk.KW_ELSE:
            if (len(output) > 5 and chr(output[-5]) == ':' and
                        chr(output[-6]) in string.digits):
                output[:] = output[:-5] + ' ' + tk.KW_ELSE
            else:
                output[:] = output[:-5] + tk.KW_ELSE
        # token followed by token or number is separated by a space,
        # except operator tokens and SPC(, TAB(, FN, USR
        nxt = util.peek(ins)
        if (not comment and
                nxt not in tk.end_line + tk.operator +
                        (tk.O_REM, '"', ',', ';', ' ', ':', '(', ')', '$',
                         '%', '!', '#', '_', '@', '~', '|', '`') and
                s not in tk.operator + tk.with_bracket + (tk.USR, tk.FN)):
            # excluding TAB( SPC( and FN. \xD9 is ', \xD1 is FN, \xD0 is USR.
            output += ' '
        return comment

    def _detokenise_number(self, ins, lead, output):
        """Convert number token to Python string."""
        ntrail = tk.plus_bytes.get(lead, 0)
        trail = ins.read(ntrail)
        if len(trail) != ntrail:
            # not sure what GW does if the file is truncated here - we just stop
            return
        if lead == tk.T_OCT:
            output += b'&O' + values.integer_to_str_oct(self._values.from_bytes(trail))
            # not sure what GW does if the file is truncated here - we just stop
        elif lead == tk.T_HEX:
            output += b'&H' + values.integer_to_str_hex(self._values.from_bytes(trail))
        elif lead == tk.T_BYTE:
            output += str(ord(trail))
        elif tk.C_0 <= lead < tk.C_10:
            output += chr(ord(b'0') + ord(lead) - 0x11)
        elif lead == tk.C_10:
            output += b'10'
        elif lead == tk.T_INT:
            # lowercase h for signed int
            output += str(struct.unpack(b'<h', trail)[0])
        elif lead == tk.T_SINGLE:
            output += values.float_to_str(self._values.from_bytes(trail), screen=False, write=False)
        elif lead == tk.T_DOUBLE:
            output += values.float_to_str(self._values.from_bytes(trail), screen=False, write=False)
