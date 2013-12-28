#
# PC-BASIC 3.23  - printer.py
#
# Printer device implementation
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import oslayer
import StringIO

class PrinterStream(StringIO.StringIO):

    def __init__(self, name=''):
        self.printer_name=name
        StringIO.StringIO.__init__(self)
    
    
    # flush buffer to LPR printer    
    def flush(self):
        oslayer.line_print(self.getvalue(), self.printer_name)
        self.truncate(0)
        self.seek(0)

    def close(self):
        self.flush()
        
        # don't actually close the stream, there may be copies
        #StringIO.StringIO.close(self)

'''
    def write(self, s):
        tab = 8
        last=''
        for c in s:
            # enforce width setting, unles wrapping is enabled (width=255)
            if self.col == width and self.width !=255:
                self.col=1
                self.printbuf+='\n'
            
            if c=='\x0d' or c=='\x0a' and self.width!=255: # CR, LF
                if c=='\x0a' and last=='\x0d':
                    pass
                else:
                    self.col = 1
                    self.printbuf += '\n'#c
            elif c=='\x09': # TAB
                num = (tab - (self.col-1 - tab*int((self.col-1)/tab)))
                self.printbuf +=' '*num
            else:
                self.col+=1    
                self.printbuf += c    
            last=c
'''
        
