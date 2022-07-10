"""
PC-BASIC - userfunctions.py
User-defined functions.

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from ...compat import int2byte, zip

from ..base import error
from ..base import codestream
from ..base import tokens as tk
from .. import values


class UserFunction(object):
    """User-defined function."""

    def __init__(self, name, code_stream, varnames, memory, expression_parser):
        """Define function."""
        self._codestream = code_stream
        self._start_loc = code_stream.tell()
        self._is_parsing = False
        self._memory = memory
        # if type not specified, it is evaluated at evaluation time, not at creation time
        self._varnames = varnames
        self._sigil = name[-1:]
        self._expression_parser = expression_parser

    def number_arguments(self):
        """Retrieve number of arguments."""
        return len(self._varnames)

    def evaluate(self, iargs):
        """Evaluate user-defined function."""
        # parse/evaluate arguments
        conversions = (values.TYPE_TO_CONV[self._memory.complete_name(name)[-1:]] for name in self._varnames)
        args = [conv(arg) for arg, conv in zip(iargs, conversions)]
        # recursion is not allowed as there's no way to terminate it
        if self._is_parsing:
            raise error.BASICError(error.OUT_OF_MEMORY)
        # parse/evaluate function expression
        # save existing vars
        varsave = {}
        varnames = [self._memory.complete_name(_v) for _v in self._varnames]
        for name in varnames:
            # set to 0 if they don't yet exist
            if name not in self._memory.scalars:
                self._memory.scalars.set(name)
            # copy the buffer
            varsave[name] = self._memory.scalars.view(name).clone()
        # set variables
        for name, value in zip(varnames, args):
            # append sigil, if missing
            name = self._memory.complete_name(name)
            self._memory.scalars.set(name, value)
        # set recursion flag
        self._is_parsing = True
        save_loc = self._codestream.tell()
        try:
            self._codestream.seek(self._start_loc)
            value = self._expression_parser.parse(self._codestream)
            return values.to_type(self._sigil, value)
        finally:
            self._codestream.seek(save_loc)
            # unset recursion flag
            self._is_parsing = False
            # restore existing vars, remove ones added
            for name in varsave:
                # re-assign the stored value
                self._memory.scalars.view(name).copy_from(varsave[name])



class UserFunctionManager(object):
    """User-defined function handler."""

    def __init__(self, memory, values, expression_parser):
        """Initialise functions."""
        self._fn_dict = {}
        # state variable for detecting recursion
        self._memory = memory
        self._values = values
        self._expression_parser = expression_parser

    def clear(self):
        """Clear all user-defined functions."""
        self._fn_dict.clear()

    def get(self, fnname):
        """Retrieve function by name."""
        # append sigil, if missing
        fnname = self._memory.complete_name(fnname)
        # parse/evaluate arguments
        try:
            fn = self._fn_dict[fnname]
        except KeyError:
            raise error.BASICError(error.UNDEFINED_USER_FUNCTION)
        if fn is None:
            raise error.BASICError(error.STX)
        return fn

    def define(self, fnname, ins):
        """Define a function."""
        ins.skip_blank()
        pointer_loc = self._memory.code_start + ins.tell()
        # read parameters
        fnvars = []
        if ins.skip_blank_read_if((b'(',)):
            while True:
                name = ins.read_name()
                # must not be empty
                error.throw_if(not name, error.STX)
                # do not append sigil here yet, leave until evaluation time
                fnvars.append(name)
                if ins.skip_blank() in tk.END_STATEMENT + (b')',):
                    break
                ins.require_read((b',',))
            ins.require_read((b')',))
        # read code
        if not ins.skip_blank_read_if((tk.O_EQ,)):
            self._fn_dict[fnname] = None
            return
        self._fn_dict[fnname] = UserFunction(fnname, ins, fnvars, self._memory, self._expression_parser)
        ins.skip_to(tk.END_STATEMENT)
        # update memory model
        # allocate function pointer
        pointer = struct.pack('<H', pointer_loc) + bytearray(values.size_bytes(fnname)-2)
        # function name is represented with first char shifted by 128
        memory_name = int2byte(128+ord(fnname[0:1])) + fnname[1:]
        self._memory.scalars.set(memory_name, self._values.from_bytes(pointer))
        for name in fnvars:
            # allocate, but don't set, variables
            # this is essential for them to be preserved during evaluate()
            name = self._memory.complete_name(name)
            self._memory.scalars.set(name)
