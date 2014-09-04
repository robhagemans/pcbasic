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

# basic-style redirected input
def load_redirected_input(f):
    # read everything
    all_input = f.read()
    last = ''
    for c in all_input:
        # replace CRLF with CR
        if not (c == '\n' and last == '\r'):
            console.insert_key(c)
        last = c
    console.input_closed = True

# basic_style redirected output   
# backspace actually takes characters out 
# we need to buffer to be able to redirect to stdout which is not seekable
linebuffer = ''   

def echobuffer(s):
    global linebuffer
    out = ''
    scancode = False
    for c in s:
        linebuffer += c
        if c in ('\r', '\n'):
            out += linebuffer
            linebuffer = ''
        elif c == '\b' and len(linebuffer) > 1:
            linebuffer = linebuffer[:-2]
    return out

def echo_ascii(s, f):
    f.write(echobuffer(s))
                        
