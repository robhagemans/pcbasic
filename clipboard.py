""" 
PC-BASIC 3.23 - clipboard.py 
Clipboard handling 

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import subprocess
try:
    import pygame 
except ImportError:
    pygame = None
import os

import plat
import logging

# set any UTF-8 environment for subprocess
# we're assuming en_US locale always exists
env = os.environ
env['LANG'] = 'en_US.UTF-8'

def prepare():
    """ Prepare the clipboard module. """
    pass


class Clipboard(object):
    """ Clipboard handling interface. """
    
    def __init__(self):
        """ Initialise the clipboard handler. """
        self.ok = True
    
    def copy(self, text_utf8, mouse=False):
        """ Put text on clipboard. """
        pass
        
    def paste(self, mouse=False):
        """ Return text from clipboard. """
        return ''    


class PygameClipboard(Clipboard):
    """ Clipboard handling using Pygame.Scrap. """

    # text type we look for in the clipboard
    text = ('UTF8_STRING', 'text/plain;charset=utf-8', 'text/plain',
            'TEXT', 'STRING')
        
    def __init__(self):
        """ Initialise the clipboard handler. """
        try:
            pygame.scrap.init()
            self.ok = True
        except Exception:
            if pygame:
                logging.warning('PyGame.Scrap clipboard handling module not found.')    
            self.ok = False    

    def copy(self, text, mouse=False):
        """ Put text on clipboard. """
        if mouse:
            pygame.scrap.set_mode(pygame.SCRAP_SELECTION)
        else:
            pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        try: 
            if plat.system == 'Windows':
                # on Windows, encode as utf-16 without FF FE byte order mark and null-terminate
                pygame.scrap.put('text/plain;charset=utf-8', text.decode('utf-8').encode('utf-16le') + '\0\0')
            else:    
                pygame.scrap.put(pygame.SCRAP_TEXT, text)
        except KeyError:
            logging.debug('Clipboard copy failed for clip %s', repr(text))    
        
    def paste(self, mouse=False):
        """ Return text from clipboard. """
        if mouse:
            pygame.scrap.set_mode(pygame.SCRAP_SELECTION)
        else:
            pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        us = None
        available = pygame.scrap.get_types()
        for text_type in self.text:
            if text_type not in available:
                continue
            us = pygame.scrap.get(text_type)
            if us:
                break            
        if plat.system == 'Windows':
            if text_type == 'text/plain;charset=utf-8':
                # it's lying, it's giving us UTF16 little-endian
                # ignore any bad UTF16 characters from outside
                us = us.decode('utf-16le', 'ignore')
            # null-terminated strings
            us = us[:us.find('\0')] 
            us = us.encode('utf-8')
        if not us:
            return ''
        return us


class MacClipboard(object):
    """ Clipboard handling for OSX. """
    
    def paste(self, mouse=False):
        """ Get text from clipboard. """
        return subprocess.check_output('pbpaste', env=env)
        
    def copy(self, thing, mouse=False):
        """ Put text on clipboard. """
        try:
            p = subprocess.Popen('pbcopy', env=env, stdin=subprocess.PIPE)
            p.communicate(thing)
        except subprocess.CalledProcessError:
            pass
    

class XClipboard(object):
    """ Clipboard handling for X Window System using xsel or xclip. """

    def __init__(self):
        """ Check for presence of xsel or xclip. """
        check = "command -v %s >/dev/null 2>&1"
        if subprocess.call(check % 'xsel', shell=True) == 0:
            self._command = 'xsel'
            self._notmouse = ['-b']
            self.ok = True
        elif subprocess.call(check % 'xclip', shell=True) == 0:
            self._command = 'xclip'
            self._notmouse = ['-selection', 'clipboard']
            self.ok = True
        else:
            self.ok = False
            
    def paste(self, mouse=False):
        """ Get text from clipboard. """
        if mouse:
            return subprocess.check_output((self._command, '-o'), env=env)
        else:
            return subprocess.check_output(
                                [self._command, '-o'] + self._notmouse, env=env)
        
    def copy(self, thing, mouse=False):
        """ Put text on clipboard. """
        try:
            if mouse:
                p = subprocess.Popen((self._command, '-i'),
                                     env=env, stdin=subprocess.PIPE)
            else:
                p = subprocess.Popen([self._command, '-i'] + self._notmouse, 
                                     env=env, stdin=subprocess.PIPE)
            p.communicate(thing)
        except subprocess.CalledProcessError:
            pass


def get_handler():
    """ Get a working Clipboard handler object. """
    # Pygame.Scrap doesn't work on OSX and is buggy on Linux; avoid if we can
    if plat.system == 'OSX':
        clipboard = MacClipboard()
    elif plat.system in ('Linux', 'Unknown_OS') and XClipboard().ok:
        clipboard = XClipboard()
    else:
        clipboard = PygameClipboard()
    if not clipboard.ok:
        logging.warning('Clipboard copy and paste not available.')        
        clipboard = Clipboard()
    return clipboard


prepare()
