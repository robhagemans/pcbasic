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

    def __init__(self, program, memory, scalars, values):
        """Initialise functions."""
        self._code = {}
        # state variable for detecting recursion
        self._parsing = set()
        self._program = program
        self._memory = memory
        self._scalars = scalars
        self._values = values

    def define(self, fnname, ins):
        """Define a function."""
        pointer_loc = self._memory.code_start + ins.tell()
        fntype = fnname[-1]
        # read parameters
        fnvars = []
        if ins.skip_blank_read_if(('(',)):
            while True:
                name = ins.read_name()
                # must not be empty
                error.throw_if(not name, error.STX)
                # do not append sigil here yet, level until evaluation time
                fnvars.append(name)
                if ins.skip_blank() in tk.END_STATEMENT + (')',):
                    break
                ins.require_read((',',))
            ins.require_read((')',))
        # read code
        ins.require_read((tk.O_EQ,)) #=
        self._code[fnname] = fnvars, ins.tell()
        ins.skip_to(tk.END_STATEMENT)
        # update memory model
        # allocate function pointer
        pointer = struct.pack('<H', pointer_loc) + bytearray(values.size_bytes(fntype)-2)
        # function name is represented with first char shifted by 128
        self._scalars.set(chr(128+ord(fnname[0])) + fnname[1:], self._values.from_bytes(pointer))
        for name in fnvars:
            # allocate but don't set variables
            name = self._memory.complete_name(name)
            self._scalars.set(name)

    def value(self, fnname, functions, ins):
        """Parse a function."""
        # parse/evaluate arguments
        try:
            varnames, start_loc = self._code[fnname]
        except KeyError:
            raise error.RunError(error.UNDEFINED_USER_FUNCTION)
        # read variables
        conversions = [values.TYPE_TO_CONV[self._memory.complete_name(name)[-1]] for name in varnames]
        if conversions:
            args = functions.parse_argument_list(ins, conversions, optional=False)
        else:
            args = ()
        # recursion is not allowed as there's no way to terminate it
        if fnname in self._parsing:
            raise error.RunError(error.OUT_OF_MEMORY)
        # parse/evaluate function expression
        # save existing vars
        varsave = {}
        for name in varnames:
            if name in self._scalars:
                # copy the buffer
                varsave[name] = self._scalars.view(name).clone()
        # set variables
        for name, value in zip(varnames, args):
            # append sigil, if missing
            name = self._memory.complete_name(name)
            self._scalars.set(name, value)
        # set recursion flag
        self._parsing.add(fnname)
        save_loc = self._program.bytecode.tell()
        try:
            self._program.bytecode.seek(start_loc)
            value = functions.parse_expression(self._program.bytecode)
            return values.to_type(fnname[-1], value)
        finally:
            self._program.bytecode.seek(save_loc)
            # unset recursion flag
            self._parsing.remove(fnname)
            # restore existing vars
            for name in varsave:
                # re-assign the stored value
                self._scalars.view(name).copy_from(varsave[name])
