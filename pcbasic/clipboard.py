"""
PC-BASIC - clipboard.py
Clipboard handling

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import subprocess

import plat

encoding = plat.preferred_encoding


def prepare():
    """ Prepare the clipboard module. """


class Clipboard(object):
    """ Clipboard handling interface. """

    def __init__(self):
        """ Initialise the clipboard handler. """
        self.ok = True

    def copy(self, text, mouse=False):
        """ Put unicode text on clipboard. """
        pass

    def paste(self, mouse=False):
        """ Return unicode text from clipboard. """
        return u''


class MacClipboard(Clipboard):
    """ Clipboard handling for OSX. """

    def paste(self, mouse=False):
        """ Get unicode text from clipboard. """
        return (subprocess.check_output('pbpaste').decode(encoding, 'replace')
                .replace('\r\n','\r').replace('\n', '\r'))

    def copy(self, text, mouse=False):
        """ Put unicode text on clipboard. """
        try:
            p = subprocess.Popen('pbcopy', stdin=subprocess.PIPE)
            p.communicate(text.encode(encoding, 'replace'))
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
        """ Get unicode text from clipboard. """
        if mouse:
            output = subprocess.check_output((self._command, '-o'))
        else:
            output = subprocess.check_output(
                                [self._command, '-o'] + self._notmouse)
        return (output.decode(encoding, 'replace')
                .replace('\r\n','\r').replace('\n', '\r'))

    def copy(self, text, mouse=False):
        """ Put unicode text on clipboard. """
        try:
            if mouse:
                p = subprocess.Popen((self._command, '-i'),
                                     stdin=subprocess.PIPE)
            else:
                p = subprocess.Popen([self._command, '-i'] + self._notmouse,
                                     stdin=subprocess.PIPE)
            p.communicate(text.encode(encoding, 'replace'))
        except subprocess.CalledProcessError:
            pass

prepare()
