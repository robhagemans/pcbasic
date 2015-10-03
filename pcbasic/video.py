"""
PC-BASIC - video.py
Base classes for video and input handlers

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import logging
import threading
import Queue
import time

import backend

plugin_dict = {}
plugin = None


def prepare():
    """ Initialise video module. """

def init(plugin_name):
    """ Launch consumer thread. """
    global plugin
    # initialise video plugin
    plugin = plugin_dict[plugin_name]()

def close():
    plugin.close()


class VideoPlugin(object):
    """ Base class for display/input interface plugins. """

    def __init__(self):
        """ Setup the interface and start the event handling thread. """
        self.ok = True
        # start video thread
        self.thread = threading.Thread(target=self._consumer_thread)
        self.thread.start()

    def close(self):
        """ Close the interface. """
        # drain signal queue (to allow for persistence) and request exit
        # signal quit and wait for thread to finish
        if backend.video_queue:
            backend.video_queue.put(backend.Event(backend.VIDEO_QUIT))
            backend.video_queue.join()
        if self.thread and self.thread.is_alive():
            # signal quit and wait for thread to finish
            self.thread.join()
            self.thread = None

    # direct calls

    def set_icon(self, mask):
        """ Set the window icon. """

    # queue management

    def _consumer_thread(self):
        """ Video signal queue consumer thread. """
        while self._drain_video_queue():
            self._check_display()
            self._check_input()
            self._sleep()

    def _check_display(self):
        """ Display update cycle. """

    def _check_input(self):
        """ Input devices update cycle. """

    def _sleep(self):
        """ Sleep a tick to avoid hogging the cpu. """
        time.sleep(0.024)

    def _drain_video_queue(self):
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
            elif signal.event_type == backend.VIDEO_SET_MODE:
                self.set_mode(signal.params)
            elif signal.event_type == backend.VIDEO_PUT_GLYPH:
                self.put_glyph(*signal.params)
            elif signal.event_type == backend.VIDEO_MOVE_CURSOR:
                self.move_cursor(*signal.params)
            elif signal.event_type == backend.VIDEO_CLEAR_ROWS:
                self.clear_rows(*signal.params)
            elif signal.event_type == backend.VIDEO_SCROLL_UP:
                self.scroll_up(*signal.params)
            elif signal.event_type == backend.VIDEO_SCROLL_DOWN:
                self.scroll_down(*signal.params)
            elif signal.event_type == backend.VIDEO_SET_PALETTE:
                self.set_palette(*signal.params)
            elif signal.event_type == backend.VIDEO_SET_CURSOR_SHAPE:
                self.set_cursor_shape(*signal.params)
            elif signal.event_type == backend.VIDEO_SET_CURSOR_ATTR:
                self.set_cursor_attr(signal.params)
            elif signal.event_type == backend.VIDEO_SHOW_CURSOR:
                self.show_cursor(signal.params)
            elif signal.event_type == backend.VIDEO_MOVE_CURSOR:
                self.move_cursor(*signal.params)
            elif signal.event_type == backend.VIDEO_SET_PAGE:
                self.set_page(*signal.params)
            elif signal.event_type == backend.VIDEO_COPY_PAGE:
                self.copy_page(*signal.params)
            elif signal.event_type == backend.VIDEO_SET_BORDER_ATTR:
                self.set_border_attr(signal.params)
            elif signal.event_type == backend.VIDEO_SET_COLORBURST:
                self.set_colorburst(*signal.params)
            elif signal.event_type == backend.VIDEO_BUILD_GLYPHS:
                self.build_glyphs(signal.params)
            elif signal.event_type == backend.VIDEO_PUT_PIXEL:
                self.put_pixel(*signal.params)
            elif signal.event_type == backend.VIDEO_PUT_INTERVAL:
                self.put_interval(*signal.params)
            elif signal.event_type == backend.VIDEO_FILL_INTERVAL:
                self.fill_interval(*signal.params)
            elif signal.event_type == backend.VIDEO_PUT_RECT:
                self.put_rect(*signal.params)
            elif signal.event_type == backend.VIDEO_FILL_RECT:
                self.fill_rect(*signal.params)
            elif signal.event_type == backend.VIDEO_SET_CAPTION:
                self.set_caption_message(signal.params)
            backend.video_queue.task_done()

    # signal handlers

    def set_mode(self, mode_info):
        """ Initialise a given text or graphics mode. """

    def set_caption_message(self, msg):
        """ Add a message to the window caption. """

    def set_palette(self, rgb_palette_0, rgb_palette_1):
        """ Build the palette. """

    def set_border_attr(self, attr):
        """ Change the border attribute. """

    def set_colorburst(self, on, rgb_palette, rgb_palette1):
        """ Change the NTSC colorburst setting. """

    def clear_rows(self, back_attr, start, stop):
        """ Clear a range of screen rows. """

    def set_page(self, vpage, apage):
        """ Set the visible and active page. """

    def copy_page(self, src, dst):
        """ Copy source to destination page. """

    def show_cursor(self, cursor_on):
        """ Change visibility of cursor. """

    def move_cursor(self, crow, ccol):
        """ Move the cursor to a new position. """

    def set_cursor_attr(self, attr):
        """ Change attribute of cursor. """

    def scroll_up(self, from_line, scroll_height, back_attr):
        """ Scroll the screen up between from_line and scroll_height. """

    def scroll_down(self, from_line, scroll_height, back_attr):
        """ Scroll the screen down between from_line and scroll_height. """

    def put_glyph(self, pagenum, row, col, c, fore, back, blink, underline, for_keys):
        """ Put a single-byte character at a given position. """

    def build_glyphs(self, new_dict):
        """ Build a dict of glyphs for use in text mode. """

    def set_cursor_shape(self, width, height, from_line, to_line):
        """ Build a sprite for the cursor. """

    def put_pixel(self, pagenum, x, y, index):
        """ Put a pixel on the screen; callback to empty character buffer. """

    def fill_rect(self, pagenum, x0, y0, x1, y1, index):
        """ Fill a rectangle in a solid attribute. """

    def fill_interval(self, pagenum, x0, x1, y, index):
        """ Fill a scanline interval in a solid attribute. """

    def put_interval(self, pagenum, x, y, colours):
        """ Write a list of attributes to a scanline interval. """

    def put_rect(self, pagenum, x0, y0, x1, y1, array):
        """ Apply numpy array [y][x] of attribytes to an area. """


prepare()
