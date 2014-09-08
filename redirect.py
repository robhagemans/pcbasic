#
# PC-BASIC 3.23 - redirect.py
#
# BASIC-style I/O redirection
# 
# (c) 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import logging
from functools import partial

import config
import unicodepage
import backend
                            
# converter with DBCS lead-byte buffer for utf8 output redirection
utf8conv = unicodepage.UTF8Converter(preserve_control=True)

def prepare():
    """ Initialise redirect module. """
    if config.options['output']:
        try:
            set_output(open(config.options['output'], 'wb'))
        except EnvironmentError as e:
            logging.warning('Could not open output file %s: %s', config.options['output'], e.strerror)
    if config.options['input']:
        try:
            set_input(open(config.options['input'], 'rb'))
        except EnvironmentError as e:
            logging.warning('Could not open input file %s: %s', config.options['input'], e.strerror)

def set_input(f):
    """ BASIC-style redirected input. """
    # read everything
    all_input = f.read()
    last = ''
    for c in all_input:
        # replace CRLF with CR
        if not (c == '\n' and last == '\r'):
            backend.insert_key(c)
        last = c
    backend.input_closed = True

def set_output(f, utf8=False):
    """ Redirected output in ASCII or UTF-8 """
    if not utf8:
        echo = partial(echo_ascii, f=f)
    else:
        echo = partial(echo_utf8, f=f)
    backend.output_echos.append(echo) 
    backend.input_echos.append(echo)
        
def echo_ascii(s, f):
    """ Output redirection echo as raw bytes. """
    f.write(str(s))
    
def echo_utf8(s, f):
    """ Output redirection echo as UTF-8. """
    f.write(utf8conv.to_utf8(str(s))) 

prepare()
    
