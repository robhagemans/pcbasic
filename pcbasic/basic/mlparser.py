"""
PC-BASIC - mlparser.py
DRAW and PLAY macro language stream utilities

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string

from . import error
from . import values
from . import util


class MLParser(util.CodeStream):
    """Macro Language parser."""

    # whitespace character for both macro languages is only space
    blanks = ' '

    def __init__(self, gml, data_memory, values):
        """Initialise macro-language parser."""
        util.CodeStream.__init__(self, gml)
        self.memory = data_memory
        self.values = values

    def parse_value(self, default):
        """Parse a value in a macro-language string."""
        c = self.skip_blank()
        sgn = -1 if c == '-' else 1
        if c in ('+', '-'):
            self.read(1)
            c = self.peek()
            # don't allow default if sign is given
            default = None
        if c == '=':
            self.read(1)
            c = self.peek()
            if len(c) == 0:
                raise error.RunError(error.IFC)
            elif ord(c) > 8:
                name = self.read_name()
                indices = self._parse_indices()
                step = self.memory.get_variable(name, indices)
                self.require_read((';',), err=error.IFC)
            else:
                # varptr$
                step = self.memory.get_value_for_varptrstr(self.read(3))
        elif c and c in string.digits:
            step = self._parse_const()
        elif default is not None:
            step = default
        else:
            raise error.RunError(error.IFC)
        if sgn == -1:
            step = values.neg(step)
        return step

    def parse_number(self, default=None):
        """Parse and return a number value in a macro-language string."""
        try:
            return values.to_int(self.parse_value(default))
        except error.RunError as e:
            if e.err == error.TYPE_MISMATCH:
                e.err = error.IFC
            raise e

    def parse_string(self):
        """Parse a string value in a macro-language string."""
        c = self.skip_blank()
        if len(c) == 0:
            raise error.RunError(error.IFC)
        elif ord(c) > 8:
            try:
                name = self.read_name()
            except error.RunError as e:
                if e.err == error.STX:
                    e.err = error.IFC
                raise e
            indices = self._parse_indices()
            sub = self.memory.get_variable(name, indices)
            self.require_read((';',), err=error.IFC)
            return values.pass_string(sub, err=error.IFC).to_str()
        else:
            # varptr$
            ptr = self.memory.get_value_for_varptrstr(self.read(3))
            return values.pass_string(ptr).to_str()

    def _parse_const(self):
        """Parse and return a constant value in a macro-language string."""
        c = self.skip_blank()
        if c and c in string.digits:
            numstr = ''
            while c and c in string.digits:
                self.read(1)
                numstr += c
                c = self.skip_blank()
            return self.values.new_single().from_int(int(numstr))
        else:
            raise error.RunError(error.IFC)

    def _parse_const_int(self):
        """Parse a constant value in a macro-language string, return Python int."""
        try:
            return values.to_int(self._parse_const())
        except error.RunError as e:
            if e.err == error.TYPE_MISMATCH:
                e.err = error.IFC
            raise e

    def _parse_indices(self):
        """Parse constant array indices."""
        indices = []
        c = self.skip_blank()
        if c in ('[', '('):
            self.read(1)
            while True:
                indices.append(self._parse_const_int())
                c = self.skip_blank()
                if c == ',':
                    self.read(1)
                else:
                    break
            self.require_read((']', ')'))
        return indices
