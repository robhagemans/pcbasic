""" 
PC-BASIC 3.23 - pygame_mac_scrap.py 
OSX Clipboard handling
Workaround for import errors with pygame.scrap module on OSX.

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import subprocess

env = {'LANG': 'en_US.UTF-8'}

def init():
    """ Initialise module. """
    return True

def get(scrap_type):
    """ Get text from clipboard. """
    if scrap_type == 'text/plain':
        return subprocess.check_output('pbpaste', env=env)
    
def put(scrap_type, thing):
    """ Put text on clipboard. """
    if scrap_type == 'text/plain':
        p = subprocess.Popen('pbcopy', env=env, stdin=subprocess.PIPE)
        p.communicate(thing)

def set_mode(mode):
    """ Ignore the selection vs. clipboard mode """
    pass

def get_types():
    """ Pretend there's always text available; we can't check. """
    return ['text/plain']
    
    
    
