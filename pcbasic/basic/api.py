"""
PC-BASIC - api.py
Session API

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os

from ..compat import text_type

from .base import error
from .devices import NameWrapper
from . import implementation

from ..data import read_codepage as codepage
from ..data import read_fonts as font
from .values import TYPE_TO_CLASS as SIGILS

#FIXME - should not be here
from .inputs.keyboard import MODIFIER as _MODS


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
        # if a file name, resolve
        if (
                not isinstance(file_name_or_object, (bytes, text_type))
                or os.path.isfile(file_name_or_object)
            ):
            # if it's an object or the file name exists, use it
            return self._impl.files.get_device(b'@:').bind(file_name_or_object, name)
        elif create and (
                not os.path.dirname(file_name_or_object) or
                os.path.isdir(os.path.dirname(file_name_or_object))
            ):
            # if it doesn't and we're allowed to create and the directory exists, create new
            return self._impl.files.get_device(b'@:').bind(file_name_or_object, name)
        # not resolved, try to use/create as internal name
        return NameWrapper(self._impl.codepage, file_name_or_object)

    def execute(self, command):
        """Execute a BASIC statement."""
        self.start()
        with self._impl.io_streams.activate():
            for cmd in command.splitlines():
                if isinstance(cmd, text_type):
                    cmd = self._impl.codepage.unicode_to_bytes(cmd)
                self._impl.execute(cmd)

    def evaluate(self, expression):
        """Evaluate a BASIC expression."""
        self.start()
        with self._impl.io_streams.activate():
            if isinstance(expression, text_type):
                expression = self._impl.codepage.unicode_to_bytes(expression)
            return self._impl.evaluate(expression)

    def set_variable(self, name, value):
        """Set a variable in memory."""
        self.start()
        if isinstance(name, text_type):
            name = name.encode('ascii')
        name = name.upper()
        if name.split(b'(')[0][-1:] not in SIGILS:
            raise ValueError('Sigil must be explicit')
        self._impl.set_variable(name, value)

    def get_variable(self, name, as_type=None):
        """Get a variable in memory."""
        self.start()
        if isinstance(name, text_type):
            name = name.encode('ascii')
        if name.split(b'(')[0][-1:] not in SIGILS:
            raise ValueError('Sigil must be explicit')
        return self._impl.get_variable(name, as_type)

    def convert(self, value, to_type):
        """Convert a Python value to another type, consistent with BASIC rules."""
        self.start()
        return self._impl.get_converter(type(value), to_type)(value)

    def press_keys(self, keys):
        """Insert keypresses."""
        self.start()
        if isinstance(keys, text_type):
            self._impl.keyboard.inject_keystrokes(keys)
        elif isinstance(keys, bytes):
            raise TypeError(
                'Key specification must be eascii in unicode, or sequence of scancodes; not bytes.'
            )
        else:
            with self._impl.keyboard.buf.ignore_limit():
                # must be a sequence type
                print(repr(keys))
                for keyspec in keys:
                    if isinstance(keyspec, int):
                        # single scancode
                        eascii, scancode, modifiers = u'', keyspec, set()
                    elif isinstance(keyspec, text_type):
                        # single eascii
                        eascii, scancode, modifiers = keyspec, None, set()
                    elif isinstance(keyspec, bytes):
                        raise TypeError('Key specification must not be bytes.')
                    else:
                        # combination
                        eascii, scancode, modifiers = u'', None, set()
                        for part in keyspec:
                            if isinstance(part, text_type) and not eascii:
                                eascii = part
                            elif isinstance(part, int):
                                if part in _MODS:
                                    modifiers.add(part)
                                elif not scancode:
                                    scancode = part
                                else:
                                    raise ValueError('Invalid key specification %r' % keyspec)
                            else:
                                raise TypeError(
                                    'Key specification must consist of int and unicode, not %s.'
                                    % type(part)
                                )
                    # fixme: private access
                    print(repr((eascii, scancode, modifiers)))
                    self._impl.keyboard._key_down(eascii, scancode, modifiers)
                    self._impl.keyboard._key_up(scancode)


    def get_chars(self, as_type=bytes):
        """Get currently displayed characters, as tuple of list of bytes / unicode."""
        self.start()
        return self._impl.text_screen.get_chars(as_type=as_type)

    def get_pixels(self):
        """Get currently displayed pixels, as tuple of tuples of int attributes."""
        self.start()
        return self._impl.display.vpage.pixels[:, :].to_rows()

    def greet(self):
        """Emit the interpreter greeting and show the key bar."""
        self.start()
        self._impl.execute(implementation.GREETING)

    def interact(self):
        """Interactive interpreter session."""
        self.start()
        with self._impl.io_streams.activate():
            self._impl.interact()

    def close(self):
        """Close the session."""
        if self._impl:
            self._impl.close()
