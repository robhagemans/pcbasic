#
# PC-BASIC 3.23 - nopenstick.py
#
# Null pen & stick implementation
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

def trigger_pen(pos):
    pass
                
def trigger_stick(joy, button):
    pass

def get_pen(fn):
    return 0 if fn < 6 else 1

def get_stick(fn):
    return 0

def get_strig(fn):       
    return 0
