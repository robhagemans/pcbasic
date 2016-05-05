"""
PC-BASIC - video_none.py
Filter interface - implements basic "video" I/O for redirected input streams

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import platform

import interface as video
import signals
import plat


encoding = sys.stdin.encoding or 'utf-8'

if platform.system() == 'Windows':
    from msvcrt import kbhit
else:
    import select

    def kbhit():
        """ Return whether a character is ready to be read from the keyboard. """
        return select.select([sys.stdin], [], [], 0)[0] != []

###############################################################################

def prepare():
    """ Initialise video_none module. """
    video.video_plugin_dict['none'] = VideoNone


##############################################################################

class VideoNone(video.VideoPlugin):
    """ Command-line filter interface. """

    def __init__(self, input_queue, video_queue, **kwargs):
        """ Initialise filter interface. """
        # sys.stdout output for video=none is set in redirect module
        video.VideoPlugin.__init__(self, input_queue, video_queue)
        # on unix ttys, replace input \n with \r
        # setting termios won't do the trick as it will not trigger read_line, gets too complicated
        if platform.system() != 'Windows' and plat.stdin_is_tty:
            self.lf_to_cr = True

    def _check_input(self):
        """ Handle keyboard events. """
        # avoid blocking on ttys if there's no input
        if plat.stdin_is_tty and not kbhit():
            return
        # NOTE: errors occur when backspace is used with text input
        # only the last byte is erased, not the whole utf-8 sequence
        s = sys.stdin.readline().decode(encoding, errors='ignore')
        if s == '':
            self.input_queue.put(signals.Event(signals.KEYB_CLOSED))
        for c in s:
            # replace LF -> CR if needed
            if c == u'\n' and self.lf_to_cr:
                c = u'\r'
            # check_full=False as all input may come at once
            self.input_queue.put(signals.Event(signals.KEYB_CHAR, (c, False)))

prepare()
