#
# PC-BASIC 3.23  - program.py
#
# Program buffer utilities
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#


import error
import glob
import vartypes
import var
import events
import tokenise
import protect
from util import *

import StringIO 


#######################################################

# program bytecode buffer
bytecode = StringIO.StringIO()
# direct line buffer
direct_line = StringIO.StringIO()


# for error handling - can be in program bytecode or in linebuf
current_codestream = None
current_statement =  0

# bookkeeping of file positions and line numbers for jumps
line_numbers = {}

# protected flag, disallow LIST, LLIST and SAVE to ascii
protected = False

# current line number, here as a convenient place for globals used by many modules
linenum = -1        

# return positions    
gosub_return = []
for_next_stack = []
while_wend_stack = []

stop = None  


# where are we READing DATA?
data_pos=0
data_line = -1

# is the program running?    
run_mode = False

# show a prompt?
prompt = True

#######################################################

def set_runmode(new_runmode=True):
    global run_mode, bytecode, direct_line, current_codestream
    run_mode= new_runmode

    if run_mode:
        current_codestream = bytecode
    if not run_mode:
        current_codestream = direct_line
    
def unset_runmode():
    set_runmode(False)
def runmode():
    return run_mode



    
# jump to line number    
def jump(jumpnum):
    global bytecode, linenum
    
    if jumpnum in line_numbers:
        # jump to target
        bytecode.seek(line_numbers[jumpnum])
        linenum = jumpnum
        set_runmode()
        
    else:
        # Undefined line number
        raise error.RunError(8)


# build list of line numbers and positions
def preparse():
    global bytecode, line_numbers
    
    # preparse to build line number dictionary
    line_numbers = {}
    bytecode.seek(1)
    while True:
        
        scanline = parse_line_number(bytecode)
        if scanline == -1:
            # program ends
            if peek(bytecode) == '':
                # truncated file, no \00\00\00\nn (\nn can be \1a or something else)
                # fix that
                bytecode.write('\x00\x00\x00\x1a')
                # try again 
                bytecode.seek(last)
                skip_to_read(bytecode, end_line)
                parse_line_number(bytecode)
              
            line_numbers[65536] = bytecode.tell() - 3  
            break
        
        last = bytecode.tell() - 5   
        line_numbers[scanline] = last  
        
        skip_to_read(bytecode, end_line)
        
    reset_program()
    
    
            
def reset_program():
    global bytecode, gosub_return, for_next_stack, linenum, data_line, data_pos
    
    gosub_return = []
    for_next_stack=[]
    
    # disable error trapping
    error.error_resume = None
    error.on_error=0
    # reset err and erl
    error.reset_error()
        
    # reset event trapping
    events.reset_events()    
        
    stop=None
    linenum=-1
    var.clear_variables()
    bytecode.seek(0)
    
    data_line =-1
    data_pos = 0
    
    
def clear_program():
    global bytecode, protected, line_numbers, data_line, data_pos
    
    bytecode.truncate(0)
    bytecode.write('\x00\x00\x00\x1A')
    protected = False
    line_numbers = {}    
    reset_program()

    #data_line =-1
    #data_pos = 0
    
    
def truncate_program(rest):
    global bytecode
    
    if rest=='':
        bytecode.write('\x00\x00\x00\x1a')
    else:
        bytecode.write(rest)
    
    pos = bytecode.tell()
    
    # clear out the rest of the buffer
    # no more elegant way?
    program = bytecode.getvalue()
    program = program[:pos]
    
    bytecode.truncate(0) 
    bytecode.write(program)    

    
def store_line(linebuf, auto_mode=False):
    global bytecode, line_numbers, linenum
    
    start = linebuf.tell()
    # check if linebuf is an empty line after the line number
    linebuf.seek(5)
    empty = (skip_white_read(linebuf) in end_line)
    
    # get the new line number
    linebuf.seek(1)
    scanline = parse_line_number(linebuf)
    
    
    # find the lowest line after this number
    after = 65536
    afterpos = 0 
    for num in line_numbers:
        if num > scanline and num <= after:
            after = num
            afterpos = line_numbers[after]        
            # if not found, afterpos will be the number stored at 65536, ie the end of program
    
    # read the remainder of the program into a buffer to be pasted back after the write
    bytecode.seek(afterpos)
    rest = bytecode.read()
    
    # replace or insert?
    if scanline in line_numbers and not (auto_mode and empty):
        # line number exists, replace line
        bytecode.seek(line_numbers[scanline])
    else:
        if empty:
            if not auto_mode:
                # undefined line number
                raise error.RunError(8)
            else:
                ### assign to global linenum, needed for AUTO
                #linenum = scanline
                ###
    
                return scanline
                
        # insert    
        bytecode.seek(afterpos)
            
    # write the line buffer to the program buffer
    if not empty:
        linebuf.seek(0)
        bytecode.write(linebuf.read())
    
    # write back the remainder of the program
    truncate_program(rest)
            
    bytecode.seek(0)
    preparse()

    return scanline #linenum = scanline


def delete_lines(fromline, toline):
    global bytecode, line_numbers
    
    startline = 0
    startpos = 0
    # fromline and toline must both exist, if specified
    if fromline == -1:
        pass
    elif fromline not in line_numbers: 
        raise error.RunError(5)
    else:
        startline = fromline
        startpos = line_numbers[startline]
        
    
    afterline = 65536
    afterpos = 0 
    if toline == -1:
        toline = 65535
        pass
    elif toline not in line_numbers:
        raise error.RunError(5)
    
    for num in line_numbers:
        # lowest number above range
        if num > toline and num <= afterline:
            afterline = num
            afterpos = line_numbers[afterline]        
    
    # if not found, afterpos will be the number stored at 65536, ie the end of program
    bytecode.seek(afterpos)
    rest = bytecode.read()
    
    bytecode.seek(startpos)
    truncate_program(rest)
    
    bytecode.seek(0)
    preparse()



def edit_line(from_line, pos=-1):
    global bytecode, prompt
    
    # list line
    current = bytecode.tell()	        
    bytecode.seek(1)
    
    output = StringIO.StringIO()
    tokenise.detokenise(bytecode, output, from_line, from_line, pos)
    
    output.seek(0)
    bytecode.seek(current)
    
    glob.scrn.write(output.getvalue())
    output.close()
     
    # throws back to direct mode
    unset_runmode()
    #suppress prompt, move cursor?
    prompt=False
    glob.scrn.set_pos(glob.scrn.get_row()-1, 1)
    
    
def renumber(new_line=-1, start_line=-1, step=-1):
    global bytecode, line_numbers
    
    if new_line==-1:
        new_line=10
    if start_line==-1:
        start_line=0
    if step==-1:
        step=10        
    
    # get line number dict in the form it should've been in anyway had I implemented it sensibly
    lines = []
    for num in line_numbers:
        if num >= start_line:
            lines.append([num, line_numbers[num]])        
    lines.sort()    
    
    # assign the new numbers
    for pairs in lines:
        pairs.append(new_line)
        new_line += step    
    
    # write the new numbers
    for pairs in lines:
        if pairs[0]==65536:
            break
        bytecode.seek(pairs[1])
        bytecode.read(3)
        bytecode.write(vartypes.value_to_uint(pairs[2]))
        
        
    #write the indirect line numbers
    bytecode.seek(0)
    linum = -1
    while peek(bytecode) != '':
        linum = skip_to(bytecode, ['\x0d', '\x0e'], linum)
        if linum ==-1:
            break
        bytecode.read(1)
        s = bytecode.read(2)
        
        jumpnum = uint_to_value(s)
        newnum = -1
        
        for triplets in lines:
            if triplets[0]==jumpnum:
                newnum = triplets[2]
        if newnum != -1:    
            bytecode.seek(-2,1)
            bytecode.write(vartypes.value_to_uint(newnum))
        else:
            # just a message, not an actual error. keep going.
            glob.scrn.write('Undefined line '+str(jumpnum)+' in '+str(linum)+glob.endl)
    
    # rebuild the line number dictionary    
    preparse()    
    
    
    


def load(g):
    global bytecode, protected
    
    bytecode.truncate(0)
    
    c = g.read(1)
    
    if c == '\xFF':
        # bytecode file
        bytecode.write('\x00')
        protected = False
        bytecode.write(g.read())
    elif c=='\xFE':
        # protected file
        bytecode.write('\x00')
        protected = True                
        protect.unprotect(g, bytecode)
    elif c=='\xFC':
        # QuickBASIC file
        error.warning(6, program.linenum, '')
        return
    elif c=='':
        # empty file
        pass
    else:
        # TODO: check allowed first chars for ASCII file - > whitespace + nums? letters?
    
        # ASCII file, maybe
        g.seek(-1,1)
        protected = False
        tokenise.tokenise_stream(g, bytecode)
    
    preparse()
    
    
    
    

def merge(g):
    
    if peek(g) in ('\xFF', '\xFE', '\xFC', ''):
        # bad file mode
        raise error.RunError(54)
    else:
        
        more=True
        while (more): #peek(g)=='' and not peek(g)=='\x1A':
            tempbuf = StringIO.StringIO()
    
            more = tokenise.tokenise_stream(g, tempbuf, one_line=True)
            tempbuf.seek(0)
            
            c = peek(tempbuf) 
            if c=='\x00':
                # line starts with a number, add to program memory
                store_line(tempbuf)
            elif skip_white(tempbuf) in end_line:
                # empty line
                pass
            else:
                # direct statement in file
                raise error.RunError(66)                
    
            tempbuf.close()    
        
    
    

def save(g, mode='B'):
    global bytecode, protected
    
    bytecode.seek(1)
    if mode=='B':
        if protected:
            raise error.RunError(5)
        else:
            g.write('\xff')
            g.write(bytecode.read())
    elif mode=='P':
        g.write('\xfe')
        protect.protect(bytecode, g)    
    else:
        if protected:
            raise error.RunError(5)
        else:
            tokenise.detokenise(bytecode, g) 
            # fix \x1A eof
            g.write('\x1a')        
                    
                        
                
                
            
            
            

