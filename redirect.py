"""
PC-BASIC - redirect.py
I/O redirection

(c) 2014, 2015 Rob Hagemans
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
utf8conv = unicodepage.UTF8Converter(preserve_control=True)

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

def set_input(f):
    """ BASIC-style redirected input. """
    global input_closed
    # read everything
    all_input = f.read()
    last = ''
    for c in all_input:
        # replace CRLF with CR
        if not (c == '\n' and last == '\r'):
            state.console_state.keyb.insert_chars(c)
        last = c
    input_closed = True

def set_output(f, utf8=False):
    """ Redirected output in ASCII or UTF-8 """
    if not utf8:
        echo = partial(echo_ascii, f=f)
    else:
        echo = partial(echo_utf8, f=f)
    output_echos.append(echo)

def echo_ascii(s, f):
    """ Output redirection echo as raw bytes. """
    f.write(str(s))

def echo_utf8(s, f):
    """ Output redirection echo as UTF-8. """
    f.write(utf8conv.to_utf8(str(s)))

def toggle_echo(device):
    """ Toggle copying of all screen I/O to LPT1. """
    if device.write in output_echos:
        output_echos.remove(device.write)
    else:
        output_echos.append(device.write)


prepare()
