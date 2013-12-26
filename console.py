#
# PC-BASIC 3.23 - console.py
#
# Console front-end
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# this module contains all the screen and keyboard routines
# including file access to devices SCRN: and KEYB:
#
# this module is the front-end; it needs a back-end implementation
# known back-ends: 
# - gameterm (text, graphics and sound, using pygame)
# - terminal (textmode only, using escape sequences)


import copy

import util
import error
import sound

backend=None


# number of columns, counting 1..width
width = 80
# number of rows, counting 1..height
height = 25

view_start=1
scroll_height=24
view_set=False


# cursor/current characteristics
attr = 7
row = 1
col = 1
cursor = True
cursor_is_line = False

# non-printing characters
control = ('\x07', '\x08', '\x09', '\x0a','\x0b','\x0c', '\x0d', '\x1c', '\x1d', '\x1e', '\x1f')

# incoming keys, either ascii or \00 followed by scancode 
keybuf = ''

# writing on bottom row is allowed    
last_row_is_on=False



class ScreenBuffer:
    def __init__(self, bwidth, bheight):
        # screen buffer, initialised to spaces, dim white on black
        self.charbuf = [[' ']*bwidth for x in xrange(bheight)]
        self.attrbuf = [[7]*bwidth for x in xrange(bheight)]
        # last non-white character
        self.end = [0 for x in xrange(bheight)]
        # line continues on next row (either LF or word wrap happened)
        self.wrap = [False for x in xrange(bheight)]
            
                        
        
num_pages = 1            
pages = [ ScreenBuffer(width, height) ]
vpage = pages[0]
apage = pages[0]



# officially, whether colours are displayed. in reality, SCREEN just clears the screen if this value is changed
colorswitch = True

# graphics vs text mode 
graphics_mode=False
screen_mode=0


def init():
    backend.init()

def close():
    backend.close()

def get_mode():
    global screen_mode
    return screen_mode

def idle():
    backend.idle()


def mode_info(mode):
    global width
    
    graphics_mode=True
    
    if mode==0:
        graphics_mode=False
        font_height = 16
        attr = (7,0)
        colour_depth = (32,64)
        new_width = width
        num_pages=4
        
    elif mode ==1:
        font_height =8
        attr = (3,0)
        colour_depth = (4,16)
        new_width=40
        num_pages=1
        
    elif mode==2:
        font_height =8
        attr = (1,0)
        colour_depth = (2,16)
        new_width=80
        num_pages=1    
        
    elif mode ==7:
        font_height = 8
        attr =(15,0)
        colour_depth = (16,16)
        new_width=40
        num_pages = 8
        
        
    elif mode==8:
        font_height = 8
        attr = (15,0)
        colour_depth = (16,16)
        new_width=80
        num_pages=4
        
    elif mode==9:
        font_height =14
        attr = (15,0)
        colour_depth = (16,64)
        new_width=80
        num_pages=2
        
    else:
        return None
    
    return (graphics_mode, font_height, attr, colour_depth, new_width, num_pages)
    

def set_mode(mode):
    global screen_mode, graphics_mode, cursor
    global pages, vpage, apage, num_pages
    global height, width

    screen_mode=mode
    
    (graphics_mode, font_height, attr, colour_depth, new_width, num_pages) = mode_info(mode)

    backend.set_font_height(font_height)
    set_attr (*attr)
    set_colour_depth(*colour_depth)
    
    resize(25,new_width)
    
    set_line_cursor(True)
    backend.init_screen_mode(mode)        
    show_cursor(cursor)

    
num_colours=32    
num_palette=64

def set_colour_depth(colours, palette):
    global num_colours
    global num_palette
    num_colours=colours
    num_palette=palette
    
    
def colours_ok(c):
    return (c>=0 and c<= num_colours)
    
    
def check_events():
    backend.check_events()   
    
    
def set_palette(new_palette=None):
    backend.set_palette(new_palette)


def set_palette_entry(index, colour):
    backend.set_palette_entry(index, colour)


def get_palette_entry(index):
    return backend.get_palette_entry(index)


def write(s, scroll_ok=True):
    global row, col, apage
    tab = 8
    last = ''
    for c in s:
        if c not in control or c=='\x08':                  # char 08 is written as symbol
            put_char(c)
                
        elif c=='\x09':                                     # TAB
            num = (tab - (col-1 - tab*int((col-1)/tab)))
            for _ in range(num):
                put_char(' ')
                 
        elif c == '\x0A':                                   # LF
            # exclude CR/LF
            if last != '\x0D': 
                # LF connects lines like word wrap
                apage.wrap[row-1]=True
                set_pos(row+1, 1,scroll_ok)
                
        elif c == '\x0D':   set_pos(row+1, 1,scroll_ok)     # CR
        elif c == '\x00':   put_char('\x00')                # NUL
        elif c == '\x07':   sound.beep()                  # BEL
        elif c == '\x0B':   set_pos(1,1, scroll_ok)         # HOME
        elif c == '\x0C':   clear()
        elif c == '\x1C':   set_pos(row, col+1,scroll_ok)
        elif c == '\x1D':   set_pos(row, col-1,scroll_ok)
        elif c == '\x1E':   set_pos(row-1, col,scroll_ok )
        elif c == '\x1F':   set_pos(row+1, col,scroll_ok)
        last = c






def insert_char(crow, ccol, c, cattr):
    global apage
    
    while True:
        apage.charbuf[crow-1].insert(ccol-1,c)
        apage.attrbuf[crow-1].insert(ccol-1,cattr)
        if apage.end[crow-1]<width:
            apage.charbuf[crow-1].pop()
            apage.attrbuf[crow-1].pop()
            if apage.end[crow-1] > ccol-1:
                apage.end[crow-1] += 1
            else:
                apage.end[crow-1] = ccol
            break
        else:
            if crow==scroll_height:
                scroll()
                # this is not the global row which is changed by scroll()
                crow-=1
                
            if not apage.wrap[crow-1]:
                scroll_down(crow+1)
                apage.wrap[crow-1]=True    
                
            c = apage.charbuf[crow-1].pop()
            cattr = apage.attrbuf[crow-1].pop()
            crow += 1
            ccol = 1
                  
    return crow            
        
        
def delete_char(crow, ccol):
    global apage, width 
    save_col=ccol
    
    if crow>1 and ccol==apage.end[crow-1]+1 and apage.wrap[crow-1]:
        
        # row was a LF-ending row
        apage.charbuf[crow-1] = apage.charbuf[crow-1][:ccol-1] + apage.charbuf[crow][:width-ccol+1] 
        apage.attrbuf[crow-1] = apage.attrbuf[crow-1][:ccol-1] + apage.attrbuf[crow][:width-ccol+1] 
        apage.end[crow-1] += apage.end[crow]
        if apage.end[crow-1]> width:
            apage.end[crow-1]=width
            
        while apage.wrap[crow] and crow < scroll_height:
            apage.charbuf[crow] = apage.charbuf[crow][width-ccol+1:] + apage.charbuf[crow+1][:width-ccol+1]  
            apage.attrbuf[crow] = apage.attrbuf[crow][width-ccol+1:] + apage.attrbuf[crow+1][:width-ccol+1]
            apage.end[crow] += apage.end[crow+1]
            if apage.end[crow]> width:
                apage.end[crow]=width
            crow+=1    
        
        apage.charbuf[crow] = apage.charbuf[crow][width-ccol+1:] + [' ']*(width-ccol+1) 
        apage.attrbuf[crow] = apage.attrbuf[crow][width-ccol+1:] + [attr]*(width-ccol+1)
        apage.end[crow] -= width-ccol    
        
        redraw_row(save_col-1)
        
        if apage.end[crow]<=0:
            apage.end[crow]=0
            ccol += 1
            apage.wrap[crow-1]=False
            scroll(crow+1)
        
        
        
    elif ccol <= apage.end[crow-1]:
            
        while True:            
            if (not apage.wrap[crow-1]) or (apage.end[crow-1]<width) or crow==scroll_height:
                apage.charbuf[crow-1] = apage.charbuf[crow-1][:ccol-1] + apage.charbuf[crow-1][ccol:apage.end[crow-1]] + [' '] + apage.charbuf[crow-1][apage.end[crow-1]:]
                apage.attrbuf[crow-1] = apage.attrbuf[crow-1][:ccol-1] + apage.attrbuf[crow-1][ccol:apage.end[crow-1]] + [attr] + apage.attrbuf[crow-1][apage.end[crow-1]:]
                break
                    
            else:
                # wrap and end[row-1]==width
                apage.charbuf[crow-1] = apage.charbuf[crow-1][:ccol-1] + apage.charbuf[crow-1][ccol:apage.end[crow-1]] + [ apage.charbuf[crow][0] ]
                apage.attrbuf[crow-1] = apage.attrbuf[crow-1][:ccol-1] + apage.attrbuf[crow-1][ccol:apage.end[crow-1]] + [ apage.attrbuf[crow][0] ]
                
                crow=crow+1
                ccol=1
        
        # this works from *global* row onwrds
        redraw_row(save_col-1)
        
        # this works on *local* row (last row edited)
        if apage.end[crow-1] >0:
            apage.end[crow-1] -=1
        else:
            scroll(crow)
            if crow>1:
                apage.wrap[crow-2]=False            
            

            

def read():
    global row, col, apage 
    insert = False
    
    c = ''
    inp = ''
    while c != '\x0d': 
        # wait_char returns a string of ascii and MS-DOS/GW-BASIC style keyscan codes
        c = wait_char() 
        
        pos=0
        while pos<len(c):
            if c[pos] == '\x03':            # ctrl-C, probably already caught in wait_char()
                raise error.Break()
                
            if c[pos] == '\x08':            # backspace
                inp = inp[:-1]
                
                if col==1:
                    if row>1 and apage.wrap[row-2]:
                        col=apage.end[row-2] #+1
                        row-=1
                    else:
                        col=1
                else: 
                    col=col-1
                
                delete_char(row,col)
                        
                if col >= 1:
                    set_pos(row, col)
                else:
                    set_pos(row, 1)
                        
            if c[pos] == '\x09':                  #  TAB
                inp = inp[:-1]
                if not insert:
                    set_pos(row, col+8, scroll_ok=False)
                else:
                    for _ in range(8):
                        insert_char(row,col,' ', attr)
                    redraw_row(col-1, row)
                        
                    set_pos(row,col+8)
                    
            if c[pos] == '\x0A':                   #  LF
                # moves rest of line to next line
                if col < apage.end[row-1]:
                    #end_row=row
                    for _ in range(width-col+1):
                        insert_char(row, col, ' ', attr)
                    redraw_row(col-1, row)
                    apage.end[row-1]=col-1 
                
                else:
                    crow=row
                    while apage.wrap[crow-1] and crow<scroll_height:
                        crow+=1
                    
                    if crow>=scroll_height:
                        scroll()
                        
                    scroll_down(row+1)
                            
                # LF connects lines like word wrap
                apage.wrap[row-1]=True
                set_pos(row+1, 1)
            
            elif c[pos]== '\x1B':                   # ESC
                
                clear_line(row)
                
                
            elif c[pos] not in control + ('', '\x00', '\x08'): 
                inp += c[pos]
                if insert:
                    insert_char(row,col, c[pos], attr)
                    redraw_row(col-1, row)
                    set_pos(row, col+1)
                else:    
                    put_char(c[pos], echo=True)
                    
            elif c[pos] == '\x00' and pos+1<len(c):
                pos+=1
                
                if c[pos] == '\x48':                    # up
                    insert = False
                    set_line_cursor(True)
                    set_pos(row-1, col, scroll_ok=False)
                
                elif c[pos] == '\x50':                  # down
                    insert = False
                    set_line_cursor(True)
                    set_pos(row+1, col, scroll_ok=False)
                
                elif c[pos] == '\x4D':                  # right
                    insert = False
                    set_line_cursor(True)
                    set_pos(row, col+1, scroll_ok=False)
                
                elif c[pos] == '\x4B':                  # left
                    insert = False
                    set_line_cursor(True)
                    set_pos(row, col-1, scroll_ok=False)
                
                elif c[pos] == '\x52':                  # INS
                    insert=not insert
                    set_line_cursor(not insert)  
                
                elif c[pos] == '\x53':                  # DEL
                    delete_char(row,col)
                    
                elif c[pos] == '\x47':                  # HOME
                    insert = False
                    set_line_cursor(True)
                    set_pos(1,1)
                
                elif c[pos] == '\x4F':                  # END
                    insert = False
                    set_line_cursor(True)
                    while apage.wrap[row-1] and row<height:
                        row+=1
                    set_pos(row, apage.end[row-1]+1)
                     
            pos+=1

    insert = False
    set_line_cursor(True)
                       
    return inp  
    

def read_screenline(write_endl=True, from_start=False):
    global row,col, apage
    prompt_row=row
    prompt_col=col
    
    savecurs = show_cursor() 
    read()
    show_cursor(savecurs)
    
    # find start of wrapped block
    crow = row
    while crow>1 and apage.wrap[crow-2]:
        crow-=1
    
    line = []
    # add lines 
    while crow<height:
        add = apage.charbuf[crow-1][:apage.end[crow-1]]

        # exclude prompt, if any
        if crow==prompt_row and not from_start:
            add = add[prompt_col-1:]
    
        line += add
        
        if apage.wrap[crow-1]:
            if apage.end[crow-1]<width:
                # wrap before end of line means LF
                line += '\x0a'
            crow+=1
        else:
            break
    
    # go to last line
    row = crow
    
    if write_endl:
        write(util.endl)
    
    # remove trailing whitespace 
    while len(line)>0 and line[-1] in util.whitespace:
        line = line[:-1]
   
    return ''.join(line)    



    
def clear_line(the_row):
    global apage
    
    # find start of line
    crow=the_row
    while crow>1 and apage.wrap[crow-2]:
        crow-=1
    
    #srow=crow
    while True:
        apage.charbuf[crow-1] = [' ']*width
        apage.attrbuf[crow-1] = [attr]*width
        apage.end[crow-1] = width
        if apage.wrap[crow-1]:
            crow+=1
        else:
            break    
    
    #redraw_row(0, srow)
    
    for r in range(crow, the_row, -1):
        apage.end[r-1] = 0
        apage.wrap[r-1] = False
        scroll(r)
        
    apage.end[the_row-1] = 0
    apage.wrap[the_row-1]=False
    set_pos(the_row,1)
    
    backend.clear_row(the_row, colours(attr)[1] & 0xf)
    

def start_line():
    global row, col
    
    if col!=1:
        set_pos(row+1, 1)        

def set_width(to_width):
    global height, width
    resize(height, to_width)    


def set_colorswitch(new_val):
    global colorswitch
    colorswitch=new_val



def read_screen(crow, ccol):
    global apage #,mcharbuf, attrbuf
    char = apage.charbuf[crow-1][ccol-1]
    att = apage.attrbuf[crow-1][ccol-1]
    return (char, att)




# non-blocking keystroke read
def get_char():
    backend.check_events()
    return pass_char( peek_char() )

    
# peek character from keyboard buffer
def peek_char():
    global keybuf
    
    ch =''
    if len(keybuf)>0:
        ch = keybuf[0]
        if ch=='\x00' and len(keybuf)>0:
            ch += keybuf[1]
        
    return ch 

# drop character from keyboard buffer
def pass_char(ch):
    global keybuf
    keybuf = keybuf[len(ch):]        
    return ch

# blocking keystroke read
def read_chars(num):
    for _ in range(num):
        word = ''
        a = ''
        savecurs = show_cursor(False)
        while a =='':
            backend.idle()            
            a = get_char()
        word += a[0]
        show_cursor(savecurs)
    
    return word


# blocking keystroke read
def wait_char():
    global keybuf
    
    while len(keybuf)==0:
        backend.idle()
        backend.check_events()
    
    return get_char()
       


def get_pos():
    global row, col
    return (row, col)


def get_row():
    global row
    return row

    
def get_col():
    global col
    return col        

             

def check_pos(scroll_ok=True):
    global row, col, scroll_height, width, last_row_is_on
    oldrow = row
    oldcol = col
    
    if last_row_is_on and row==height:
        if col > width:
            col = width
        elif col < 1:
            col += 1    
    else:
        # if row > height, we also end up here
        
        if col > width:
            if row < scroll_height or scroll_ok:
                col = col - width
                row += 1
            else:
                col = width        
        elif col < 1:
            if row > view_start:
                col = col + width
                row -= 1
            else:
                col = 1   
        
        # adjust viewport if necessary
        last_row_off()
               
        if row > scroll_height:
            if scroll_ok:
                scroll()                # Scroll Here
            row = scroll_height
        elif row < view_start:
            row = view_start
            
        
    if row != oldrow or col != oldcol:
        # signal position change
        return False
    
    return True
    

def set_attr(fore, back):
    global attr
    blink = fore > 0xf
    attr = ((0x8 if blink else 0x0) + (back & 0x7))*0x10 + (fore & 0xf)                   

    
def get_attr():
    global attr
    return colours(attr)            
        


def show_cursor(do_show = True):
    global cursor, graphics_mode
    prev = cursor
    cursor = do_show
    backend.show_cursor(do_show, prev)
    return prev

    
def hide_cursor():
    return show_cursor(False)


def colours(at):
    back = (at>>4)&0x7
    blink = (at>>7)
    fore = (blink*0x10) + (at&0xf)
    return (fore, back)




def clear():
    global view_set, view_start, scroll_height
    save_view_set, save_view_start, save_scroll_height = view_set, view_start, scroll_height
    set_view(1,25)
    clear_view()
    if save_view_set:
        set_view(save_view_start, save_scroll_height)
    else:
        unset_view()
        
        
def set_view(start=1,stop=24):
    global view_start, scroll_height, view_set, width, scroll_area
    global font_height, screen1, screen0, surface1,surface0
    view_set=True    
    view_start = start
    scroll_height = stop       
    backend.set_scroll_area(view_start, scroll_height, width)
    set_pos(start,1)
 
 
def unset_view():
    global view_set
    set_view()
    view_set=False
    
    
    
def last_row_on(on=True):
    global last_row_is_on
    global view_start, scroll_height, height, width
    # allow writing on bottom line    
    if last_row_is_on != on:
        if on:
            backend.set_scroll_area(view_start, height, width)
        else:
            backend.set_scroll_area(view_start, scroll_height, width)
        last_row_is_on=on


def last_row_off():
    last_row_on(False)
    


def resize(to_height, to_width):
    global height, width
    width = to_width
    height = to_height
    setup_screen(height, width)

    
def clear_all():
    global width, height
    setup_screen(height, width)
        
    
def setup_screen(to_height, to_width):    
    global num_pages, pages, vpage, apage    
    global row, col
    
    pages = []
    for i in range(num_pages):
        pages.append(ScreenBuffer(to_width, to_height))
        
    vpage = pages[0]
    apage = pages[0]

    backend.setup_screen(to_height, to_width)

    row=1
    col=1

    
    
def set_apage(page_num):
    global num_pages, apage
    
    if page_num < num_pages:
        apage=pages[page_num]
        return True
    else:
        return False    
        
def set_vpage(page_num):
    global num_pages, vpage
    backend.screen_changed=True
    
    if page_num < num_pages:
        vpage=pages[page_num]
        return True
    else:
        return False 
   
   
   
def copy_page(src, dst):
    global num_pages, pages
    global width, height
        
    if src < num_pages and dst<num_pages:
        for x in range(height):
            pages[dst].charbuf[x] = copy.copy(pages[src].charbuf[x])
            pages[dst].attrbuf[x] = copy.copy(pages[src].attrbuf[x])
            pages[dst].end[x] = pages[src].end[x]
            pages[dst].wrap[x] = pages[src].wrap[x]
    
        backend.copy_page(src,dst)
        
        return True
    else:
        return False
    
    
    
         
def clear_view():
    global row, col, apage #,charbuf, attrbuf, end, wrap,  
    global height, width, view_start, scroll_height
    global attr
    
     
    for r in range(view_start, scroll_height+1):
        apage.charbuf[r-1] = [' ']*width
        apage.attrbuf[r-1] = [attr]*width
        apage.end[r-1] = 0
        apage.wrap[r-1]=False
        
    fore, back = colours(attr)
    bg = back & 0xf
    
    row = view_start
    col = 1
     
    backend.clear_scroll_area(bg)
    



    
def set_pos(to_row, to_col, scroll_ok=True):
    global row, col, width, apage
    row = to_row
    col = to_col
    
    check_pos(scroll_ok)
 
    fore, back = colours(apage.attrbuf[row-1][col-1])
    color = fore & 0xf
    backend.set_cursor_colour(color)
    
    
def set_line_cursor(is_line=True):
    global cursor_is_line

    if is_line==cursor_is_line:
        return
    else:
        cursor_is_line = is_line
        backend.build_line_cursor(is_line)




def put_char(c, echo=False):
    global row, col, attr, height, width, apage #, charbuf, attrbuf, end
    
    # check if scroll& repositioning needed
    check_pos(scroll_ok=True)
    
    save_curs = show_cursor(False)
    if graphics_mode:
        # no blink, bg=0
        attr = attr & 0xf
        
    if not echo or not backend.echo:    
        backend.putc_at(row, col, c, attr)    
    show_cursor(save_curs)
    
    if row >0 and row <= height and col > 0 and col <= width:   
        apage.charbuf[row-1][col-1] = c
        apage.attrbuf[row-1][col-1] = attr
        if apage.end[row-1] <= col-1:
            apage.end[row-1] = col
        
    col += 1
    if col > width:
        # wrap line
        apage.wrap[row-1]=True
        row += 1
        col = 1
    
   


def redraw_row(start=0, crow=-1):
    global apage
    global row, height
    if crow==-1:
        crow=row
    
    save_curs = hide_cursor()
    while True:
        if crow >= height or crow <0:
            break
            
        for i in range(start, apage.end[crow-1]): 
            
            # redrawing changes colour attributes to current foreground (cf. GW)
            apage.attrbuf[crow-1][i]=attr
            backend.putc_at(crow, i+1, apage.charbuf[crow-1][i], apage.attrbuf[crow-1][i])
        if apage.wrap[crow-1]:
            crow+=1
            start=0
        else:
            break    

    show_cursor(save_curs)
    


def scroll(from_line=-1): 
    global row, col, apage #,charbuf, attrbuf, end
    global count, width, attr

    if from_line==-1:
        from_line=view_start
        
    save_curs = show_cursor(False)    
    backend.scroll(from_line)
    
    # sync buffers with the new screen reality:
    if row>from_line:
        row = row-1
    
    apage.charbuf.insert(scroll_height, [' ']*width)
    apage.attrbuf.insert(scroll_height, [attr]*width)
    apage.end.insert(scroll_height, 0)
    apage.wrap.insert(scroll_height, False)

    del apage.charbuf[from_line-1] 
    del apage.attrbuf[from_line-1]
    del apage.end[from_line-1]
    del apage.wrap[from_line-1]

    show_cursor(save_curs)
    
    
    

   
def scroll_down(from_line):
    global row, col, apage #,charbuf, attrbuf, end, 
    global count, width,attr

    save_curs = show_cursor(False)    
    backend.scroll_down(from_line)
    if row >= from_line:
        row = row+1
    
    # sync buffers with the new screen reality:
    apage.charbuf.insert(from_line-1, [' ']*width)
    apage.attrbuf.insert(from_line-1, [attr]*width)
    apage.end.insert(from_line-1, 0)
    apage.wrap.insert(from_line-1, False)


    del apage.charbuf[scroll_height-1] 
    del apage.attrbuf[scroll_height-1]
    del apage.end[scroll_height-1]
    del apage.wrap[scroll_height-1]
    
    show_cursor(save_curs)

