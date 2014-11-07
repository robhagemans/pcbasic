""" 
PC-BASIC 3.23 - pygame_mac_scrap.py 

OSX Clipboard handling
Workaround for import errors with pygame.scrap module on OSX.

(c) 2013, 2014 Rob Hagemans 

This file is released under the GNU GPL version 3. 
please see text file COPYING for licence terms.
"""

import subprocess

env = {'LANG': 'en_US.UTF-8'}

def init():
    return True

def get(scrap_type):
    if scrap_type == 'text/plain':
        return subprocess.check_output('pbpaste', env=env)
    
def put(scrap_type, thing):
    if scrap_type == 'text/plain':
        p = subprocess.Popen('pbcopy', env=env, stdin=subprocess.PIPE)
        p.communicate(thing)

def set_mode (mode):
    # ignore the selection vs. clipboard mode
    pass

def get_types ():
    # pretend there's always text available; we can't check.
    return ['text/plain']
    
    
    
