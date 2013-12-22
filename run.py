#
# PC-BASIC 3.23 - run.py
# Main loops for pc-basic 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#


import sys
import StringIO

import glob
import error
import util
import var
import rnd

import events
import tokenise 
import program
import statements 
import oslayer
import fileio

import stat_code

#######################################################



def init_run():
    
    # initialise
    program.clear_program()
    var.clear_variables()
    rnd.clear()
    program.set_runmode(False)
    
    if glob.args.run or glob.args.load:
        fin = sys.stdin
        try:
            if glob.args.run != '':
                fin = oslayer.safe_open(glob.args.infile, 'rb')
            program.load(fin)
        except error.Error as e:
            if not handle_error(e):
                exit()
                #sys.exit(0)
        
    if glob.args.run and glob.args.cmd == None:
        # if a command is given, the program is only loaded.
        glob.args.cmd = 'RUN'
        
    if glob.args.cmd != None:
        get_command_line(glob.args.cmd)
        program.set_runmode(False)
        #program.current_codestream = program.direct_line
        execution_loop()

        if glob.args.quit:
            # we were running as a script, exit after completion
            #sys.exit(0)
            exit()
        
def auto_mode_show_line():
    if stat_code.auto_mode:
        stat_code.auto_linenum += stat_code.auto_increment
        glob.scrn.write(str(stat_code.auto_linenum))
        if stat_code.auto_linenum in program.line_numbers:
            glob.scrn.write('*')
        else:
            glob.scrn.write(' ')
                
def auto_mode_remove_star(line):                
    if stat_code.auto_mode and stat_code.auto_linenum in program.line_numbers:
        # AUTO: remove star
        num_len=len(str(stat_code.auto_linenum))
        
        if line[:num_len] == str(stat_code.auto_linenum):
            line=list(line)
            line[num_len]=' '
            line=''.join(line)




def main_loop():
    while True:
        
        # prompt for commands
        prompt()
        auto_mode_show_line()
                
        # call input loop
        try:
            line = glob.scrn.read_screenline() 
        except error.Break:
            #program.unset_runmode()
            if stat_code.auto_mode:
                program.prompt=True
                stat_code.auto_mode=False
            else:
                program.prompt=False
            continue
    
        auto_mode_remove_star(line)
        get_command_line(line)
        
        # check for empty lines or lines that start with a line number & deal with them
        if parse_start_direct(program.direct_line):
            # no prompt
            continue
        
        # run stuff             
        execution_loop()




# execute any commands
def execution_loop():
    glob.scrn.hide_cursor()
    while True:
        try:
            glob.scrn.check_events()
            events.handle_events()
            if not statements.parse_statement():
                break
        except error.Error as e:
            if not handle_error(e):
                break

        

    

                   
# direct mode functions:               
               
def prompt(force=False):
    glob.scrn.show_cursor()    
    if program.prompt or force:
        glob.scrn.start_line()
        glob.scrn.write("Ok "+glob.endl)
    else:
        program.prompt = True
              
              
def get_command_line(line):
    program.direct_line.truncate(0)
    sline = StringIO.StringIO(line)

    tokenise.tokenise_stream(sline, program.direct_line, onfile=False)
    program.direct_line.seek(0)
    
               
               
               
def parse_start_direct(linebuf):               
    c = util.peek(linebuf) 
    if c=='\x00':
        # line starts with a number, add to program memory
        try:
            if program.protected:
                # don't list protected files
                raise error.RunError(5)
    
            linenum = program.store_line(linebuf, stat_code.auto_mode)
            stat_code.auto_linenum = linenum
            program.prompt = False
        
        except error.RunError as e:
            handle_error(e)
            
        linebuf.seek(0)
        return True

    # check for empty line, no prompt
    if util.skip_white(linebuf) in util.end_line:
        linebuf.seek(0)
        program.prompt = False
        return True
        
    return False        

                                     

   
# error handler                
def handle_error(e):
    #if linum == None or linum==-1:
    #    linum = e.erl              
    program.prompt=True  
    if not program.runmode() or e.erl != -1:
        errline = e.erl
    else:
        errline = program.linenum
    
    if isinstance(e, error.Break):
        error.write_error_message(e.msg, errline)
        if program.runmode():
            program.stop = [program.bytecode.tell()-1, program.linenum]
            program.unset_runmode()
        return False
                
    # set ERR and ERL
    error.set_error(e.err, errline)
    
    # don't jump if we're already busy handling an error
    if error.on_error != None and error.on_error !=0 and not error.error_handle_mode:
        error.error_resume = program.current_statement, program.current_codestream, program.runmode()
       
        program.jump(error.on_error)
        error.error_handle_mode = True
        program.set_runmode()
        events.enable_events=False
        return True
    else:
        # not handled by ON ERROR, stop execution
        error.write_error_message(e.msg, errline)   
        error.error_handle_mode = False
        program.unset_runmode()
        program.prompt = True
        
        # for syntax error, line edit gadget appears
        if e.err==2 and errline !=-1:
            prompt()
            program.edit_line(errline)
        return False    


def exit():
    fileio.close_all()
    sys.exit(0)
