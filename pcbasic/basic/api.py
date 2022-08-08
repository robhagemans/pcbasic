"""
PC-BASIC - api.py
Session API

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import io

from ..compat import text_type

from .base import error
from .devices import NameWrapper
from . import implementation
from . import state

from ..data import read_codepage as codepage
from ..data import read_fonts as font
from .values import TYPE_TO_CLASS as SIGILS


class Session(object):
    """Public API to BASIC session."""

    def __init__(self, **kwargs):
        """Set up session object."""
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
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle and resume the session."""
        self.__dict__.update(pickle_dict)

    def start(self):
        """Start the session."""
        if not self._impl:
            self._impl = implementation.Implementation(**self._kwargs)
            return True
        return False

    def attach(self, interface=None):
        """Attach interface to interpreter session."""
        self.start()
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

    def execute(self, command, as_type=None):
        """Execute a BASIC statement."""
        self.start()
        if as_type is None:
            as_type = type(command)
        output = io.BytesIO() if as_type == bytes else io.StringIO()
        with self._impl.io_streams.activate():
            self._impl.io_streams.toggle_echo(output)
            for cmd in command.splitlines():
                if isinstance(cmd, text_type):
                    cmd = self._impl.codepage.unicode_to_bytes(cmd)
                self._impl.execute(cmd)
            self._impl.io_streams.toggle_echo(output)
        return output.getvalue()

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
        self._impl.keyboard.inject_keystrokes(keys)

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

    def suspend(self, session_filename):
        """Save session object to file."""
        state.save_session(self, session_filename)

    @classmethod
    def resume(self, session_filename):
        """Load new session object from file."""
        return state.load_session(session_filename)

    def close(self):
        """Close the session."""
        if self._impl:
            self._impl.close()

    @property
    def info(self):
        """Get a session information object."""
        self.start()
        return SessionInfo(self)

    def set_hook(self, step_function):
        """Set function to be called on interpreter step."""
        self.start()
        self._impl.interpreter.step = step_function


class SessionInfo(object):
    """Retrieve information about current session."""

    def __init__(self, session):
        """Initialise the SessionInfo object."""
        self._session = session
        self._impl = session._impl

    def repr_scalars(self):
        """Get a representation of all scalars."""
        return repr(self._impl.scalars)

    def repr_arrays(self):
        """Get a representation of all arrays."""
        return repr(self._impl.scalars)

    def repr_strings(self):
        """Get a representation of string space."""
        return repr(self._impl.strings)

    def repr_text_screen(self):
        """Get a representation of the text screen."""
        return repr(self._impl.display.text_screen)

    def repr_program(self):
        """Get a marked-up hex dump of the program."""
        return repr(self._impl.program)

    def get_current_code(self, as_type=bytes):
        """Obtain statement being executed."""
        if self._impl.interpreter.run_mode:
            codestream = self._impl.program.bytecode
            bytepos = codestream.tell()
            from_line = self._impl.program.get_line_number(bytepos-1)
            try:
                codestream.seek(self._impl.program.line_numbers[from_line]+1)
                _, output, _ = self._impl.lister.detokenise_line(codestream)
                code_line = bytes(output)
            except KeyError:
                code_line = b''
        else:
            codestream = self._impl.interpreter.direct_line
            bytepos = codestream.tell()
            codestream.seek(0)
            code_line = bytes(
                self._impl.lister.detokenise_compound_statement(codestream)[0]
            )
        codestream.seek(bytepos)
        return self._session.convert(code_line, as_type)
