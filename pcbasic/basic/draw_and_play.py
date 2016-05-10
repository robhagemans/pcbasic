"""
PC-BASIC - draw_and_play.py
DRAW and PLAY macro language stream utilities

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string

from . import error
from . import vartypes
from .operators import Operators as op
from . import util


class MLParser(object):
    """ Macro Language parser. """

    # whitespace character for both macro languages is only space
    whitepace = ' '

    def __init__(self, gmls, data_memory):
        """ Initialise macro-language parser. """
        self.gmls = gmls
        self.memory = data_memory

    def parse_value(self, default):
        """ Parse a value in a macro-language string. """
        c = util.skip(self.gmls, self.whitepace)
        sgn = -1 if c == '-' else 1
        if c in ('+', '-'):
            self.gmls.read(1)
            c = util.peek(self.gmls)
            # don't allow default if sign is given
            default = None
        if c == '=':
            self.gmls.read(1)
            c = util.peek(self.gmls)
            if len(c) == 0:
                raise error.RunError(error.IFC)
            elif ord(c) > 8:
                name = util.read_name(self.gmls)
                indices = self._parse_indices()
                step = self.memory.get_variable(name, indices)
                util.require_read(self.gmls, (';',), err=error.IFC)
            else:
                # varptr$
                step = self.memory.get_value_for_varptrstr(self.gmls.read(3))
        elif c and c in string.digits:
            step = self._parse_const()
        elif default is not None:
            step = default
        else:
            raise error.RunError(error.IFC)
        if sgn == -1:
            step = op.number_neg(step)
        return step

    def parse_number(self, default=None):
        """ Parse and return a number value in a macro-language string. """
        return vartypes.pass_int_unpack(self.parse_value(default), err=error.IFC)

    def parse_string(self):
        """ Parse a string value in a macro-language string. """
        c = util.skip(self.gmls, self.whitepace)
        if len(c) == 0:
            raise error.RunError(error.IFC)
        elif ord(c) > 8:
            name = util.read_name(self.gmls, err=error.IFC)
            indices = self._parse_indices()
            sub = self.memory.get_variable(name, indices)
            util.require_read(self.gmls, (';',), err=error.IFC)
            return self.memory.strings.copy(vartypes.pass_string(sub, err=error.IFC))
        else:
            # varptr$
            return self.memory.strings.copy(
                    vartypes.pass_string(
                        self.memory.get_value_for_varptrstr(self.gmls.read(3))))

    def _parse_const(self):
        """ Parse and return a constant value in a macro-language string. """
        c = util.skip(self.gmls, self.whitepace)
        if c and c in string.digits:
            numstr = ''
            while c and c in string.digits:
                self.gmls.read(1)
                numstr += c
                c = util.skip(self.gmls, self.whitepace)
            return vartypes.int_to_integer_signed(int(numstr))
        else:
            raise error.RunError(error.IFC)

    def _parse_const_int(self):
        """ Parse a constant value in a macro-language string, return Python int. """
        return vartypes.pass_int_unpack(self._parse_const(), err=error.IFC)

    def _parse_indices(self):
        """ Parse constant array indices. """
        indices = []
        c = util.skip(self.gmls, self.whitepace)
        if c in ('[', '('):
            self.gmls.read(1)
            while True:
                indices.append(self._parse_const_int())
                c = util.skip(self.gmls, self.whitepace)
                if c == ',':
                    self.gmls.read(1)
                else:
                    break
            util.require_read(self.gmls, (']', ')'))
        return indices
