"""
PC-BASIC - userfunctions.py
User-defined functions.

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from . import error
from . import util
from . import values
from . import tokens as tk

class UserFunctions(object):
    """User-defined functions."""

    def __init__(self, scalars, values):
        """Initialise functions."""
        self._code = {}
        # state variable for detecting recursion
        self._parsing = set()
        self._scalars = scalars
        self._values = values

    def define(self, fnname, parser, ins, pointer_loc):
        """Define a function."""
        fntype = fnname[-1]
        # read parameters
        fnvars = []
        if util.skip_white_read_if(ins, ('(',)):
            while True:
                fnvars.append(parser.parse_scalar(ins))
                if util.skip_white(ins) in tk.end_statement + (')',):
                    break
                util.require_read(ins, (',',))
            util.require_read(ins, (')',))
        # read code
        fncode = ''
        util.require_read(ins, (tk.O_EQ,)) #=
        startloc = ins.tell()
        util.skip_to(ins, tk.end_statement)
        endloc = ins.tell()
        ins.seek(startloc)
        fncode = ins.read(endloc - startloc)
        if not parser.run_mode:
            # GW doesn't allow DEF FN in direct mode, neither do we
            # (for no good reason, works fine)
            raise error.RunError(error.ILLEGAL_DIRECT)
        self._code[fnname] = fnvars, fncode
        # update memory model
        # allocate function pointer
        pointer = struct.pack('<H', pointer_loc) + bytearray(values.size_bytes(fntype)-2)
        # function name is represented with first char shifted by 128
        self._scalars.set(chr(128+ord(fnname[0])) + fnname[1:], self._values.from_bytes(pointer))
        for name in fnvars:
            # allocate but don't set variables
            self._scalars.set(name)

    def value(self, fnname, parser, ins):
        """Parse a function."""
        # recursion is not allowed as there's no way to terminate it
        if fnname in self._parsing:
            raise error.RunError(error.OUT_OF_MEMORY)
        try:
            varnames, fncode = self._code[fnname]
        except KeyError:
            raise error.RunError(error.UNDEFINED_USER_FUNCTION)
        # save existing vars
        varsave = {}
        for name in varnames:
            if name in self._scalars:
                # copy the buffer
                varsave[name] = self._scalars.view(name).clone()
        # read variables
        if util.skip_white_read_if(ins, ('(',)):
            exprs = []
            while True:
                exprs.append(parser.parse_expression(ins))
                if not util.skip_white_read_if(ins, (',',)):
                    break
            if len(exprs) != len(varnames):
                raise error.RunError(error.STX)
            for name, value in zip(varnames, exprs):
                self._scalars.set(name, value)
            util.require_read(ins, (')',))
        # execute the code
        fns = util.TokenisedStream(fncode)
        fns.seek(0)
        self._parsing.add(fnname)
        value = parser.parse_expression(fns)
        self._parsing.remove(fnname)
        # restore existing vars
        for name in varsave:
            # re-assign the stored value
            self._scalars.view(name).copy_from(varsave[name])
        return values.to_type(fnname[-1], value)
