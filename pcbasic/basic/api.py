"""
PC-BASIC - api.py
Session API

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import Queue
import os

from .base import error
from .devices import NameWrapper
from . import implementation


class Session(object):
    """Public API to BASIC session."""

    def __init__(self, interface=None, **kwargs):
        """Set up session object."""
        self.interface = interface
        self._kwargs = kwargs
        self._impl = None

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, ex_type, ex_val, tb):
        """Context guard."""
        self.close()
        # catch Exit and Break events
        if ex_type in (error.Exit, error.Break):
            return True

    def __getstate__(self):
        """Pickle the session."""
        pickle_dict = self.__dict__.copy()
        pickle_dict['interface'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle and resume the session."""
        self.__dict__.update(pickle_dict)

    def start(self):
        """Start the session."""
        if not self._impl:
            self._impl = implementation.Implementation(**self._kwargs)
            self._impl.attach_interface(self.interface)

    def attach(self, interface=None):
        """Attach interface to interpreter session."""
        self.start()
        self.interface = interface
        self._impl.attach_interface(interface)
        return self

    def bind_file(self, file_name_or_object, name=None, create=False):
        """Bind a native file name or Python stream to a BASIC file name."""
        self.start()
        if isinstance(name, unicode):
            name = self._impl.codepage.str_from_unicode(name)
        # if a file name, resolve
        if not isinstance(file_name_or_object, basestring) or os.path.isfile(file_name_or_object):
            # if it's an obkect or the file name exists, use it
            return self._impl.files.get_device(b'@:').bind(file_name_or_object, name)
        elif create and (
                not os.path.dirname(file_name_or_object) or
                os.path.isdir(os.path.dirname(file_name_or_object))):
            # if it doesn't and we're allowed to create and the directory exists, create new
            return self._impl.files.get_device(b'@:').bind(file_name_or_object, name)
        # not resolved, try to use/create as internal name
        if isinstance(file_name_or_object, unicode):
            return NameWrapper(self._impl.codepage.str_from_unicode(file_name_or_object))
        return NameWrapper(file_name_or_object)

    def execute(self, command):
        """Execute a BASIC statement."""
        self.start()
        with self._impl.io_streams.activate():
            for cmd in command.splitlines():
                if isinstance(cmd, unicode):
                    cmd = self._impl.codepage.str_from_unicode(cmd)
                self._impl.execute(cmd)

    def evaluate(self, expression):
        """Evaluate a BASIC expression."""
        self.start()
        with self._impl.io_streams.activate():
            if isinstance(expression, unicode):
                expression = self._impl.codepage.str_from_unicode(expression)
            return self._impl.evaluate(expression)

    def set_variable(self, name, value):
        """Set a variable in memory."""
        self.start()
        if isinstance(name, unicode):
            name = name.encode('ascii')
        name = name.upper()
        self._impl.set_variable(name, value)

    def get_variable(self, name):
        """Get a variable in memory."""
        self.start()
        if isinstance(name, unicode):
            name = name.encode('ascii')
        return self._impl.get_variable(name)

    def interact(self):
        """Interactive interpreter session."""
        self.start()
        with self._impl.io_streams.activate():
            self._impl.interact()

    def close(self):
        """Close the session."""
        if self._impl:
            self._impl.close()
