"""
PC-BASIC - parseinput.py
INPUT statement handling

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import io

from . import devices
from . import values
from . import error
from . import tokens as tk


def input_(session, value_handler, newline, prompt, following, readvar):
    """INPUT: request input from user."""
    if following == ';':
        prompt += '? '
    # read the input
    session.input_mode = True
    session.redo_on_break = True
    varlist = input_console(session.editor, value_handler, prompt, readvar, newline)
    session.redo_on_break = False
    session.input_mode = False
    for v in varlist:
        session.memory.set_variable(*v)

def input_file_(memory, value_handler, finp, readvar):
    """INPUT: retrieve input from file."""
    for v in readvar:
        name, indices = v
        word, _ = finp.input_entry(name[-1], allow_past_end=False)
        value = value_handler.from_repr(word, allow_nonnum=False, typechar=name[-1])
        if value is None:
            value = value_handler.new(name[-1])
        memory.set_variable(name, indices, value)

def line_input_(session, value_handler, finp, prompt, readvar, indices, newline):
    """LINE INPUT: request line of input from user."""
    if not readvar:
        raise error.RunError(error.STX)
    elif readvar[-1] != '$':
        raise error.RunError(error.TYPE_MISMATCH)
    # read the input
    if finp:
        line = finp.read_line()
        if line is None:
            raise error.RunError(error.INPUT_PAST_END)
    else:
        session.input_mode = True
        session.redo_on_break = True
        session.screen.write(prompt)
        line = session.editor.wait_screenline(write_endl=newline)
        session.redo_on_break = False
        session.input_mode = False
    session.memory.set_variable(readvar, indices, value_handler.from_value(line, values.STR))

def parse_prompt(ins):
    """Helper function for INPUT: parse prompt definition."""
    # ; to avoid echoing newline
    newline = not ins.skip_blank_read_if((';',))
    # parse prompt
    prompt, following = '', ';'
    if ins.skip_blank() == '"':
        # only literal allowed, not a string expression
        prompt = ins.read_string().strip('"')
        following = ins.require_read((';', ','))
    return newline, prompt, following

def input_console(editor, value_handler, prompt, readvar, newline):
    """Read a list of variables for INPUT."""
    # readvar is a list of (name, indices) tuples
    # we return a list of (name, indices, values) tuples
    while True:
        editor.screen.write(prompt)
        # disconnect the wrap between line with the prompt and previous line
        if editor.screen.current_row > 1:
            editor.screen.apage.row[editor.screen.current_row-2].wrap = False
        line = editor.wait_screenline(write_endl=newline)
        inputstream = InputTextFile(line)
        # read the values and group them and the separators
        var, values, seps = [], [], []
        for v in readvar:
            word, sep = inputstream.input_entry(v[0][-1], allow_past_end=True)
            try:
                value = value_handler.from_repr(word, allow_nonnum=False, typechar=v[0][-1])
            except error.RunError as e:
                # string entered into numeric field
                value = None
            var.append(list(v))
            values.append(value)
            seps.append(sep)
        # last separator not empty: there were too many values or commas
        # earlier separators empty: there were too few values
        # empty values will be converted to zero by from_str
        # None means a conversion error occurred
        if (seps[-1] or '' in seps[:-1] or None in values):
            # good old Redo!
            editor.screen.write_line('?Redo from start')
            readvar = var
        else:
            return [r + [v] for r, v in zip(var, values)]


class InputTextFile(devices.TextFileBase):
    """Handle INPUT from console."""

    # spaces do not separate numbers on console INPUT
    soft_sep = ''

    def __init__(self, line):
        """Initialise InputStream."""
        devices.TextFileBase.__init__(self, io.BytesIO(line), 'D', 'I')
