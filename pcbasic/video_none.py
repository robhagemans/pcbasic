"""
PC-BASIC - video_none.py
Filter interface - implements basic "video" I/O for redirected input streams

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import sys
import time

import video

import backend
import unicodepage
import plat
import redirect

# replace lf with cr
lf_to_cr = False

if plat.system == 'Windows':
    from msvcrt import kbhit
else:
    import select

    def kbhit():
        """ Return whether a character is ready to be read from the keyboard. """
        return select.select([sys.stdin], [], [], 0)[0] != []

###############################################################################

def prepare():
    """ Initialise video_none module. """
    global lf_to_cr
    # on unix ttys, replace input \n with \r
    # setting termios won't do the trick as it will not trigger read_line, gets too complicated
    if plat.system != 'Windows' and plat.stdin_is_tty:
        lf_to_cr = True
    video.plugin_dict['none'] = VideoNone


##############################################################################

class VideoNone(video.VideoPlugin):
    """ Command-line filter interface. """

    def __init__(self):
        """ Initialise filter interface. """
        # use redirection echos; these are not kept in state
        redirect.set_output(sys.stdout, utf8=True)
        video.VideoPlugin.__init__(self)

    def _check_input(self):
        """ Handle keyboard events. """
        # avoid blocking on ttys if there's no input
        if plat.stdin_is_tty and not kbhit():
            return
        s = sys.stdin.readline().decode('utf-8')
        if s == '':
            redirect.input_closed = True
        for u in s:
            c = u.encode('utf-8')
            # replace LF -> CR if needed
            if c == '\n' and lf_to_cr:
                c = '\r'
            # convert utf8 to codepage if necessary
            try:
                c = unicodepage.from_utf8(c)
            except KeyError:
                pass
            # check_full=False?
            backend.input_queue.put(backend.Event(backend.KEYB_CHAR, c))

prepare()
