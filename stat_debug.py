#
# PC-BASIC 3.23 - stat_debug.py
#
# DEBUG statement and utilities
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import StringIO
import sys

import glob
import util
import program

def exec_DEBUG(ins):
    # this is not a GW-BASIC behaviour, but helps debugging.
    # this is parsed like a REM by the tokeniser.
    # rest of the line is considered to be a python statement
    d = util.skip_white(ins)
    
    debug = ''
    while util.peek(ins) not in util.end_line:
        d = ins.read(1)
        debug += d
        
    buf = StringIO.StringIO()
    sys.stdout = buf
    try:
        exec(debug)
    except Exception:
        print "[exception]"
        pass    
    sys.stdout = sys.__stdout__

    glob.console.write(buf.getvalue())

    
# DEBUG utilities
def debug_dump_program():
    sys.stderr.write(program.bytecode.getvalue().encode('hex')+'\n')    
        
