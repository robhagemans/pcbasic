"""
PC-BASIC - parseinput.py
INPUT statement handling

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from . import util
from . import devices
from . import values
from . import error


class InputTextFile(devices.TextFileBase):
    """Handle INPUT from console."""

    # spaces do not separate numbers on console INPUT
    soft_sep = ''

    def __init__(self, line):
        """Initialise InputStream."""
        devices.TextFileBase.__init__(self, StringIO(line), 'D', 'I')


def input_console(editor, value_handler, prompt, readvar, newline):
    """Read a list of variables for INPUT."""
    # readvar is a list of (name, indices) tuples
    # we return a list of (name, indices, values) tuples
    while True:
        editor.screen.write(prompt)
        line = editor.wait_screenline(write_endl=newline)
        inputstream = InputTextFile(line)
        # read the values and group them and the separators
        values, seps = [], []
        for v in readvar:
            word, sep = inputstream.input_entry(v[0][-1], allow_past_end=True)
            value = value_handler.from_repr(word, allow_nonnum=False, typechar=v[0][-1])
            values.append(value)
            seps.append(sep)
        # last separator not empty: there were too many values or commas
        # earlier separators empty: there were too few values
        # empty values will be converted to zero by from_str
        # None means a conversion error occurred
        if (seps[-1] or '' in seps[:-1] or None in values):
            # good old Redo!
            editor.screen.write_line('?Redo from start')
        else:
            return [r + [v] for r, v in zip(readvar, values)]
