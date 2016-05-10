"""
PC-BASIC - interface.base
Base classes for video, input and audio handlers

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import Queue

from ..basic import signals


class InitFailed(Exception):
    """ Initialisation failed. """


###############################################################################
# video plugin


class VideoPlugin(object):
    """ Base class for display/input interface plugins. """

    def __init__(self, input_queue, video_queue):
        """ Setup the interface. """
        self.alive = True
        self.screen_changed = False
        self.input_queue = input_queue
        self.video_queue = video_queue

    def __exit__(self, type, value, traceback):
        """ Close the interface. """

    def __enter__(self):
        """ Final initialisation. """
        return self

    def cycle(self):
        """ Video/input event cycle. """
        if self.alive:
            self.alive = self._drain_video_queue()
        if self.alive:
            self._check_display()
            self._check_input()

    def _check_display(self):
        """ Display update cycle. """

    def _check_input(self):
        """ Input devices update cycle. """

    def _drain_video_queue(self):
        """ Drain signal queue. """
        alive = True
        while alive:
            try:
                signal = self.video_queue.get(False)
            except Queue.Empty:
                return True
            if signal.event_type == signals.VIDEO_QUIT:
                # close thread after task_done
                alive = False
            elif signal.event_type == signals.VIDEO_SET_MODE:
                self.set_mode(signal.params)
            elif signal.event_type == signals.VIDEO_PUT_GLYPH:
                self.put_glyph(*signal.params)
            elif signal.event_type == signals.VIDEO_MOVE_CURSOR:
                self.move_cursor(*signal.params)
            elif signal.event_type == signals.VIDEO_CLEAR_ROWS:
                self.clear_rows(*signal.params)
            elif signal.event_type == signals.VIDEO_SCROLL_UP:
                self.scroll_up(*signal.params)
            elif signal.event_type == signals.VIDEO_SCROLL_DOWN:
                self.scroll_down(*signal.params)
            elif signal.event_type == signals.VIDEO_SET_PALETTE:
                self.set_palette(*signal.params)
            elif signal.event_type == signals.VIDEO_SET_CURSOR_SHAPE:
                self.set_cursor_shape(*signal.params)
            elif signal.event_type == signals.VIDEO_SET_CURSOR_ATTR:
                self.set_cursor_attr(signal.params)
            elif signal.event_type == signals.VIDEO_SHOW_CURSOR:
                self.show_cursor(signal.params)
            elif signal.event_type == signals.VIDEO_MOVE_CURSOR:
                self.move_cursor(*signal.params)
            elif signal.event_type == signals.VIDEO_SET_PAGE:
                self.set_page(*signal.params)
            elif signal.event_type == signals.VIDEO_COPY_PAGE:
                self.copy_page(*signal.params)
            elif signal.event_type == signals.VIDEO_SET_BORDER_ATTR:
                self.set_border_attr(signal.params)
            elif signal.event_type == signals.VIDEO_SET_COLORBURST:
                self.set_colorburst(*signal.params)
            elif signal.event_type == signals.VIDEO_BUILD_GLYPHS:
                self.build_glyphs(signal.params)
            elif signal.event_type == signals.VIDEO_PUT_PIXEL:
                self.put_pixel(*signal.params)
            elif signal.event_type == signals.VIDEO_PUT_INTERVAL:
                self.put_interval(*signal.params)
            elif signal.event_type == signals.VIDEO_FILL_INTERVAL:
                self.fill_interval(*signal.params)
            elif signal.event_type == signals.VIDEO_PUT_RECT:
                self.put_rect(*signal.params)
            elif signal.event_type == signals.VIDEO_FILL_RECT:
                self.fill_rect(*signal.params)
            elif signal.event_type == signals.VIDEO_SET_CAPTION:
                self.set_caption_message(signal.params)
            elif signal.event_type == signals.VIDEO_SET_CLIPBOARD_TEXT:
                self.set_clipboard_text(*signal.params)
            elif signal.event_type == signals.VIDEO_SET_CODEPAGE:
                self.set_codepage(signal.params)
            self.video_queue.task_done()

    # signal handlers

    def set_mode(self, mode_info):
        """ Initialise a given text or graphics mode. """

    def set_caption_message(self, msg):
        """ Add a message to the window caption. """

    def set_clipboard_text(self, text, mouse):
        """ Put text on the clipboard. """

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

    def put_glyph(self, pagenum, row, col, cp, is_fullwidth, fore, back, blink, underline, for_keys):
        """ Put a character at a given position. """

    def build_glyphs(self, new_dict):
        """ Build a dict of glyphs for use in text mode. """

    def set_codepage(self, new_codepage):
        """ Set codepage used in sending characters. """

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

###############################################################################
# audio plugin


class AudioPlugin(object):
    """ Base class for audio interface plugins. """

    def __init__(self, tone_queue, message_queue):
        """ Setup the audio interface and start the event handling thread. """
        # sound generators for sounds not played yet
        # if not None, something is playing
        self.next_tone = [ None, None, None, None ]
        self.alive = True
        self.playing = False
        self.tone_queue = tone_queue
        self.message_queue = message_queue

    def __exit__(self, type, value, traceback):
        """ Close the audio interface. """

    def __enter__(self):
        """ Perform any necessary initialisations. """
        return self

    def cycle(self):
        """ Audio event cycle. """
        if self.alive:
            self.alive = self._drain_message_queue()
        if self.alive:
            self.playing = not (self._drain_tone_queue() and self.next_tone == [None, None, None, None])
            self._play_sound()

    def _play_sound(self):
        """ Play the sounds queued."""

    def _drain_message_queue(self):
        """ Process sound system messages. """
        return False

    def _drain_tone_queue(self):
        """ Process tone events. """
        return True
