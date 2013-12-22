#
# PC-BASIC 3.23  - printer.py
#
# Printer implementation using LPR
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os

### interface

# number of columns, counting 1..width
width = 80


def init():
    pass


def set_width(to_width):
    global width
    width = to_width
    

def get_col():
    global col
    return col        


def write(s):
    global printbuf, col, width
    tab = 8
    last=''
    for c in s:
        # enforce width setting, unles wrapping is enabled (width=255)
        if col == width and width !=255:
            col=1
            printbuf+='\n'
        
        if c=='\x0d' or c=='\x0a' and width!=255: # CR, LF
            if c=='\x0a' and last=='\x0d':
                pass
            else:
                col = 1
                printbuf += '\n'#c
        elif c=='\x09': # TAB
            num = (tab - (col - tab*int((col-1)/tab)))
            printbuf +=' '*num
        else:
            col+=1    
            printbuf += c    
        last=c


def set_printer(name=''):
    global printer_name
    printer_name=name
    
    
# flush buffer to LPR printer    
def flush():
    global printbuf
    options=''
    if printer_name!='':
        options += ' -P '+printer_name
    if printbuf!='':
        pr=os.popen("lpr "+ options, "w")
        pr.write(printbuf)
        pr.close()
        printbuf = ''
    
### implementation

col = 1
printbuf = ''
printer_name=''

