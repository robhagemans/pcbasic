#
# PC-BASIC 3.23 - stat_os.py
#
# OS statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os
import datetime

import error
import vartypes
import expressions
import oslayer
import util
import console
import fileio

def exec_chdir(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    if name == '':
        raise error.RunError(64)
    name = oslayer.dospath_read_dir(name, '', 76)
    oslayer.safe(os.chdir, str(name))
    util.require(ins, util.end_statement)

def exec_mkdir(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    if name == '':
        raise error.RunError(64)
    oslayer.safe(os.mkdir, str(oslayer.dospath_write_dir(name,'', 76)))
    util.require(ins, util.end_statement)

def exec_rmdir(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    name = oslayer.dospath_read_dir(name, '', 76)
    oslayer.safe(os.rmdir, str(name))
    util.require(ins, util.end_statement)

def exec_name(ins):
    oldname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    oldname = oslayer.dospath_read(oldname, '', 76)
    # AS is not a tokenised word
    word = util.skip_white_read(ins) + ins.read(1)
    if word.upper() != 'AS':
        raise error.RunError(2)
    newname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    newname = oslayer.dospath_write(newname, '', 76)
    if os.path.exists(str(newname)):
        # file already exists
        raise error.RunError(58)
    oslayer.safe(os.rename, str(oldname), str(newname))
    util.require(ins, util.end_statement)

def exec_kill(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    name = oslayer.dospath_read(name, '', 53)
    # don't delete open files
    for f in fileio.files:
        if name == fileio.files[f].fhandle.name:
            raise error.RunError(55)
    oslayer.safe(os.remove, str(name))
    util.require(ins, util.end_statement)
        

def exec_files(ins):
    path, mask = '.', '*.*'
    if util.skip_white(ins) not in util.end_statement:
        pathmask = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        if pathmask == '':
            # bad file name
            raise error.RunError(64)
        pathmask = pathmask.rsplit('\\', 1)
        if len(pathmask) > 1:
            path = str(pathmask[0])
            if path == '':
                path = '\\'
            mask = str(pathmask[1])
        else:
            if pathmask[0]:
                path = '.'
                mask = str(pathmask[0])            
    mask = mask.upper()
    if mask == '':
        mask = '*.*'
    # get top level directory for '.'
    path = os.path.abspath(path.replace('\\', os.sep))
    roots, dirs, files = [], [], []
    for root, dirs, files in oslayer.safe(os.walk, path):
        break
    # get working dir, replace / with \
    cwd = path.replace(os.sep,'\\')
    console.write(cwd + util.endl)
    if (roots, dirs, files) == ([], [], []):
        raise error.RunError(53)
    dosfiles = oslayer.pass_dosnames(files, mask)
    dosfiles = [ name+'     ' for name in dosfiles ]
    dirs += ['.', '..']
    dosdirs = oslayer.pass_dosnames(dirs, mask)
    dosdirs = [ name+'<DIR>' for name in dosdirs ]
    dosfiles.sort()
    dosdirs.sort()    
    output = dosdirs + dosfiles
    num = console.width/20
    if len(output) == 0:
        # file not found
        raise error.RunError(53)
    while len(output) > 0:
        line = ' '.join(output[:num])
        output = output[num:]
        console.write(line+util.endl)       
        # allow to break during dir listing & show names flowing on screen
        console.check_events()             
    console.write(str(oslayer.disk_free(path)) + ' Bytes free' + util.endl)
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
    now = datetime.datetime.today() + oslayer.time_offset
    timelist = [0, 0, 0]
    pos. listpos, word = 0, 0, ''
    while pos < len(timestr):
        if listpos > 2:
            break
        c = chr(timestr[pos])
        if c in (':', '.'):
            timelist[listpos] = int(word)
            listpos += 1
            word = ''
        elif (c < '0' or c > '9'): 
            raise error.RunError(5)
        else:
            word += c
        pos += 1
    if word:
        timelist[listpos] = int(word)     
    if timelist[0] > 23 or timelist[1] > 59 or timelist[2] > 59:
        raise error.RunError(5)
    newtime = datetime.datetime(now.year, now.month, now.day, timelist[0], timelist[1], timelist[2], now.microsecond)
    oslayer.time_offset += newtime - now    
        
def exec_date(ins):
    util.require_read(ins, ('\xE7',)) # date$=
    # allowed formats:
    # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
    # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
    datestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    now = datetime.datetime.today() + oslayer.time_offset
    datelist = [1, 1, 1]
    pos, listpos, word = 0, 0, ''
    if len(datestr) < 8:
        raise error.RunError(5)
    while pos < len(datestr):
        if listpos > 2:
            break
        c = chr(datestr[pos])
        if c in ('-', '/'):
            datelist[listpos] = int(word)
            listpos += 1
            word = ''
        elif (c < '0' or c > '9'): 
            if listpos == 2:
                break
            else:
                raise error.RunError(5)
        else:
            word += c
        pos += 1
    if word:
        datelist[listpos] = int(word)     
    if (datelist[0] > 12 or datelist[1] > 31 or
            (datelist[2] > 77 and datelist[2] < 80) or 
            (datelist[2] > 99 and datelist[2] < 1980 or datelist[2] > 2099)):
        raise error.RunError(5)
    if datelist[2] <= 77:
        datelist[2] = 2000 + datelist[2]
    elif datelist[2] < 100 and datelist[2] > 79:
        datelist[2] = 1900 + datelist[2]
    try:
        newtime = datetime.datetime(datelist[2], datelist[0], datelist[1], now.hour, now.minute, now.second, now.microsecond)
    except ValueError:
        raise error.RunError(5)
    oslayer.time_offset += newtime - now    
    
