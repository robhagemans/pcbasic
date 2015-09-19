"""
PC-BASIC - video_none.py
Filter interface - implements basic "video" I/O for redirected input streams

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import sys
import time
import threading
import Queue

import backend
import unicodepage
import plat
import redirect

# no fallback - if this doesn't work, quit
fallback = None

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


##############################################################################
# interface

def init():
    """ Initialise filter interface. """
    # use redirection echos; these are not kept in state
    redirect.set_output(sys.stdout, utf8=True)
    launch_thread()
    return True

def close():
    """ Close the filter interface. """
    # drain signal queue (to allow for persistence) and request exit
    if backend.video_queue:
        backend.video_queue.put(backend.Event(backend.VIDEO_QUIT))
        backend.video_queue.join()
    if thread and thread.is_alive():
        # signal quit and wait for thread to finish
        thread.join()

##############################################################################
# implementation

thread = None

tick_s = 0.024

def launch_thread():
    """ Launch consumer thread. """
    global thread
    thread = threading.Thread(target=consumer_thread)
    thread.start()

def consumer_thread():
    """ Audio signal queue consumer thread. """
    while drain_video_queue():
        check_keys()
        # do not hog cpu
        time.sleep(tick_s)

def drain_video_queue():
    """ Drain signal queue. """
    alive = True
    while alive:
        try:
            signal = backend.video_queue.get(False)
        except Queue.Empty:
            return True
        if signal.event_type == backend.VIDEO_QUIT:
            # close thread after task_done
            alive = False
        # drop other messages
        backend.video_queue.task_done()


###############################################################################

def check_keys():
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
        backend.keyboard_queue.put(backend.Event(backend.KEYB_CHAR, c))

prepare()
