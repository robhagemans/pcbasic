#
# PC-BASIC 3.23 - console.py
#
# Console front-end
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import logging

import config
import state
import backend
# for Break, Exit, Reset
import error
# for dbcs
import unicodepage

# alt+key macros for interactive mode (these happen at a higher level than F-key macros)
alt_key_replace = {
    '\x00\x1E': 'AUTO',  '\x00\x30': 'BSAVE',  '\x00\x2E': 'COLOR',  '\x00\x20': 'DELETE', '\x00\x12': 'ELSE', 
    '\x00\x21': 'FOR',   '\x00\x22': 'GOT0',   '\x00\x23': 'HEX$',   '\x00\x17': 'INPUT',
    '\x00\x25': 'KEY',   '\x00\x26': 'LOCATE', '\x00\x32': 'MOTOR',  '\x00\x31': 'NEXT',   '\x00\x18': 'OPEN', 
    '\x00\x19': 'PRINT', '\x00\x13': 'RUN',    '\x00\x1F': 'SCREEN', '\x00\x14': 'THEN',   '\x00\x16': 'USING', 
    '\x00\x2F': 'VAL',   '\x00\x11': 'WIDTH',  '\x00\x2D': 'XOR' }

# on the keys line 25, what characters to replace & with which
keys_line_replace_chars = { 
        '\x07': '\x0e',    '\x08': '\xfe',    '\x09': '\x1a',    '\x0A': '\x1b',
        '\x0B': '\x7f',    '\x0C': '\x16',    '\x0D': '\x1b',    '\x1C': '\x10',
        '\x1D': '\x11',    '\x1E': '\x18',    '\x1F': '\x19',
    }        
    
# KEY ON?
state.console_state.keys_visible = True

# viewport parameters
state.console_state.view_start = 1
state.console_state.scroll_height = 24
state.console_state.view_set = False
# writing on bottom row is allowed    
state.console_state.bottom_row_allowed = False

# current attribute
state.console_state.attr = 7
# current row and column
state.console_state.row = 1
state.console_state.col = 1
# true if we're on 80 but should be on 81
state.console_state.overflow = False

# overwrite mode (instead of insert)
state.console_state.overwrite_mode = True

#############################
# init

def prepare():
    """ Initialise console module. """
    if config.options['run']:
        state.console_state.keys_visible = False
    
def init_mode():
    """ Initialisation when we switched to new screen mode. """
    # only redraw keys if screen has been cleared 
    # (any colours stay the same). s.c_s.screen_mode must be set for this
    if state.console_state.keys_visible:  
        show_keys(True)
    # rebuild build the cursor; 
    # first move to home in case the screen has shrunk
    set_pos(1, 1)
    set_default_cursor()
    backend.update_cursor_visibility()
    # there is only one VIEW PRINT setting across all pages.
    unset_view()

def set_width(to_width):
    """ Change the width of the screen. """
    # raise an error if the width value doesn't make sense
    if to_width not in (20, 40, 80):
        return False
    if to_width == state.console_state.width:
        return True
    if not backend.set_width(to_width):
        return False
    init_mode()
    return True

############################### 
# interactive mode         

def wait_screenline(write_endl=True, from_start=False, alt_replace=False):
    prompt_row = state.console_state.row
    # force cursor visibility in all cases
    backend.show_cursor(True) 
    try:
        furthest_left, furthest_right = wait_interactive(from_start, alt_replace)
    except error.Break:
        for echo in backend.input_echos:  
            echo ('\x0e')
        write_line()    
        raise        
    backend.update_cursor_visibility()
    # find start of wrapped block
    crow = state.console_state.row
    while crow > 1 and state.console_state.apage.row[crow-2].wrap:
        crow -= 1
    line = []
    # add lines 
    while crow <= state.console_state.height:
        therow = state.console_state.apage.row[crow-1]
        # exclude prompt, if any; only go from furthest_left to furthest_right
        if crow == prompt_row and not from_start:
            line += therow.buf[:therow.end][furthest_left-1:furthest_right-1]
        else:    
            line += therow.buf[:therow.end]
        if therow.wrap:
            if therow.end < state.console_state.width:
                # wrap before end of line means LF
                line += ('\n', state.console_state.attr),
            crow += 1
        else:
            break
    # go to last line
    state.console_state.row = crow
    # remove trailing whitespace 
    while len(line) > 0 and line[-1] in (' ', '\t', '\x0a'):
        line = line[:-1]
    outstr = bytearray()
    for c, _ in line:
        outstr += c
    # only the first 255 chars are registered    
    outstr = outstr[:255]    
    # redirections receive exactly what's going to the parser
    for echo in backend.input_echos:
        echo(outstr)
    # echo the CR, if requested
    if write_endl:
        for echo in backend.input_echos:
            echo('\r\n')
        set_pos(state.console_state.row+1, 1)
    return outstr    

def wait_interactive(from_start=False, alt_replace = True):
    # this is where we started
    start_row, furthest_left = state.console_state.row, (state.console_state.col if not from_start else 1)
    # this is where we arrow-keyed on the start line
    furthest_right = state.console_state.col 
    while True: 
        if state.console_state.row == start_row:
            furthest_left = min(state.console_state.col, furthest_left)
            furthest_right = max(state.console_state.col, furthest_right)
        # wait_char returns one ascii ar MS-DOS/GW-BASIC style keyscan code
        d = backend.pass_char(backend.wait_char())
        if not d:
            # input stream closed
            raise error.Exit()
        if d in ('\x00\x48', '\x1E', '\x00\x50', '\x1F',  '\x00\x4D', '\x1C', '\x00\x4B', 
                    '\x1D', '\x00\x47', '\x0B', '\x00\x4F', '\x0E' ):
            set_overwrite_mode(True)
        if d == '\x03':         
            raise error.Break()    # not caught in wait_char like <CTRL+BREAK>
        elif d == '\r':                     break                                   # <ENTER>
        elif d == '\a':                     backend.beep()                            # <CTRL+G>
        elif d == '\b':                     backspace(start_row, furthest_left)     # <BACKSPACE>
        elif d == '\t':                     tab()                                   # <TAB> or <CTRL+I>
        elif d == '\n':                     line_feed()                             # <CTRL+ENTER> or <CTRL+J>
        elif d == '\x1B':                   clear_line(state.console_state.row)                     # <ESC> or <CTRL+[>
        elif d in ('\x00\x75', '\x05'):     clear_rest_of_line(state.console_state.row, state.console_state.col)  # <CTRL+END> <CTRL+E>
        elif d in ('\x00\x48', '\x1E'):                                             # <UP> <CTRL+6>
            set_pos(state.console_state.row - 1, state.console_state.col, scroll_ok=False)    
        elif d in ('\x00\x50', '\x1F'):                                             # <DOWN> <CTRL+->
            set_pos(state.console_state.row + 1, state.console_state.col, scroll_ok=False)    
        elif d in ('\x00\x4D', '\x1C'):                                             # <RIGHT> <CTRL+\>
            # skip dbcs trail byte
            skip = 2 if state.console_state.apage.row[state.console_state.row-1].double[state.console_state.col-1] == 1 else 1   
            set_pos(state.console_state.row, state.console_state.col + skip, scroll_ok=False)
        elif d in ('\x00\x4B', '\x1D'):                                             # <LEFT> <CTRL+]>
            set_pos(state.console_state.row, state.console_state.col - 1, scroll_ok=False)                
        elif d in ('\x00\x74', '\x06'):     skip_word_right()                       # <CTRL+RIGHT> or <CTRL+F>
        elif d in ('\x00\x73', '\x02'):     skip_word_left()                        # <CTRL+LEFT> or <CTRL+B>
        elif d in ('\x00\x52', '\x12'):     set_overwrite_mode(not state.console_state.overwrite_mode)  # <INS> <CTRL+R>
        elif d in ('\x00\x53', '\x7F'):     delete_char(state.console_state.row, state.console_state.col)                   # <DEL> <CTRL+BACKSPACE>
        elif d in ('\x00\x47', '\x0B'):     set_pos(1, 1)                           # <HOME> <CTRL+K>
        elif d in ('\x00\x4F', '\x0E'):     end()                                   # <END> <CTRL+N>
        elif d in ('\x00\x77', '\x0C'):     clear()                                 # <CTRL+HOME> <CTRL+L>   
        elif d == '\x00\x37':               backend.print_screen()                  # <SHIFT+PRT_SC>, already caught in wait_char()
        else:
            try:
                # these are done on a less deep level than the fn key replacement
                letters = list(alt_key_replace[d]) + [' ']
            except KeyError:
                letters = [d]
            if not alt_replace:
                letters = [d]
            for d in letters:        
                if d[0] not in ('\x00', '\r'): 
                    if not state.console_state.overwrite_mode:
                        insert_char(state.console_state.row, state.console_state.col, d, state.console_state.attr)
                        backend.redraw_row(state.console_state.col-1, state.console_state.row)
                        set_pos(state.console_state.row, state.console_state.col+1)
                    else:    
                        put_char(d, do_scroll_down=True)
        # move left if we end up on dbcs trail byte
        if state.console_state.apage.row[state.console_state.row-1].double[state.console_state.col-1] == 2:
            set_pos(state.console_state.row, state.console_state.col-1, scroll_ok=False) 
        # adjust cursor width
        if state.console_state.apage.row[state.console_state.row-1].double[state.console_state.col-1] == 1:
            cursor_width = 2*state.console_state.font_width
        else:
            cursor_width = state.console_state.font_width
        if cursor_width != state.console_state.cursor_width:
            state.console_state.cursor_width = cursor_width
            backend.video.build_cursor(state.console_state.cursor_width, state.console_state.font_height, 
                    state.console_state.cursor_from, state.console_state.cursor_to)
            backend.video.update_cursor_attr(state.console_state.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)
    set_overwrite_mode(True)
    return furthest_left, furthest_right
      
def set_overwrite_mode(new_overwrite=True):
    if new_overwrite != state.console_state.overwrite_mode:
        state.console_state.overwrite_mode = new_overwrite
        set_default_cursor()

def set_default_cursor():
    if state.console_state.overwrite_mode:
        if state.console_state.screen_mode != 0: 
            backend.set_cursor_shape(0, state.console_state.font_height-1)
        elif backend.video_capabilities == 'ega':
            backend.set_cursor_shape(state.console_state.font_height-2, state.console_state.font_height-2)
        else:
            backend.set_cursor_shape(state.console_state.font_height-1, state.console_state.font_height-1)
    else:
        backend.set_cursor_shape(state.console_state.font_height/2, state.console_state.font_height-1)
      
def insert_char(crow, ccol, c, cattr):
    while True:
        therow = state.console_state.apage.row[crow-1]
        therow.buf.insert(ccol-1, (c, cattr))
        if therow.end < state.console_state.width:
            therow.buf.pop()
            if therow.end > ccol-1:
                therow.end += 1
            else:
                therow.end = ccol
            break
        else:
            if crow == state.console_state.scroll_height:
                scroll()
                # this is not the global row which is changed by scroll()
                crow -= 1
            if not therow.wrap and crow < state.console_state.height:
                scroll_down(crow+1)
                therow.wrap = True    
            c, cattr = therow.buf.pop()
            crow += 1
            ccol = 1
    return crow            
        
def delete_char(crow, ccol):
    double = state.console_state.apage.row[crow-1].double[ccol-1]
    if double == 0:
        delete_sbcs_char(crow, ccol)
    elif double == 1:    
        delete_sbcs_char(crow, ccol)
        delete_sbcs_char(crow, ccol)
    elif double == 2:    
        delete_sbcs_char(crow, ccol-1)
        delete_sbcs_char(crow, ccol-1)
        
def delete_sbcs_char(crow, ccol):
    save_col = ccol
    therow = state.console_state.apage.row[crow-1]
    if crow > 1 and ccol >= therow.end and therow.wrap:
        nextrow = state.console_state.apage.row[crow]
        # row was a LF-ending row
        therow.buf[ccol-1:] = nextrow.buf[:state.console_state.width-ccol+1] 
        therow.end = min(max(therow.end, ccol) + nextrow.end, state.console_state.width)
        while crow < state.console_state.scroll_height and nextrow.wrap:
            nextrow2 = state.console_state.apage.row[crow+1]
            nextrow.buf = nextrow.buf[state.console_state.width-ccol+1:] + nextrow2.buf[:state.console_state.width-ccol+1]  
            nextrow.end = min(nextrow.end + nextrow2.end, state.console_state.width)
            crow += 1
            therow, nextrow = state.console_state.apage.row[crow-1], state.console_state.apage.row[crow]
        nextrow.buf = nextrow.buf[state.console_state.width-ccol+1:] + [(' ', state.console_state.attr)]*(state.console_state.width-ccol+1) 
        nextrow.end -= state.console_state.width - ccol    
        backend.redraw_row(save_col-1, state.console_state.row)
        if nextrow.end <= 0:
            nextrow.end = 0
            ccol += 1
            therow.wrap = False
            scroll(crow+1)
    elif ccol <= therow.end:
        while True:            
            if therow.end < state.console_state.width or crow == state.console_state.scroll_height or not therow.wrap:
                del therow.buf[ccol-1]
                therow.buf.insert(therow.end-1, (' ', state.console_state.attr))
                break
            else:
                nextrow = state.console_state.apage.row[crow]
                # wrap and end[row-1]==width
                del therow.buf[ccol-1]
                therow.buf.insert(therow.end-1, nextrow.buf[0])
                crow += 1
                therow, nextrow = state.console_state.apage.row[crow-1], state.console_state.apage.row[crow]
                ccol = 1
        # this works from *global* row onwrds
        backend.redraw_row(save_col-1, state.console_state.row)
        # this works on *local* row (last row edited)
        if therow.end > 0:
            therow.end -= 1
        else:
            scroll(crow)
            if crow > 1:
                state.console_state.apage.row[crow-2].wrap = False            

    
def clear_line(the_row):
    # find start of line
    srow = the_row
    while srow > 1 and state.console_state.apage.row[srow-2].wrap:
        srow -= 1
    clear_rest_of_line(srow, 1)

def clear_rest_of_line(srow, scol):
    therow = state.console_state.apage.row[srow-1] 
    therow.buf = therow.buf[:scol-1] + [(' ', state.console_state.attr)]*(state.console_state.width-scol+1)
    therow.end = min(therow.end, scol-1)
    crow = srow
    while state.console_state.apage.row[crow-1].wrap:
        crow += 1
        state.console_state.apage.row[crow-1].clear(state.console_state.attr) 
    for r in range(crow, srow, -1):
        state.console_state.apage.row[r-1].wrap = False
        scroll(r)
    therow = state.console_state.apage.row[srow-1]    
    therow.wrap = False
    set_pos(srow, scol)
    save_end = therow.end
    therow.end = state.console_state.width
    if scol > 1:
        backend.redraw_row(scol-1, srow)
    else:
        backend.video.clear_rows(state.console_state.attr, srow, srow)
    therow.end = save_end

def backspace(start_row, start_col):
    crow, ccol = state.console_state.row, state.console_state.col
    # don't backspace through prompt
    if ccol == 1:
        if crow > 1 and state.console_state.apage.row[crow-2].wrap:
            ccol = state.console_state.width 
            crow -= 1
    elif ccol != start_col or state.console_state.row != start_row: 
        ccol -= 1
    set_pos(crow, max(1, ccol))
    if state.console_state.apage.row[state.console_state.row-1].double[state.console_state.col-1] == 2:
        # we're on a trail byte, move to the lead
        set_pos(state.console_state.row, state.console_state.col-1)
    delete_char(crow, ccol)
    
def tab():
    if state.console_state.overwrite_mode:
        set_pos(state.console_state.row, state.console_state.col+8, scroll_ok=False)
    else:
        for _ in range(8):
            insert_char(state.console_state.row, state.console_state.col, ' ', state.console_state.attr)
        backend.redraw_row(state.console_state.col-1, state.console_state.row)
        set_pos(state.console_state.row, state.console_state.col+8)
        
def end():
    crow = state.console_state.row
    while state.console_state.apage.row[crow-1].wrap and crow < state.console_state.height:
        crow += 1
    if state.console_state.apage.row[crow-1].end == state.console_state.width:
        set_pos(crow, state.console_state.apage.row[crow-1].end)
        state.console_state.overflow = True
    else:        
        set_pos(crow, state.console_state.apage.row[crow-1].end+1)

def line_feed():
    # moves rest of line to next line
    if state.console_state.col < state.console_state.apage.row[state.console_state.row-1].end:
        for _ in range(state.console_state.width-state.console_state.col+1):
            insert_char(state.console_state.row, state.console_state.col, ' ', state.console_state.attr)
        backend.redraw_row(state.console_state.col-1, state.console_state.row)
        state.console_state.apage.row[state.console_state.row-1].end = state.console_state.col-1 
    else:
        crow = state.console_state.row
        while state.console_state.apage.row[crow-1].wrap and crow < state.console_state.scroll_height:
            crow += 1
        if crow >= state.console_state.scroll_height:
            scroll()
        if state.console_state.row < state.console_state.height:    
            scroll_down(state.console_state.row+1)
    # LF connects lines like word wrap
    state.console_state.apage.row[state.console_state.row-1].wrap = True
    set_pos(state.console_state.row+1, 1)
    
def skip_word_right():
    crow, ccol = state.console_state.row, state.console_state.col
    # find non-alphanumeric chars
    while True:
        c = state.console_state.apage.row[crow-1].buf[ccol-1][0].upper()
        if (c < '0' or c > '9') and (c < 'A' or c > 'Z'):
            break
        ccol += 1
        if ccol > state.console_state.width:
            if crow >= state.console_state.scroll_height:
                # nothing found
                return
            crow += 1
            ccol = 1
    # find alphanumeric chars
    while True:
        c = state.console_state.apage.row[crow-1].buf[ccol-1][0].upper()
        if not ((c < '0' or c > '9') and (c < 'A' or c > 'Z')):
            break
        ccol += 1
        if ccol > state.console_state.width:
            if crow >= state.console_state.scroll_height:
                # nothing found
                return
            crow += 1
            ccol = 1
    set_pos(crow, ccol)                            
        
def skip_word_left():
    crow, ccol = state.console_state.row, state.console_state.col
    # find alphanumeric chars
    while True:
        ccol -= 1
        if ccol < 1:
            if crow <= state.console_state.view_start:
                # not found
                return
            crow -= 1
            ccol = state.console_state.width
        c = state.console_state.apage.row[crow-1].buf[ccol-1][0].upper()
        if not ((c < '0' or c > '9') and (c < 'A' or c > 'Z')):
            break
    # find non-alphanumeric chars
    while True:
        last_row, last_col = crow, ccol
        ccol -= 1
        if ccol < 1:
            if crow <= state.console_state.view_start:
                break
            crow -= 1
            ccol = state.console_state.width
        c = state.console_state.apage.row[crow-1].buf[ccol-1][0].upper()
        if (c < '0' or c > '9') and (c < 'A' or c > 'Z'):
            break
    set_pos(last_row, last_col)                            

def clear():
    save_view_set, save_view_start, save_scroll_height = state.console_state.view_set, state.console_state.view_start, state.console_state.scroll_height
    set_view(1,25)
    clear_view()
    if save_view_set:
        set_view(save_view_start, save_scroll_height)
    else:
        unset_view()
    if state.console_state.keys_visible:
        show_keys(True)
        
##### output methods

def write(s, scroll_ok=True, do_echo=True):
    if do_echo: 
        for echo in backend.output_echos:
            # CR -> CRLF, CRLF -> CRLF LF
            echo(''.join([ ('\r\n' if c == '\r' else c) for c in s ]))
    last = ''
    for c in s:
        if c == '\t':                                       # TAB
            num = (8 - (state.console_state.col-1 - 8*int((state.console_state.col-1)/8)))
            for _ in range(num):
                put_char(' ')
        elif c == '\n':                                     # LF
            # exclude CR/LF
            if last != '\r': 
                # LF connects lines like word wrap
                state.console_state.apage.row[state.console_state.row-1].wrap = True
                set_pos(state.console_state.row+1, 1, scroll_ok)
        elif c == '\r':     
            state.console_state.apage.row[state.console_state.row-1].wrap = False
            set_pos(state.console_state.row+1, 1, scroll_ok)     # CR
        elif c == '\a':     backend.beep()                     # BEL
        elif c == '\x0B':   set_pos(1, 1, scroll_ok)         # HOME
        elif c == '\x0C':   clear()
        elif c == '\x1C':   set_pos(state.console_state.row, state.console_state.col+1, scroll_ok)
        elif c == '\x1D':   set_pos(state.console_state.row, state.console_state.col-1, scroll_ok)
        elif c == '\x1E':   set_pos(state.console_state.row-1, state.console_state.col, scroll_ok)
        elif c == '\x1F':   set_pos(state.console_state.row+1, state.console_state.col, scroll_ok)
        else:
            # includes \b, \0, and non-control chars
            put_char(c)
        last = c

def write_line(s='', scroll_ok=True, do_echo=True): 
    write(s, scroll_ok, do_echo)
    if do_echo:
        for echo in backend.output_echos:
            echo('\r\n')
    check_pos(scroll_ok=True)
    state.console_state.apage.row[state.console_state.row-1].wrap = False
    set_pos(state.console_state.row + 1, 1)

# print a line from a program listing - no wrap if 80-column line, clear row before printing.
def list_line(line):
    # flow of listing is visible on screen
    backend.check_events()
    cuts = line.split('\a')
    for i, l in enumerate(cuts):
        clear_line(state.console_state.row)
        write(str(l))
        if i != len(cuts)-1:
            write('\a')
    clear_rest_of_line(state.console_state.row, state.console_state.col)
    write_line()
    # remove wrap after 80-column program line
    if len(line) == state.console_state.width and state.console_state.row > 2:
        state.console_state.apage.row[state.console_state.row-3].wrap = False
    
#####################
# key replacement

def list_keys():
    """ Print a list of the function key macros. """
    for i in range(backend.num_fn_keys):
        text = bytearray(state.console_state.key_replace[i])
        for j in range(len(text)):
            try:
                text[j] = keys_line_replace_chars[chr(text[j])]
            except KeyError:
                pass    
        write_line('F' + str(i+1) + ' ' + str(text))    

def clear_key_row():
    """ Clear row 25 on the active page. """
    state.console_state.apage.row[24].clear(state.console_state.attr)
    backend.video.clear_rows(state.console_state.attr, 25, 25)

def show_keys(do_show):
    """ Show/hide the function keys line on the active page. """
    # Keys will only be visible on the active page at which KEY ON was given, 
    # and only deleted on page at which KEY OFF given.
    if not do_show:
        state.console_state.keys_visible = False
        clear_key_row()
    else:
        state.console_state.keys_visible = True
        clear_key_row()
        for i in range(state.console_state.width/8):
            text = str(state.console_state.key_replace[i][:6])
            kcol = 1+8*i
            write_for_keys(str(i+1)[-1], kcol, state.console_state.attr)
            if state.console_state.screen_mode:
                write_for_keys(text, kcol+1, state.console_state.attr)
            else:
                if (state.console_state.attr>>4) & 0x7 == 0:    
                    write_for_keys(text, kcol+1, 0x70)
                else:
                    write_for_keys(text, kcol+1, 0x07)
        state.console_state.apage.row[24].end = state.console_state.width           

def write_for_keys(s, col, cattr):
    """ Write chars on the keys line, with no echo and some character replacements. """
    for c in s:
        if c == '\x00':
            # NUL character terminates display of a word
            break
        else:
            try:
                c = keys_line_replace_chars[c]
            except KeyError:
                pass    
            backend.put_screen_char_attr(state.console_state.apage, 25, col, c, cattr, for_keys=True)    
        col += 1
    backend.video.set_attr(state.console_state.attr)
    
#####################
# screen read/write
        
def put_char(c, do_scroll_down=False):
    # check if scroll& repositioning needed
    if state.console_state.overflow:
        state.console_state.col += 1
        state.console_state.overflow = False
    # see if we need to wrap and scroll down
    check_wrap(do_scroll_down)
    # move cursor and see if we need to scroll up
    check_pos(scroll_ok=True) 
    # put the character
    backend.put_screen_char_attr(state.console_state.apage, 
            state.console_state.row, state.console_state.col, c, state.console_state.attr)
    # adjust end of line marker
    if state.console_state.col > state.console_state.apage.row[state.console_state.row-1].end:
         state.console_state.apage.row[state.console_state.row-1].end = state.console_state.col
    # move cursor. if on col 80, only move cursor to the next row when the char is printed
    if state.console_state.col < state.console_state.width:
        state.console_state.col += 1
    else:
        state.console_state.overflow = True
    # move cursor and see if we need to scroll up
    check_pos(scroll_ok=True)
    
def check_wrap(do_scroll_down):    
    if state.console_state.col > state.console_state.width:
        # wrap line
        state.console_state.apage.row[state.console_state.row-1].wrap = True
        if do_scroll_down:
            # scroll down (make space by shifting the next rows down)
            if state.console_state.row < state.console_state.scroll_height:
                scroll_down(state.console_state.row+1)
        state.console_state.row += 1
        state.console_state.col = 1
        backend.video.move_cursor(state.console_state.row, state.console_state.col)
            
def set_pos(to_row, to_col, scroll_ok=True):
    state.console_state.overflow = False
    state.console_state.row, state.console_state.col = to_row, to_col
    check_pos(scroll_ok)
    backend.video.update_cursor_attr(state.console_state.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)
    backend.video.move_cursor(state.console_state.row,state. console_state.col)

def check_pos(scroll_ok=True):
    oldrow, oldcol = state.console_state.row, state.console_state.col
    if state.console_state.bottom_row_allowed:
        if state.console_state.row == state.console_state.height:
            state.console_state.col = min(state.console_state.width, state.console_state.col)
            if state.console_state.col < 1:
                state.console_state.col += 1    
            backend.video.move_cursor(state.console_state.row,state. console_state.col)
            return state.console_state.col == oldcol    
        else:
            # if row > height, we also end up here (eg if we do INPUT on the bottom row)
            # adjust viewport if necessary
            state.console_state.bottom_row_allowed = False
    # see if we need to move to the next row        
    if state.console_state.col > state.console_state.width:
        if state.console_state.row < state.console_state.scroll_height or scroll_ok:
            # either we don't nee to scroll, or we're allowed to
            state.console_state.col -= state.console_state.width
            state.console_state.row += 1
        else:
            # we can't scroll, so we just stop at the right border 
            state.console_state.col = state.console_state.width        
    # see if we eed to move a row up
    elif state.console_state.col < 1:
        if state.console_state.row > state.console_state.view_start:
            state.console_state.col += state.console_state.width
            state.console_state.row -= 1
        else:
            state.console_state.col = 1   
    # see if we need to scroll 
    if state.console_state.row > state.console_state.scroll_height:
        if scroll_ok:
            scroll()                # Scroll Here
        state.console_state.row = state.console_state.scroll_height
    elif state.console_state.row < state.console_state.view_start:
        state.console_state.row = state.console_state.view_start
    backend.video.move_cursor(state.console_state.row,state. console_state.col)
    # signal position change
    return state.console_state.row == oldrow and state.console_state.col == oldcol

def start_line():
    """ Move the cursor to the start of the next line, this line if empty. """
    if state.console_state.col != 1:
        for echo in backend.input_echos:
            echo('\r\n')
        check_pos(scroll_ok=True)
        set_pos(state.console_state.row + 1, 1)
    # ensure line above doesn't wrap    
    state.console_state.apage.row[state.console_state.row-2].wrap = False    
        
def write_error_message(msg, linenum):
    """ Write an error message to the console. """
    start_line()
    write(msg) 
    if linenum != None and linenum > -1 and linenum < 65535:
        write(' in %i' % linenum)
    write_line(' ')                  


#####################
# viewport / scroll area

def set_view(start=1, stop=24):
    """ Set the scroll area. """
    state.console_state.view_set = True 
    state.console_state.view_start = start 
    state.console_state.scroll_height = stop
    set_pos(start, 1)
 
def unset_view():
    """ Unset scroll area. """
    set_view()
    state.console_state.view_set = False

def clear_view():
    """ Clear the scroll area. """
    if backend.video_capabilities in ('ega', 'cga', 'cga_old'):
        # keep background, set foreground to 7
        attr_save = state.console_state.attr
        state.console_state.attr = state.console_state.attr & 0x70 | 0x7
    for r in range(state.console_state.view_start, 
                    state.console_state.scroll_height+1):
        state.console_state.apage.row[r-1].clear(state.console_state.attr)
        state.console_state.apage.row[r-1].wrap = False
    state.console_state.row = state.console_state.view_start 
    state.console_state.col = 1
    if state.console_state.bottom_row_allowed:
        last_row = state.console_state.height 
    else:
        last_row = state.console_state.scroll_height 
    backend.video.clear_rows(state.console_state.attr, 
                             state.console_state.view_start, last_row)
    backend.video.move_cursor(state.console_state.row, state.console_state.col)
    if backend.video_capabilities in ('ega', 'cga', 'cga_old'):
        # restore attr
        state.console_state.attr = attr_save
    
def scroll(from_line=None): 
    """ Scroll the scroll region up by one line, starting at from_line. """
    if from_line == None:
        from_line = state.console_state.view_start
    backend.video.scroll(from_line, state.console_state.scroll_height, 
                         state.console_state.attr)
    # sync buffers with the new screen reality:
    if state.console_state.row > from_line:
        state.console_state.row -= 1
    state.console_state.apage.row.insert(state.console_state.scroll_height, 
            backend.ScreenRow(state.console_state.attr, 
                              state.console_state.width))
    del state.console_state.apage.row[from_line-1]
   
def scroll_down(from_line):
    """ Scroll the scroll region down by one line, starting at from_line. """
    backend.video.scroll_down(from_line, state.console_state.scroll_height, 
                              state.console_state.attr)
    if state.console_state.row >= from_line:
        state.console_state.row += 1
    # sync buffers with the new screen reality:
    state.console_state.apage.row.insert(from_line - 1, 
            backend.ScreenRow(state.console_state.attr, 
                              state.console_state.width))
    del state.console_state.apage.row[state.console_state.scroll_height-1] 

################################################

prepare()

