"""
PC-BASIC - extensions.py
Extension handler

(c) 2018--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
from importlib import import_module

from ..compat import text_type

from .base import error
from . import values


class Extensions(object):
    """Extension handler."""

    def __init__(self, extension, values, codepage):
        """Initialise extension handler."""
        # `extension` can be an iterable of extensions/names of extensions, just one extension,
        # or a name of an extension (as bytes or str)
        try:
            # test for being iterable
            iter(extension)
        except TypeError:
            extension = [extension]
        if isinstance(extension, (bytes, text_type)):
            extension = [extension]
        self._extension = list(extension)
        self._values = values
        self._codepage = codepage
        self._ext_funcs = None

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # modules can't be pickled
        pickle_dict['_ext_funcs'] = None
        pickle_dict['step'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)
        self.step = lambda: None

    def add(self, ext):
        """Add an extension."""
        self._extension.append(ext)
        # reset cache
        self._ext_funcs = None

    def _load_extensions(self):
        """Cache extension modules and objects."""
        if self._ext_funcs is not None:
            return
        if not self._extension:
            raise error.BASICError(error.STX)
        ext_objs = []
        for ext in self._extension:
            try:
                if isinstance(ext, (bytes, text_type)):
                    ext_objs.append(import_module(ext))
                else:
                    ext_objs.append(ext)
            except Exception as e:
                logging.error(u'Could not load extension module `%s`: %s', ext, repr(e))
                raise error.BASICError(error.INTERNAL_ERROR)
        self._ext_funcs = {
            n.upper().encode('ascii', 'ignore'): getattr(ext_obj, n)
            for ext_obj in ext_objs
            for n in dir(ext_obj) if not n.startswith('_')
        }

    def call_as_statement(self, args):
        """Extension statement: call a python function as a statement."""
        self._load_extensions()
        func_name = next(args)
        func_args = list(arg.to_value() for arg in args if arg is not None)
        try:
            result = self._ext_funcs[func_name](*func_args)
        except (error.Exit, error.Reset):
            raise
        except Exception as e:
            logging.error(u'Could not call extension function `%s%s`: %s', func_name, tuple(func_args), repr(e))
            raise error.BASICError(error.INTERNAL_ERROR)
        return result

    def call_as_function(self, args):
        """Extension function: call a python function as a function."""
        result = self.call_as_statement(args)
        if isinstance(result, text_type):
            return self._values.new_string().from_str(self._codepage.unicode_to_bytes(result))
        if isinstance(result, bytes):
            return self._values.from_value(result, values.STR)
        elif isinstance(result, bool):
            return self._values.from_bool(result)
        elif isinstance(result, int) or isinstance(result, float):
            return self._values.from_value(result, values.DBL)
        raise error.BASICError(error.TYPE_MISMATCH)
