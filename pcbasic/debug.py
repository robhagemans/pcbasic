"""
PC-BASIC - debug.py
DEBUG statement and utilities

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from StringIO import StringIO
import sys
import traceback
import platform
import logging
import subprocess
import os

import plat
import config
import logging
import state
import vartypes
import var
import representation
import expressions
import tokenise
import program
import console
import flow

debug_mode = False
debug_tron = False
watch_list = []

def prepare():
    """ Initialise the debug module. """
    global debug_mode
    debug_mode = config.get('debug')

def debug_exec(debug_cmd):
    """ Execute a debug command. """
    buf = StringIO()
    save_stdout = sys.stdout
    sys.stdout = buf
    try:
        exec(debug_cmd)
    except Exception as e:
        debug_handle_exc(e)
        traceback.print_tb(sys.exc_info()[2])
    sys.stdout = save_stdout
    logging.debug(buf.getvalue()[:-1]) # exclude \n

def debug_step(linum):
    """ Execute traces and watches on a program step. """
    if not debug_mode:
        return
    outstr = ''
    if debug_tron:
        outstr += ('['+('%i' % linum) +']')
    for (expr, outs) in watch_list:
        outstr += (' ' + expr +' = ')
        outs.seek(2)
        try:
            val = expressions.parse_expression(outs)
            if val[0] == '$':
                outstr += '"' + var.copy_str(val) + '"'
            else:
                outstr += representation.number_to_str(val, screen=False)
        except Exception as e:
            debug_handle_exc(e)
    if outstr:
        logging.debug(outstr)

def debug_handle_exc(e):
    """ Handle debugging exception. """
    logging.debug(str(type(e))+' '+str(e))

# DEBUG user utilities

def dump_program():
    """ Hex dump the program to the log. """
    logging.debug(state.basic_state.bytecode.getvalue().encode('hex'))

def dump_vars():
    """ Dump all variables to the log. """
    logging.debug(repr(state.basic_state.variables))

def show_screen():
    """ Copy the screen buffer to the log. """
    logging.debug('  +' + '-'*state.console_state.screen.mode.width+'+')
    i = 0
    lastwrap = False
    for row in state.console_state.screen.apage.row:
        s = [ c[0] for c in row.buf ]
        i += 1
        outstr = '{0:2}'.format(i)
        if lastwrap:
            outstr += ('\\')
        else:
            outstr += ('|')
        outstr += (''.join(s))
        if row.wrap:
            logging.debug(outstr + '\\ {0:2}'.format(row.end))
        else:
            logging.debug(outstr + '| {0:2}'.format(row.end))
        lastwrap = row.wrap
    logging.debug('  +' + '-'*state.console_state.screen.mode.width+'+')

def show_program():
    """ Write a marked-up hex dump of the program to the log. """
    code = state.basic_state.bytecode.getvalue()
    offset_val, p = 0, 0
    for key in sorted(state.basic_state.line_numbers.keys())[1:]:
        offset, linum = code[p+1:p+3], code[p+3:p+5]
        last_offset = offset_val
        offset_val = vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(offset)) - program.program_memory_start
        linum_val = vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(linum))
        logging.debug(    (code[p:p+1].encode('hex') + ' ' +
                        offset.encode('hex') + ' (+%03d) ' +
                        code[p+3:p+5].encode('hex') + ' [%05d] ' +
                        code[p+5:state.basic_state.line_numbers[key]].encode('hex')),
                     offset_val - last_offset, linum_val )
        p = state.basic_state.line_numbers[key]
    logging.debug(code[p:p+1].encode('hex') + ' ' +
                code[p+1:p+3].encode('hex') + ' (ENDS) ' +
                code[p+3:p+5].encode('hex') + ' ' + code[p+5:].encode('hex'))

def trace(on=True):
    """ Switch line number tracing on or off. """
    global debug_tron
    debug_tron = on

def watch(expr):
    """ Add an expression to the watch list. """
    outs = tokenise.tokenise_line('?'+expr)
    watch_list.append((expr, outs))


def details():
    """ Show detailed version/debugging information. """
    logging.info('\nPLATFORM')
    logging.info('os: %s %s %s', plat.system, platform.processor(), platform.version())
    logging.info('python: %s %s', sys.version.replace('\n',''), ' '.join(platform.architecture()))
    logging.info('\nMODULES')
    # try numpy before pygame to avoid strange ImportError on FreeBSD
    modules = ('numpy', 'win32api', 'sdl2', 'pygame', 'curses', 'pexpect', 'serial', 'parallel')
    for module in modules:
        try:
            m = __import__(module)
        except ImportError:
            logging.info('%s: --', module)
        else:
            for version_attr in ('__version__', 'version', 'VERSION'):
                try:
                    version = getattr(m, version_attr)
                    logging.info('%s: %s', module, version)
                    break
                except AttributeError:
                    pass
            else:
                logging.info('available\n')
    if plat.system != 'Windows':
        logging.info('\nEXTERNAL TOOLS')
        tools = ('lpr', 'paps', 'beep', 'xclip', 'xsel', 'pbcopy', 'pbpaste')
        for tool in tools:
            try:
                location = subprocess.check_output('command -v %s' % tool, shell=True).replace('\n','')
                logging.info('%s: %s', tool, location)
            except Exception as e:
                logging.info('%s: --', tool)


def bluescreen(e):
    """ Display a modal exception message. """
    state.console_state.screen.screen(0, 0, 0, 0, new_width=80)
    console.clear()
    console.init_mode()
    exc_type, exc_value, exc_traceback = sys.exc_info()
    # log the standard python error
    logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    # format the error more readably on the screen
    state.console_state.screen.set_border(4)
    state.console_state.screen.set_attr(0x70)
    console.write_line('EXCEPTION')
    state.console_state.screen.set_attr(15)
    if state.basic_state.run_mode:
        state.basic_state.bytecode.seek(-1, 1)
        program.edit(program.get_line_number(state.basic_state.bytecode.tell()),
                                         state.basic_state.bytecode.tell())
        console.write_line('\n')
    else:
        state.basic_state.direct_line.seek(0)
        console.write_line(str(tokenise.detokenise_compound_statement(state.basic_state.direct_line)[0])+'\n')
    stack = traceback.extract_tb(exc_traceback)
    for s in stack[-4:]:
        stack_line = '{0}:{1}, {2}'.format(
            os.path.split(s[0])[-1], s[1], s[2])
        stack_line_2 = '    {0}'.format(s[3])
        state.console_state.screen.set_attr(15)
        console.write_line(stack_line)
        state.console_state.screen.set_attr(7)
        console.write_line(stack_line_2)
    exc_message = traceback.format_exception_only(exc_type, exc_value)[0]
    state.console_state.screen.set_attr(15)
    console.write('{0}:'.format(exc_type.__name__))
    state.console_state.screen.set_attr(7)
    console.write_line(' {0}'.format(str(exc_value)))
    state.console_state.screen.set_attr(0x70)
    console.write_line(
        '\nThis is a bug in PC-BASIC.')
    state.console_state.screen.set_attr(7)
    console.write(
        'Sorry about that. Please send the above messages to the bugs forum\nby e-mail to ')
    state.console_state.screen.set_attr(15)
    console.write(
        'bugs@discussion.pcbasic.p.re.sf.net')
    state.console_state.screen.set_attr(7)
    console.write(
        ' or by filing a bug\nreport at ')
    state.console_state.screen.set_attr(15)
    console.write(
        'https://github.com/robhagemans/pcbasic/issues')
    state.console_state.screen.set_attr(7)
    console.write_line(
        '. Please include')
    console.write_line('as much information as you can about what you were doing and how this happened.')
    console.write_line('Thank you!')
    state.console_state.screen.set_attr(7)
    flow.set_pointer(False)


prepare()
