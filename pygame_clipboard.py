""" 
PC-BASIC 3.23 - pygame_clipboard.py 
Clipboard handling 
Workaround for bugs in pygame.scrap module on OSX and Linux

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import subprocess
import pygame 
import os

import plat

# set any UTF-8 environment for subprocess
# we're assuming en_US locale always exists
env = os.environ
env['LANG'] = 'en_US.UTF-8'


def prepare():
    global scrap
    if plat.system == 'OSX':
        scrap = MacScrap()
    elif plat.system in ('Linux', 'Unknown_OS') and XScrap().init():
        scrap = XScrap()
    else:
        scrap = pygame.scrap


class MacScrap(object):
    
    def init(self):
        """ Initialise module. """
        return True

    def get(self, scrap_type):
        """ Get text from clipboard. """
        if scrap_type == 'text/plain':
            return subprocess.check_output('pbpaste', env=env)
        
    def put(self, scrap_type, thing):
        """ Put text on clipboard. """
        if scrap_type == 'text/plain':
            try:
                p = subprocess.Popen('pbcopy', env=env, stdin=subprocess.PIPE)
                p.communicate(thing)
            except subprocess.CalledProcessError:
                pass
                
    def set_mode(self, mode):
        """ Ignore the selection vs. clipboard mode """
        pass

    def get_types(self):
        """ Pretend there's always text available; we can't check. """
        return ['text/plain']
        

class XScrap(object):

    def init(self):
        """ Initialise module. Check for presence of xsel or xclip. """
        check = "command -v %s >/dev/null 2>&1"
        if subprocess.call(check % 'xsel', shell=True) == 0:
            self._command = 'xsel'
            return True
        elif subprocess.call(check % 'xclip', shell=True) == 0:
            self._command = 'xclip'
            return True
        return False

    def get(self, scrap_type):
        """ Get text from clipboard. """
        if scrap_type == 'text/plain':
            return subprocess.check_output((self._command, '-o'), env=env)
        
    def put(self, scrap_type, thing):
        """ Put text on clipboard. """
        if scrap_type == 'text/plain':
            try:
                p = subprocess.Popen((self._command, '-i'), env=env, 
                                     stdin=subprocess.PIPE)
                p.communicate(thing)
            except subprocess.CalledProcessError:
                pass

    def set_mode(self, mode):
        """ Ignore the selection vs. clipboard mode """
        pass

    def get_types(self):
        """ Pretend there's always text available; we can't check. """
        return ['text/plain']
        
    
prepare()
