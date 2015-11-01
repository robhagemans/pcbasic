"""
PC-BASIC - clipboard.py
Clipboard handling

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import subprocess
import os
import logging

import plat
import unicodepage

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


class MacClipboard(Clipboard):
    """ Clipboard handling for OSX. """

    def paste(self, mouse=False):
        """ Get text from clipboard. """
        return utf8_to_cp(subprocess.check_output('pbpaste', env=env))

    def copy(self, thing, mouse=False):
        """ Put text on clipboard. """
        try:
            p = subprocess.Popen('pbcopy', env=env, stdin=subprocess.PIPE)
            p.communicate(thing)
        except subprocess.CalledProcessError:
            pass


class XClipboard(Clipboard):
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
            output = subprocess.check_output((self._command, '-o'), env=env)
        else:
            output = subprocess.check_output(
                                [self._command, '-o'] + self._notmouse, env=env)
        return utf8_to_cp(output)

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


def utf8_to_cp(text_utf8):
    """ Convert clipboard utf8 string to codepage. """
    # ignore any bad UTF8 characters from outside
    text = ''
    for u in text_utf8.decode('utf-8', 'ignore'):
        c = u.encode('utf-8')
        last = ''
        if c == '\n':
            if last != '\r':
                char = '\r'
            else:
                char = ''
        else:
            try:
                char = unicodepage.from_utf8(c)
            except KeyError:
                char = c
        text += char
        last = c
    return text

prepare()
