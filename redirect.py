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

import unicodepage
import console
import oslayer
import state
from functools import partial

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
utf8conv = unicodepage.UTF8Converter()
    
def echo_utf8(s, f):
    """ Output redirection echo as UTF-8. """
    f.write(utf8conv.to_utf8(str(s), preserve_control=True)) 
    
    
