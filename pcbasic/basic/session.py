"""
PC-BASIC - session.py
Session API

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
import Queue

from .base import error
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
        self.start()
        return self

    def __exit__(self, ex_type, ex_val, tb):
        """Context guard."""
        self.close()
        # catch Exit and Break events
        if ex_type in (error.Exit, error.Break):
            return True

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

    def bind_file(self, file_name_or_object, name=None):
        """Bind a native file name or Python stream to a BASIC file name."""
        self.start()
        return self._impl.bind_file(file_name_or_object, name)

    def execute(self, command):
        """Execute a BASIC statement."""
        self.start()
        for cmd in command.splitlines():
            if isinstance(cmd, unicode):
                cmd = self._impl.codepage.str_from_unicode(cmd)
            self._impl.execute(cmd)

    def evaluate(self, expression):
        """Evaluate a BASIC expression."""
        self.start()
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
        self._impl.interact()

    def close(self):
        """Close the session."""
        if self._impl:
            self._impl.close()
