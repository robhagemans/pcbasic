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

import error
import console
 
shell = 'CMD'    
shell_cmd = shell + ' /c'

    
def disk_free(path):
    free_bytes = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes))
    return free_bytes.value
   
def process_stdout(p, stream):
    while True:
        c = stream.read(1)
        if c != '': # and c != '\r':
            if c!= '\r':
                console.write(c)
            else:
                console.check_events()
        elif p.poll() != None:
            break        

def spawn_interactive_shell(cmd):
    p = subprocess.Popen( cmd.split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True )
    outp = threading.Thread(target=process_stdout, args=(p, p.stdout))
    outp.daemon = True
    outp.start()
    errp = threading.Thread(target=process_stdout, args=(p, p.stderr))
    errp.daemon = True
    errp.start()
    chars = 0
    while p.poll() == None:
        console.idle()
        c = console.get_char()
        if p.poll () != None:
            break
        else:    
            if c in ('\r', '\n'): 
                # fix double echo after enter press
                console.write('\x1D'*chars)
                chars = 0
                p.stdin.write('\r\n')
            elif c != '':
                p.stdin.write(c)
                # windows only seems to echo this to the pipe after enter pressed
                console.write(c)
                chars +=1
    outp.join()
    errp.join()
        
        
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
        
