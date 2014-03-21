#
# PC-BASIC 3.23 - stat_os.py
#
# OS statements
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os

import error
import vartypes
import expressions
import oslayer
import util
import console
import fileio

def exec_chdir(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    oslayer.safe(os.chdir, str(oslayer.dospath_read_dir(name, '', 76)))
    util.require(ins, util.end_statement)

def exec_mkdir(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    oslayer.safe(os.mkdir, str(oslayer.dospath_write_dir(name,'', 76)))
    util.require(ins, util.end_statement)

def exec_rmdir(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    oslayer.safe(os.rmdir, str(oslayer.dospath_read_dir(name, '', 76)))
    util.require(ins, util.end_statement)

def exec_name(ins):
    oldname = oslayer.dospath_read(vartypes.pass_string_unpack(expressions.parse_expression(ins)), '', 53)
    # don't rename open files
    fileio.check_file_not_open(oldname)
    # AS is not a tokenised word
    word = util.skip_white_read(ins) + ins.read(1)
    if word.upper() != 'AS':
        raise error.RunError(2)
    newname = oslayer.dospath_write(vartypes.pass_string_unpack(expressions.parse_expression(ins)), '', 76)
    if os.path.exists(str(newname)):
        # file already exists
        raise error.RunError(58)
    oslayer.safe(os.rename, str(oldname), str(newname))
    util.require(ins, util.end_statement)

def exec_kill(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    name = oslayer.dospath_read(name, '', 53)
    # don't delete open files
    fileio.check_file_not_open(name)
    oslayer.safe(os.remove, str(name))
    util.require(ins, util.end_statement)

def exec_files(ins):
    pathmask = ''
    if util.skip_white(ins) not in util.end_statement:
        pathmask = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        if not pathmask:
            # bad file name
            raise error.RunError(64)
    oslayer.files(pathmask, console)
    util.require(ins, util.end_statement)
    
def exec_shell(ins):
    if util.skip_white(ins) in util.end_statement:
        cmd = oslayer.shell
    else:
        cmd = oslayer.shell_cmd + ' ' + vartypes.pass_string_unpack(expressions.parse_expression(ins))
    savecurs = console.show_cursor()
    oslayer.spawn_interactive_shell(cmd) 
    console.show_cursor(savecurs)
    util.require(ins, util.end_statement)
        
def exec_environ(ins):
    envstr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    eqs = envstr.find('=')
    if eqs <= 0:
        raise error.RunError(5)
    var = str(envstr[:eqs])
    val = str(envstr[eqs+1:])
    os.environ[var] = val
    util.require(ins, util.end_statement)
       
def exec_time(ins):
    util.require_read(ins, ('\xE7',)) #time$=
    # allowed formats:  hh   hh:mm   hh:mm:ss  where hh 0-23, mm 0-59, ss 0-59
    timestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    oslayer.set_time(timestr)

def exec_date(ins):
    util.require_read(ins, ('\xE7',)) # date$=
    # allowed formats:
    # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
    # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
    datestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    oslayer.set_date(datestr)
    
