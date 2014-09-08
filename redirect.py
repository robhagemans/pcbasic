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

import config
import unicodepage
import console
import oslayer
from functools import partial

def prepare():
        # gwbasic-style redirected output is split between graphical screen and redirected file    
    if config.options['output']:
        set_output(oslayer.safe_open(config.options['output'], "S", "W"))
    if config.options['input']:
        set_input(oslayer.safe_open(config.options['input'], "L", "R"))

def set_input(f):
    """ BASIC-style redirected input. """
    # read everything
    all_input = f.read()
    last = ''
    for c in all_input:
        # replace CRLF with CR
        if not (c == '\n' and last == '\r'):
            console.insert_key(c)
        last = c
    console.input_closed = True

def set_output(f, utf8=False):
    """ Redirected output in ASCII or UTF-8 """
    if not utf8:
        echo = partial(echo_ascii, f=f)
    else:
        echo = partial(echo_utf8, f=f)
    console.output_echos.append(echo) 
    console.input_echos.append(echo)
        
def echo_ascii(s, f):
    """ Output redirection echo as raw bytes. """
    f.write(str(s))
                            
# coverter with DBCS lead-byte buffer
utf8conv = unicodepage.UTF8Converter(preserve_control=True)
    
def echo_utf8(s, f):
    """ Output redirection echo as UTF-8. """
    f.write(utf8conv.to_utf8(str(s))) 

# FIXME: we'll need to call this explicitly because of circular import console > backend > novideo > redirect > console    
#prepare()
    
