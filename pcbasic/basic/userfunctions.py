"""
PC-BASIC - userfunctions.py
User-defined functions.

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from . import error
from . import codestream
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
        if ins.skip_blank_read_if(('(',)):
            while True:
                fnvars.append(parser.parse_scalar(ins))
                if ins.skip_blank() in tk.END_STATEMENT + (')',):
                    break
                ins.require_read((',',))
            ins.require_read((')',))
        # read code
        fncode = ''
        ins.require_read((tk.O_EQ,)) #=
        startloc = ins.tell()
        ins.skip_to(tk.END_STATEMENT)
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
        if ins.skip_blank_read_if(('(',)):
            exprs = []
            while True:
                exprs.append(parser.parse_expression(ins))
                if not ins.skip_blank_read_if((',',)):
                    break
            if len(exprs) != len(varnames):
                raise error.RunError(error.STX)
            for name, value in zip(varnames, exprs):
                self._scalars.set(name, value)
            ins.require_read((')',))
        # execute the code
        fns = codestream.TokenisedStream(fncode)
        fns.seek(0)
        self._parsing.add(fnname)
        try:
            value = parser.parse_expression(fns)
            return values.to_type(fnname[-1], value)
        finally:
            self._parsing.remove(fnname)
            # restore existing vars
            for name in varsave:
                # re-assign the stored value
                self._scalars.view(name).copy_from(varsave[name])
