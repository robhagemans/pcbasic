"""
PC-BASIC - mlparser.py
DRAW and PLAY macro language stream utilities

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..compat import iterchar
from .base import error
from .base import codestream
from .base.tokens import DIGITS
from . import values


class MLParser(codestream.CodeStream):
    """Macro Language parser."""

    # whitespace character for both macro languages is only space
    blanks = b' '

    def __init__(self, gml, data_memory, values):
        """Initialise macro-language parser."""
        codestream.CodeStream.__init__(self, gml)
        self.memory = data_memory
        self.values = values

    def parse_number(self, default=None):
        """Parse a value in a macro-language string."""
        c = self.skip_blank()
        sgn = -1 if c == b'-' else 1
        if c in (b'+', b'-'):
            self.read(1)
            c = self.peek()
            # don't allow default if sign is given
            default = None
        if c == b'=':
            self.read(1)
            c = self.peek()
            if len(c) == 0:
                raise error.BASICError(error.IFC)
            elif ord(c) > 8:
                stepval = self._parse_variable()
                step = values.pass_number(stepval).to_int()
                self.require_read((b';',), err=error.IFC)
            else:
                # varptr$
                stepval = self.memory.get_value_for_varptrstr(self.read(3))
                step = values.pass_number(stepval).to_int()
        elif c and c in DIGITS:
            step = self._parse_literal()
        elif default is not None:
            step = default
        else:
            raise error.BASICError(error.IFC)
        if sgn == -1:
            step = -step  # pylint: disable=invalid-unary-operand-type
        return step

    def parse_string(self):
        """Parse a string value in a macro-language string."""
        c = self.skip_blank()
        if len(c) == 0:
            raise error.BASICError(error.IFC)
        elif ord(c) > 8:
            sub = self._parse_variable()
            self.require_read((b';',), err=error.IFC)
            return values.pass_string(sub).to_str()
        else:
            # varptr$
            ptr = self.memory.get_value_for_varptrstr(self.read(3))
            return values.pass_string(ptr).to_str()

    def _parse_variable(self):
        """Parse and return a named variable."""
        name = self.read_name()
        error.throw_if(not name)
        indices = self._parse_indices()
        return self.memory.view_or_create_variable(name, indices)

    def _parse_literal(self):
        """Parse and return a literal value in a macro-language string."""
        digits = []
        while self.skip_blank() in set(iterchar(DIGITS)):
            digits.append(self.read(1))
        # we only have digits in here so no need to catch ValueError
        return int(b''.join(digits))

    def _parse_indices(self):
        """Parse constant array indices."""
        indices = []
        if self.skip_blank_read_if((b'[', b'(')):
            while True:
                if self.skip_blank() in set(iterchar(DIGITS)):
                    indices.append(self._parse_literal())
                else:
                    indices.append(self._parse_variable().to_int())
                if not self.skip_blank_read_if((b',',)):
                    break
            self.require_read((b']', b')'))
        return indices
