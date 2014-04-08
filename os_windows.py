#
# PC-BASIC 3.23  - os_windows.py
#
# Windows-specific OS utilities
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os
import msvcrt
import ctypes
import string
import fnmatch
import subprocess
import threading
import win32print
import win32ui
import win32gui
import win32api
import win32con

import error
import console
 
shell_interactive = 'CMD'    
shell_cmd = 'CMD /c'

file_path = os.path.dirname(os.path.realpath(__file__))

drives = { '@': os.path.join(file_path, 'info') }
current_drive = os.path.abspath(os.getcwd()).split(':')[0]
drive_cwd = { '@': '' }

# get all drives in use by windows
# if started from CMD.EXE, get the 'current wworking dir' for each drive
# if not in CMD.EXE, there's only one cwd
def store_drives():
    global drives, drive_cwd
    save_current = os.getcwd()
    for letter in win32api.GetLogicalDriveStrings().split(':\\\x00')[:-1]:
        try:
            os.chdir(letter + ':')
            cwd = win32api.GetShortPathName(os.getcwd())
            # must not start with \\
            drive_cwd[letter] = cwd[3:]  
            drives[letter] = cwd[:3]
        except WindowsError:
            pass    
    os.chdir(save_current)    

store_drives()
    
def set_icon():    
    icon = win32gui.LoadImage(0, os.path.join(file_path, 'resources\\pcbasic.ico'), 
        win32gui.IMAGE_ICON, 0, 0, win32gui.LR_DEFAULTSIZE | win32gui.LR_LOADFROMFILE);
    if icon:
        hwnd = win32api.GetFocus()
        #Change both icons to the same icon handle.
        win32api.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, icon);
        win32api.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, icon);

        #This will ensure that the application icon gets changed too.
        win32api.SendMessage(win32gui.GetWindow(hwnd, win32con.GW_OWNER), win32con.WM_SETICON, win32con.ICON_SMALL, icon);
        win32api.SendMessage(win32gui.GetWindow(hwnd, win32con.GW_OWNER), win32con.WM_SETICON, win32con.ICON_BIG, icon);

#set_icon()    
def gui_init():
    set_icon()    
    
def disk_free(path):
    free_bytes = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes))
    return free_bytes.value
   
def process_stdout(p, stream):
    while True:
        c = stream.read(1)
        if c != '': 
            if c!= '\r':
                console.write(c)
            else:
                console.check_events()
        elif p.poll() != None:
            break        

def spawn_interactive_shell(cmd):
    p = subprocess.Popen( str(cmd).split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True )
    outp = threading.Thread(target=process_stdout, args=(p, p.stdout))
    outp.daemon = True
    outp.start()
    errp = threading.Thread(target=process_stdout, args=(p, p.stderr))
    errp.daemon = True
    errp.start()
    chars = 0
    word = ''
    while p.poll() == None:
        console.idle()
        c = console.get_char()
        print repr(c)
        if p.poll () != None:
            break
        else:    
            if c in ('\r', '\n'): 
                # fix double echo after enter press
                console.write('\x1D'*chars)
                chars = 0
                p.stdin.write(word + '\r\n')
                word = ''
            elif c != '':
                # workaround for WINE that seems to attach a CR to each letter: only send to pipe when enter pressed
                # rather than p.stdin.write(c)
                word += c
                # windows only seems to echo this to the pipe after enter pressed (even if directly written to pipe)
                console.write(c)
                chars += 1
    outp.join()
    errp.join()

# get windows short name
def dossify(path, name):
    if not path:
        path = current_drive
    try:
        shortname = win32api.GetShortPathName(os.path.join(path, name)).upper()
    except Exception as e:
        # something went wrong, show as dots in FILES
        return "........", "..."
    split = shortname.split('\\')[-1].split('.')
    trunk, ext = split[0], ''
    if len(split)>1:
        ext = split[1]
    if len(trunk)>8 or len(ext)>3:
        # on some file systems, ShortPathName returns the long name
        trunk = trunk[:8]
        ext = '...'    
    return trunk, ext    


# print to Windows printer
def line_print(printbuf, printer_name):        
    if printer_name == '' or printer_name=='default':
        printer_name = win32print.GetDefaultPrinter()
    handle = win32ui.CreateDC()
    handle.CreatePrinterDC(printer_name)
    handle.StartDoc("PC-BASIC 3_23 Document")
    handle.StartPage()
    # a4 = 210x297mm = 4950x7001px; Letter = 216x280mm=5091x6600px; 
    # 65 tall, 100 wide with 50x50 margins works for US letter
    # 96 wide works for A4 with 75 x-margin
    y, yinc = 50, 100
    lines = printbuf.split('\r\n')
    slines = []
    for l in lines:
        slines += [l[i:i+96] for i in range(0, len(l), 96)]
    for line in slines:
        handle.TextOut(75, y, line) 
        y += yinc
        if y > 6500:  
            y = 50
            handle.EndPage()
            handle.StartPage()
    handle.EndPage()
    handle.EndDoc()       
        
