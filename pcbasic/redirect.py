"""
PC-BASIC - redirect.py
I/O redirection

(c) 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import logging
from functools import partial

import config
import unicodepage
import state

# input has closed
input_closed = False

# converter with DBCS lead-byte buffer for utf8 output redirection
uniconv = state.console_state.codepage.get_converter(preserve_control=True)

# redirect i/o to file or printer
output_echos = []

def prepare():
    """ Initialise redirect module. """
    pass

def prepare_redirects():
    """ Initialise i/o redirects. """
    option_input = config.get('input')
    option_output = config.get('output')
    if option_output:
        mode = 'ab' if config.get('append') else 'wb'
        try:
            set_output(open(option_output, mode))
        except EnvironmentError as e:
            logging.warning('Could not open output file %s: %s', option_output, e.strerror)
    if option_input:
        try:
            set_input(open(option_input, 'rb'))
        except EnvironmentError as e:
            logging.warning('Could not open input file %s: %s', option_input, e.strerror)

def set_input(f, encoding=None):
    """ BASIC-style redirected input. """
    global input_closed
    # read everything
    all_input = f.read()
    if encoding:
        all_input = all_input.decode(encoding, 'replace')
    else:
        # raw input means it's already in the BASIC codepage
        # but the keyboard functions use unicode
        all_input = state.console_state.codepage.str_to_unicode(
                                            all_input, preserve_control=True)
    last = ''
    for c in all_input:
        # replace CRLF with CR
        if not (c == u'\n' and last == u'\r'):
            state.console_state.keyb.insert_chars(c, check_full=False)
        last = c
    input_closed = True

def set_output(f, encoding=None):
    """ Redirected output as raw bytes or UTF-8 or other encoding """
    if not encoding:
        echo = partial(echo_raw, f=f)
    else:
        echo = partial(echo_encoded, f=f, encoding=encoding)
    output_echos.append(echo)

def echo_raw(s, f):
    """ Output redirection echo as raw bytes. """
    f.write(str(s))

def echo_encoded(s, f, encoding='utf-8'):
    """ Output redirection echo as UTF-8 or other encoding. """
    f.write(uniconv.to_unicode(str(s)).encode(encoding, 'replace'))

def toggle_echo(device):
    """ Toggle copying of all screen I/O to LPT1. """
    if device.write in output_echos:
        output_echos.remove(device.write)
    else:
        output_echos.append(device.write)


prepare()
