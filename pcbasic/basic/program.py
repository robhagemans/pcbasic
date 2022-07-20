"""
PC-BASIC - program.py
Program buffer utilities

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import binascii
import logging
import struct
import io

from ..compat import int2byte

from .base import error
from .base import tokens as tk
from . import values
from . import converter


class Program(object):
    """BASIC program."""

    def __init__(self, tokeniser, lister, hide_listing,
                allow_protect, allow_code_poke, memory, bytecode, rebuild_offsets):
        """Initialise program."""
        self._memory = memory
        # program bytecode buffer
        self.bytecode = bytecode
        self.erase()
        self.max_list_line = hide_listing if hide_listing else 65535
        self.allow_protect = allow_protect
        self.allow_code_poke = allow_code_poke
        self._rebuild_offsets = rebuild_offsets
        # to be set when file memory is initialised
        self.code_start = memory.code_start
        # for detokenise_line()
        self.tokeniser = tokeniser
        self.lister = lister

    def __repr__(self):
        """Return a marked-up hex dump of the program (for debugging)."""
        code = self.bytecode.getvalue()
        offset_val, p = 0, 0
        output = []
        for key in sorted(self.line_numbers.keys())[1:]:
            offset, linum = code[p+1:p+3], code[p+3:p+5]
            last_offset = offset_val
            offset_val = struct.unpack('<H', offset)[0] - (self.code_start + 1)
            linum_val, = struct.unpack('<H', linum)
            output.append('%s %s (+%03d) %s [%05d] %s' % (
                binascii.hexlify(code[p:p+1]),
                binascii.hexlify(offset),
                offset_val - last_offset,
                binascii.hexlify(code[p+3:p+5]),
                linum_val,
                binascii.hexlify(code[p+5:])
            ))
            p = self.line_numbers[key]
        output.append('%s %s (ENDS) %s %s' % (
            binascii.hexlify(code[p:p+1]),
            binascii.hexlify(code[p+1:p+3]),
            binascii.hexlify(code[p+3:p+5]),
            binascii.hexlify(code[p+5:])
        ))
        return '\n'.join(output)

    def size(self):
        """Size of code space """
        return self.code_size

    def erase(self):
        """Erase the program from memory."""
        self.bytecode.seek(0)
        self.bytecode.write(b'\0\0\0')
        self.protected = False
        self.line_numbers = {65536: 0}
        self.last_stored = None
        self.code_size = self.bytecode.tell()
        self.bytecode.truncate()

    def truncate(self, rest=b''):
        """Write bytecode and cut the program of beyond the current position."""
        self.bytecode.write(rest if rest else b'\0\0\0')
        self.bytecode.truncate()
        # cut off at current position
        self.code_size = self.bytecode.tell()

    def explicit_lines(self, *line_range):
        """Convert iterables of lines with '.' into explicit numbers."""
        return (self.last_stored if l == b'.' else l for l in line_range)

    def get_line_number(self, pos):
        """Get line number for stream position."""
        pre = -1
        if pos is None:
            pos = -1
        for linum in self.line_numbers:
            linum_pos = self.line_numbers[linum]
            if linum_pos <= pos and linum > pre:
                pre = linum
        return pre

    def rebuild_line_dict(self):
        """Preparse to build line number dictionary."""
        self.line_numbers, offsets = {}, []
        self.bytecode.seek(0)
        scanline, scanpos, last = 0, 0, 0
        while True:
            # pass \x00
            self.bytecode.read(1)
            scanline = self.lister.detokenise_line_number(self.bytecode)
            if scanline == -1:
                scanline = 65536
                # if detokenise_line_number returns -1, it leaves the stream pointer here:
                # 00 _00_ 00 1A
                break
            self.line_numbers[scanline] = scanpos
            last = scanpos
            self.bytecode.skip_to(tk.END_LINE)
            scanpos = self.bytecode.tell()
            offsets.append(scanpos)
        self.line_numbers[65536] = scanpos
        # rebuild offsets
        if self._rebuild_offsets:
            self.bytecode.seek(0)
            last = 0
            for pos in offsets:
                self.bytecode.read(1)
                self.bytecode.write(struct.pack('<H', self.code_start + 1 + pos))
                self.bytecode.read(pos - last - 3)
                last = pos
            # ensure program is properly sealed - last offset must be 00 00.
            # keep, but ignore, anything after.
            self.bytecode.write(b'\0\0\0')

    def update_line_dict(self, pos, afterpos, length, deleteable, beyond):
        """Update line number dictionary after deleting lines."""
        # subtract length of line we replaced
        length -= afterpos - pos
        addr = (self.code_start + 1) + afterpos
        self.bytecode.seek(afterpos + length + 1)  # pass \x00
        while True:
            next_addr = self.bytecode.read(2)
            if len(next_addr) < 2 or next_addr == b'\0\0':
                break
            next_addr, = struct.unpack('<H', next_addr)
            self.bytecode.seek(-2, 1)
            self.bytecode.write(struct.pack('<H', next_addr + length))
            self.bytecode.read(next_addr - addr - 2)
            addr = next_addr
        # update line number dict
        for key in deleteable:
            del self.line_numbers[key]
        for key in beyond:
            self.line_numbers[key] += length

    def check_number_start(self, linebuf):
        """Check if the given line buffer starts with a line number."""
        # get the new line number
        linebuf.seek(1)
        scanline = self.lister.detokenise_line_number(linebuf)
        c = linebuf.skip_blank_read()
        # check if linebuf is an empty line after the line number
        empty = (c in tk.END_LINE)
        # check if we start with a number
        if c in tk.NUMBER:
            raise error.BASICError(error.STX)
        return empty, scanline

    def store_line(self, linebuf):
        """Store the given line buffer."""
        if self.protected:
            raise error.BASICError(error.IFC)
        # get the new line number
        linebuf.seek(1)
        scanline = self.lister.detokenise_line_number(linebuf)
        # check if linebuf is an empty line after the line number
        empty = (linebuf.skip_blank_read() in tk.END_LINE)
        pos, afterpos, deleteable, beyond = self.find_pos_line_dict(scanline, scanline)
        if empty and not deleteable:
            raise error.BASICError(error.UNDEFINED_LINE_NUMBER)
        # read the remainder of the program into a buffer to be pasted back after the write
        self.bytecode.seek(afterpos)
        rest = self.bytecode.read()
        # insert
        self.bytecode.seek(pos)
        # write the line buffer to the program buffer
        length = 0
        if not empty:
            # set offsets
            linebuf.seek(3) # pass \x00\xC0\xDE
            length = len(linebuf.getvalue())
            # check for free memory
            # variables are cleared upon program code storage
            if self.code_start + 1 + pos + length > self._memory.stack_start():
                raise error.BASICError(error.OUT_OF_MEMORY)
            self.bytecode.write(
                struct.pack('<BH', 0, self.code_start + 1 + pos + length) + linebuf.read()
            )
        # write back the remainder of the program
        self.truncate(rest)
        # update all next offsets by shifting them by the length of the added line
        self.update_line_dict(pos, afterpos, length, deleteable, beyond)
        if not empty:
            self.line_numbers[scanline] = pos
        self.last_stored = scanline

    def find_pos_line_dict(self, fromline, toline):
        """Find code positions for line range."""
        deleteable = [ num for num in self.line_numbers if num >= fromline and num <= toline ]
        beyond = [num for num in self.line_numbers if num > toline ]
        # find lowest number strictly above range
        afterpos = self.line_numbers[min(beyond)]
        # find lowest number within range
        try:
            startpos = self.line_numbers[min(deleteable)]
        except ValueError:
            startpos = afterpos
        return startpos, afterpos, deleteable, beyond

    def delete(self, fromline, toline):
        """Delete range of lines from stored program."""
        fromline, toline = self.explicit_lines(fromline, toline)
        fromline = fromline if fromline is not None else min(self.line_numbers)
        toline = toline if toline is not None else 65535
        startpos, afterpos, deleteable, beyond = self.find_pos_line_dict(fromline, toline)
        if not deleteable:
            # no lines selected
            raise error.BASICError(error.IFC)
        # do the delete
        self.bytecode.seek(afterpos)
        rest = self.bytecode.read()
        self.bytecode.seek(startpos)
        self.truncate(rest)
        # update line number dict
        self.update_line_dict(startpos, afterpos, 0, deleteable, beyond)

    def edit(self, console, from_line, target_bytepos):
        """Output program line to console and position cursor."""
        if self.protected:
            console.write(b'%d\r' % (from_line,))
            raise error.BASICError(error.IFC)
        # list line
        self.bytecode.seek(self.line_numbers[from_line]+1)
        _, output, byte_to_text_positions = self.lister.detokenise_line(self.bytecode)
        # find text position from byte position
        if target_bytepos is None:
            textpos = None
        else:
            textpos = min(
                _textpos
                for _bytepos, _textpos in byte_to_text_positions
                if target_bytepos <= _bytepos
            )
        # no newline to avoid scrolling on line 24
        console.list_line(bytes(output), newline=False, set_text_position=textpos)

    def renum(self, console, new_line, start_line, step):
        """Renumber stored program."""
        new_line = 10 if new_line is None else new_line
        start_line = 0 if start_line is None else start_line
        step = 10 if step is None else step
        # ensure we're not about to overwrite anything
        remaining = [_k for _k in self.line_numbers.keys() if _k < start_line]
        if remaining and new_line <= max(remaining):
            raise error.BASICError(error.IFC)
        # get a sorted list of line numbers
        # assign the new numbers
        old_to_new = {}
        for old_line in sorted(_k for _k in self.line_numbers.keys() if _k >= start_line):
            if old_line < 65535 and new_line > 65529:
                raise error.BASICError(error.IFC)
            if old_line == 65536:
                break
            old_to_new[old_line] = new_line
            self.last_stored = new_line
            new_line += step
        # write the new numbers
        for old_line in old_to_new:
            self.bytecode.seek(self.line_numbers[old_line])
            # skip the \x00\xC0\xDE & overwrite line number
            self.bytecode.read(3)
            self.bytecode.write(struct.pack('<H', old_to_new[old_line]))
        # write the indirect line numbers
        ins = self.bytecode
        ins.seek(0)
        while ins.skip_to_read((tk.T_UINT,)) == tk.T_UINT:
            # get the old g number
            token = ins.read(2)
            jumpnum, = struct.unpack('<H', token)
            # handle exception for ERROR GOTO
            if jumpnum == 0:
                pos = ins.tell()
                # skip line number token
                ins.seek(-3, 1)
                if ins.backskip_blank() == tk.GOTO and ins.backskip_blank() == tk.ERROR:
                    ins.seek(pos)
                    continue
                ins.seek(pos)
            try:
                newjump = old_to_new[jumpnum]
            except KeyError:
                # not redefined, exists in program?
                if jumpnum not in self.line_numbers:
                    linum = self.get_line_number(ins.tell()-1)
                    console.write_line(b'Undefined line %d in %d' % (jumpnum, linum))
                newjump = jumpnum
            ins.seek(-2, 1)
            ins.write(struct.pack('<H', newjump))
        # rebuild the line number dictionary
        new_lines = {}
        for old_line in old_to_new:
            new_lines[old_to_new[old_line]] = self.line_numbers[old_line]
            del self.line_numbers[old_line]
        self.line_numbers.update(new_lines)
        return old_to_new

    def load(self, g):
        """Load program from ascii, bytecode or protected stream."""
        self.erase()
        if g.filetype == b'B':
            # bytecode file
            self.bytecode.seek(1)
            self.bytecode.write(g.read())
        elif g.filetype == b'P':
            # protected file
            self.bytecode.seek(1)
            self.protected = self.allow_protect
            converter.unprotect(g, self.bytecode)
        elif g.filetype == b'A':
            # assume ASCII file
            # erase() only writes the terminator
            # so we need to get rid of the old code which is still in memory
            # or it'll end up after the new code in memory
            self.bytecode.truncate()
            # anything but numbers or whitespace: Direct Statement in File
            self.merge(g)
        else:
            logging.debug('Incorrect file type `%s` on LOAD', g.filetype)
        # rebuild line number dict and offsets
        if g.filetype != b'A':
            self.rebuild_line_dict()
        self.code_size = self.bytecode.tell()

    def merge(self, g):
        """Merge program from ascii or utf8 (if utf8_files is True) stream."""
        while True:
            line, cr = g.read_line()
            if not line and not cr:
                # end of file
                break
            elif cr is None:
                # line > 255 chars
                raise error.BASICError(error.LINE_BUFFER_OVERFLOW)
            linebuf = self.tokeniser.tokenise_line(line)
            if linebuf.read(1) == b'\0':
                # line starts with a number, add to program memory; store_line seeks to 1 first
                self.store_line(linebuf)
            else:
                # we have read the :
                if linebuf.skip_blank() not in tk.END_LINE:
                    raise error.BASICError(error.DIRECT_STATEMENT_IN_FILE)

    def save(self, g):
        """Save the program to stream g in (A)scii, (B)ytecode or (P)rotected mode."""
        mode = g.filetype
        if self.protected and mode != b'P':
            raise error.BASICError(error.IFC)
        current = self.bytecode.tell()
        # skip first \x00 in bytecode
        self.bytecode.seek(1)
        if mode == b'B':
            # binary bytecode mode
            g.write(self.bytecode.read())
        elif mode == b'P':
            # protected mode
            converter.protect(self.bytecode, g)
        else:
            # ascii mode
            while True:
                current_line, output, _ = self.lister.detokenise_line(self.bytecode)
                if current_line == -1 or (current_line > self.max_list_line):
                    break
                g.write_line(bytes(output))
        self.bytecode.seek(current)

    def list_lines(self, from_line, to_line):
        """List line range."""
        from_line, to_line = self.explicit_lines(from_line, to_line)
        if self.protected:
            # don't list protected files
            raise error.BASICError(error.IFC)
        # 65529 is max insertable line number for GW-BASIC 3.23.
        # however, 65530-65535 are executed if present in tokenised form.
        # in GW-BASIC, 65530 appears in LIST, 65531 and above are hidden
        if to_line is None:
            to_line = self.max_list_line
        numbers = [
            num for num in self.line_numbers
            if (from_line is None or num >= from_line) and num <= to_line
        ]
        # sort by positions, not line numbers!
        listable = sorted([self.line_numbers[num] for num in numbers])
        if numbers:
            self.last_stored = max(numbers)
        lines = []
        for pos in listable:
            self.bytecode.seek(pos + 1)
            _, line, _ = self.lister.detokenise_line(self.bytecode)
            lines.append(bytes(line))
        return lines

    def get_memory(self, offset):
        """Retrieve data from program code."""
        offset -= self.code_start
        code = self.bytecode.getvalue()
        try:
            return ord(code[offset:offset+1])
        except IndexError:
            return -1

    def get_memory_block(self, offset, length):
        """Retrieve block of data from program code."""
        offset -= self.code_start
        code = self.bytecode.getvalue()
        return bytearray(code[offset:offset+length])

    def set_memory(self, offset, val):
        """Change program code."""
        if not self.allow_code_poke:
            logging.warning('Ignored POKE into program code')
        else:
            offset -= self.code_start
            loc = self.bytecode.tell()
            # move pointer to end
            self.bytecode.seek(0, 2)
            if offset > self.bytecode.tell():
                self.bytecode.write(b'\0' * (offset-self.bytecode.tell()))
            else:
                self.bytecode.seek(offset)
            self.bytecode.write(int2byte(val))
            self.bytecode.seek(0, 2)
            self.rebuild_line_dict()
            # restore program pointer
            self.bytecode.seek(loc)
