"""
PC-BASIC - print_and_input.py
Console I/O operations

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import util
import console
import devices


class InputTextFile(devices.TextFileBase):
    """ Handle INPUT from console. """

    soft_sep = ''

    def __init__(self, line):
        """ Initialise InputStream. """
        devices.TextFileBase.__init__(self, StringIO(line), 'D', 'I')

    def read_var(self, v):
        """ Read a variable for INPUT from the console. """
        return self._input_entry(v[0][-1], allow_past_end=True)


def input_console(prompt, readvar, newline):
    """ Read a list of variables for INPUT. """
    while True:
        console.write(prompt)
        line = console.wait_screenline(write_endl=newline)
        inputstream = InputTextFile(line)
        # copy to allow multiple calls (for Redo)
        count_commas, count_values, has_empty = 0, 0, False
        varlist = []
        for v in readvar:
            val, sep = inputstream.read_var(v)
            varlist.append( [v[0], v[1], val] )
            count_values += 1
            if val is None:
                has_empty = True
            if sep == ',':
                count_commas += 1
            else:
                break
        if (count_values != len(readvar) or
                count_commas != len(readvar)-1 or has_empty):
            # good old Redo!
            console.write_line('?Redo from start')
        else:
            return varlist


########################################
# for PRINT USING

def get_string_tokens(fors):
    """ Get consecutive string-related formatting tokens. """
    word = ''
    c = util.peek(fors)
    if c in ('!', '&'):
        word += fors.read(1)
    elif c == '\\':
        word += fors.read(1)
        # count the width of the \ \ token;
        # only spaces allowed and closing \ is necessary
        while True:
            c = fors.read(1)
            word += c
            if c == '\\':
                break
            elif c != ' ': # can be empty as well
                fors.seek(-len(word), 1)
                return ''
    return word

def get_number_tokens(fors):
    """ Get consecutive number-related formatting tokens. """
    word, digits_before, decimals = '', 0, 0
    # + comes first
    leading_plus = (util.peek(fors) == '+')
    if leading_plus:
        word += fors.read(1)
    # $ and * combinations
    c = util.peek(fors)
    if c in ('$', '*'):
        word += fors.read(2)
        if word[-1] != c:
            fors.seek(-len(word), 1)
            return '', 0, 0
        if c == '*':
            digits_before += 2
            if util.peek(fors) == '$':
                word += fors.read(1)
        else:
            digits_before += 1
    # number field
    c = util.peek(fors)
    dot = (c == '.')
    if dot:
        word += fors.read(1)
    if c in ('.', '#'):
        while True:
            c = util.peek(fors)
            if not dot and c == '.':
                word += fors.read(1)
                dot = True
            elif c == '#' or (not dot and c == ','):
                word += fors.read(1)
                if dot:
                    decimals += 1
                else:
                    digits_before += 1
            else:
                break
    if digits_before + decimals == 0:
        fors.seek(-len(word), 1)
        return '', 0, 0
    # post characters
    if util.peek(fors, 4) == '^^^^':
        word += fors.read(4)
    if not leading_plus and util.peek(fors) in ('-', '+'):
        word += fors.read(1)
    return word, digits_before, decimals
