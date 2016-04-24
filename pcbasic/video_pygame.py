"""
PC-BASIC - video_pygame.py
Graphical interface based on PyGame

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging

try:
    import pygame
except ImportError:
    pygame = None

try:
    import numpy
except ImportError:
    numpy = None

import plat
import signals
import scancode
from eascii import as_unicode as uea
import clipboard
import interface as video
import video_graphical


###############################################################################

def prepare():
    """ Initialise video_pygame module. """
    video.video_plugin_dict['pygame'] = VideoPygame


###############################################################################

class VideoPygame(video_graphical.VideoGraphical):
    """ Pygame-based graphical interface. """

    def __init__(self, input_queue, video_queue, **kwargs):
        """ Initialise pygame interface. """
        video_graphical.VideoGraphical.__init__(self, input_queue, video_queue, **kwargs)
        # set state objects to whatever is now in state (may have been unpickled)
        if not pygame:
            logging.warning('PyGame module not found.')
            raise video.InitFailed()
        if not numpy:
            logging.debug('NumPy module not found.')
            raise video.InitFailed()
        pygame.init()
        try:
            # poll the driver to force an exception if not initialised
            pygame.display.get_driver()
        except pygame.error:
            self._close_pygame()
            logging.warning('No suitable display driver for PyGame.')
            raise video.InitFailed()
        # display & border
        # display buffer
        self.canvas = []
        # border attribute
        self.border_attr = 0
        # palette and colours
        # composite colour artifacts
        self.composite_artifacts = False
        # working palette - attribute index in blue channel
        self.work_palette = [(0, 0, index) for index in range(256)]
        # display palettes for blink states 0, 1
        self.show_palette = [None, None]
        # composite palette
        try:
            self.composite_640_palette = video_graphical.composite_640[
                                                            self.composite_card]
        except KeyError:
            self.composite_640_palette = video_graphical.composite_640['cga']
        # text attributes supported
        self.mode_has_blink = True
        # update cycle
        # update flag
        self.screen_changed = True
        # refresh cycle parameters
        self._cycle = 0
        self.last_cycle = 0
        self._cycle_time = 120
        self.blink_cycles = 5
        # cursor
        # cursor shape
        self.cursor = None
        # current cursor location
        self.last_row = 1
        self.last_col = 1
        # cursor is visible
        self.cursor_visible = True
        # buffer for text under cursor
        self.under_top_left = None
        # fonts
        # prebuilt glyphs
        self.glyph_dict = {}
        # joystick and mouse
        # available joysticks
        self.joysticks = []
        #
        # get physical screen dimensions (needs to be called before set_mode)
        display_info = pygame.display.Info()
        self.physical_size = display_info.current_w, display_info.current_h
        # determine initial display size
        self.display_size = self._find_display_size(640, 480, self.border_width)
        self._set_icon(kwargs['icon'])
        # first set the screen non-resizeable, to trick things like maximus into not full-screening
        # I hate it when applications do this ;)
        try:
            if not self.fullscreen:
                pygame.display.set_mode(self.display_size, 0)
            self._resize_display(*self.display_size)
        except pygame.error:
            self._close_pygame()
            logging.warning('Could not initialise PyGame display')
            raise video.InitFailed()
        if self.smooth and self.display.get_bitsize() < 24:
            logging.warning("Smooth scaling not available on this display (depth %d < 24)", self.display.get_bitsize())
            self.smooth = False
        pygame.display.set_caption(self.caption)
        pygame.key.set_repeat(500, 24)
        # load an all-black 16-colour game palette to get started
        self.set_palette([(0,0,0)]*16, None)
        pygame.joystick.init()
        self.joysticks = [pygame.joystick.Joystick(x)
                            for x in range(pygame.joystick.get_count())]
        for j in self.joysticks:
            j.init()
        # if a joystick is present, its axes report 128 for mid, not 0
        for joy in range(len(self.joysticks)):
            for axis in (0, 1):
                self.input_queue.put(signals.Event(signals.STICK_MOVED,
                                                      (joy, axis, 128)))
        # mouse setups
        buttons = { 'left': 1, 'middle': 2, 'right': 3, 'none': -1 }
        copy_paste = kwargs.get('copy-paste', ('left', 'middle'))
        self.mousebutton_copy = buttons[copy_paste[0]]
        self.mousebutton_paste = buttons[copy_paste[1]]
        self.mousebutton_pen = buttons[kwargs.get('pen', 'right')]
        self.move_cursor(0, 0)
        self.set_page(0, 0)
        # set_mode shoul dbe first event on queue
        self.f11_active = False
        self.altgr = kwargs['altgr']
        if not self.altgr:
            key_to_scan[pygame.K_RALT] = scancode.ALT
            mod_to_scan[pygame.KMOD_RALT] = scancode.ALT
        self.clipboard_handler = get_clipboard_handler()

    def __exit__(self, type, value, traceback):
        """ Close the pygame interface. """
        video.VideoPlugin.__exit__(self, type, value, traceback)
        self._close_pygame()

    def _close_pygame(self):
        """ Close pygame modules and displays. """
        # if pygame import failed, close() is called while pygame is None
        if pygame:
            pygame.joystick.quit()
            pygame.display.quit()
            pygame.quit()

    def _set_icon(self, mask):
        """ Set the window icon. """
        height, width = len(mask), len(mask[0])
        icon = pygame.Surface((width, height), depth=8)
        icon.fill(0)
        icon.blit(glyph_to_surface(mask), (0, 0, width, height))
        icon.set_palette_at(0, (0, 0, 0))
        icon.set_palette_at(1, (0xff, 0xff, 0xff))
        pygame.transform.scale2x(icon)
        pygame.transform.scale2x(icon)
        pygame.display.set_icon(icon)


    ###########################################################################
    # input cycle

    def _check_input(self):
        """ Handle screen and interface events. """
        # check and handle pygame events
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                self._handle_key_down(event)
            if event.type == pygame.KEYUP:
                self._handle_key_up(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # copy, paste and pen may be on the same button, so no elifs
                if event.button == self.mousebutton_copy:
                    # LEFT button: copy
                    pos = self._normalise_pos(*event.pos)
                    self.clipboard.start(1 + pos[1] // self.font_height,
                            1 + (pos[0]+self.font_width//2) // self.font_width)
                if event.button == self.mousebutton_paste:
                    # MIDDLE button: paste
                    text = self.clipboard_handler.paste(mouse=True)
                    self.clipboard.paste(text)
                if event.button == self.mousebutton_pen:
                    # right mouse button is a pen press
                    self.input_queue.put(signals.Event(signals.PEN_DOWN,
                                                self._normalise_pos(*event.pos)))
            elif event.type == pygame.MOUSEBUTTONUP:
                self.input_queue.put(signals.Event(signals.PEN_UP))
                if event.button == self.mousebutton_copy:
                    self.clipboard.copy(mouse=True)
                    self.clipboard.stop()
            elif event.type == pygame.MOUSEMOTION:
                pos = self._normalise_pos(*event.pos)
                self.input_queue.put(signals.Event(signals.PEN_MOVED, pos))
                if self.clipboard.active():
                    self.clipboard.move(1 + pos[1] // self.font_height,
                           1 + (pos[0]+self.font_width//2) // self.font_width)
            elif event.type == pygame.JOYBUTTONDOWN:
                self.input_queue.put(signals.Event(signals.STICK_DOWN,
                                                      (event.joy, event.button)))
            elif event.type == pygame.JOYBUTTONUP:
                self.input_queue.put(signals.Event(signals.STICK_UP,
                                                      (event.joy, event.button)))
            elif event.type == pygame.JOYAXISMOTION:
                self.input_queue.put(signals.Event(signals.STICK_MOVED,
                                                      (event.joy, event.axis,
                                                      int(event.value*127 + 128))))
            elif event.type == pygame.VIDEORESIZE:
                self.fullscreen = False
                self._resize_display(event.w, event.h)
            elif event.type == pygame.QUIT:
                if self.nokill:
                    self.set_caption_message('to exit type <CTRL+BREAK> <ESC> SYSTEM')
                else:
                    self.input_queue.put(signals.Event(signals.KEYB_QUIT))

    def _handle_key_down(self, e):
        """ Handle key-down event. """
        # get scancode
        scan = key_to_scan.get(e.key, None)
        # get modifiers
        mod = [s for m, s in mod_to_scan.iteritems() if e.mod & m]
        # get eascii
        try:
            if e.mod & pygame.KMOD_LALT or (not self.altgr and e.mod & pygame.KMOD_RALT):
                c = alt_key_to_eascii[e.key]
            elif e.mod & pygame.KMOD_CTRL:
                c = ctrl_key_to_eascii[e.key]
            elif e.mod & pygame.KMOD_SHIFT:
                c = shift_key_to_eascii[e.key]
            else:
                c = key_to_eascii[e.key]
        except KeyError:
            key = e.key
            if e.mod & pygame.KMOD_CTRL and key >= ord('a') and key <= ord('z'):
                c = unichr(key - ord('a') + 1)
            elif e.mod & pygame.KMOD_CTRL and key >= ord('[') and key <= ord('_'):
                c = unichr(key - ord('A') + 1)
            else:
                c = e.unicode
        # handle F11 home-key
        if e.key == pygame.K_F11:
            self.f11_active = True
            self.clipboard.start(self.cursor_row, self.cursor_col)
        elif self.f11_active:
            # F11+f to toggle fullscreen mode
            if e.key == pygame.K_f:
                self.fullscreen = not self.fullscreen
                self._resize_display(*self._find_display_size(
                                self.size[0], self.size[1], self.border_width))
            self.clipboard.handle_key(scan, c)
        else:
            # double NUL characters, as single NUL signals e-ASCII
            if c == u'\0':
                c = uea.NUL
            # fix missing ascii for numeric keypad on Windows
            if e.mod & pygame.KMOD_NUM:
                try:
                    c = key_to_eascii_num[e.key]
                except KeyError:
                    pass
            # insert into keyboard queue
            self.input_queue.put(signals.Event(
                                    signals.KEYB_DOWN, (c, scan, mod)))

    def _handle_key_up(self, e):
        """ Handle key-up event. """
        if e.key == pygame.K_F11:
            self.clipboard.stop()
            self.f11_active = False
        # last key released gets remembered
        try:
            self.input_queue.put(signals.Event(
                                    signals.KEYB_UP, (key_to_scan[e.key],)))
        except KeyError:
            pass


    ###########################################################################
    # screen drawing cycle

    def _sleep(self):
        """ Sleep a tick to avoid hogging the cpu. """
        pygame.time.wait(24)

    def _check_display(self):
        """ Check screen and blink events; update screen if necessary. """
        self.blink_state = 0
        if self.mode_has_blink:
            self.blink_state = 0 if self._cycle < self.blink_cycles * 2 else 1
            if self._cycle % self.blink_cycles == 0:
                self.screen_changed = True
        if self.cursor_visible and (
                (self.cursor_row != self.last_row) or
                (self.cursor_col != self.last_col)):
            self.screen_changed = True
        tock = pygame.time.get_ticks()
        if (tock - self.last_cycle) >= (self._cycle_time/self.blink_cycles):
            self.last_cycle = tock
            self._cycle += 1
            if self._cycle == self.blink_cycles*4:
                self._cycle = 0
        if self.screen_changed:
            self._do_flip()
            self.screen_changed = False

    def _do_flip(self):
        """ Draw the canvas to the screen. """
        # create the screen that will be stretched onto the display
        border_x = int(self.size[0] * self.border_width / 200.)
        border_y = int(self.size[1] * self.border_width / 200.)
        # surface depth and flags match those of canvas
        screen = pygame.Surface((self.size[0] + 2*border_x,
                                 self.size[1] + 2*border_y),
                                 0, self.canvas[self.vpagenum])
        screen.set_palette(self.work_palette)
        # border colour
        border_colour = pygame.Color(0, 0, self.border_attr % self.num_fore_attrs)
        screen.fill(border_colour)
        screen.blit(self.canvas[self.vpagenum], (border_x, border_y))
        # subsurface referencing the canvas area
        workscreen = screen.subsurface((border_x, border_y, self.size[0], self.size[1]))
        self._draw_cursor(workscreen)
        if self.clipboard.active():
            create_feedback(workscreen, self.clipboard.selection_rect)
        if self.composite_artifacts:
            screen = apply_composite_artifacts(screen, 4//self.bitsperpixel)
            screen.set_palette(self.composite_640_palette)
        else:
            screen.set_palette(self.show_palette[self.blink_state])
        if self.smooth:
            pygame.transform.smoothscale(screen.convert(self.display),
                                         self.display.get_size(), self.display)
        else:
            pygame.transform.scale(screen.convert(self.display),
                                   self.display.get_size(), self.display)
        pygame.display.flip()

    def _draw_cursor(self, screen):
        """ Draw the cursor on the surface provided. """
        if not self.cursor_visible or self.vpagenum != self.apagenum:
            return
        # copy screen under cursor
        self.under_top_left = (  (self.cursor_col-1) * self.font_width,
                                 (self.cursor_row-1) * self.font_height)
        under_char_area = pygame.Rect(
                (self.cursor_col-1) * self.font_width,
                (self.cursor_row-1) * self.font_height,
                self.cursor_width, self.font_height)
        if self.text_mode:
            # cursor is visible - to be done every cycle between 5 and 10, 15 and 20
            if self._cycle/self.blink_cycles in (1, 3):
                screen.blit(self.cursor, (
                        (self.cursor_col-1) * self.font_width,
                        (self.cursor_row-1) * self.font_height) )
        else:
            index = self.cursor_attr % self.num_fore_attrs
            # reference the destination area
            dest_array = pygame.surfarray.pixels2d(
                    screen.subsurface(pygame.Rect(
                        (self.cursor_col-1) * self.font_width,
                        (self.cursor_row-1) * self.font_height + self.cursor_from,
                        self.cursor_width,
                        self.cursor_to - self.cursor_from + 1)))
            dest_array ^= index
        self.last_row = self.cursor_row
        self.last_col = self.cursor_col

    ###########################################################################
    # miscellaneous helper functions

    def _resize_display(self, width, height):
        """ Change the display size. """
        flags = pygame.RESIZABLE
        if self.fullscreen:
            flags |= pygame.FULLSCREEN | pygame.NOFRAME
        self.display = pygame.display.set_mode((width, height), flags)
        self.window_width, self.window_height = width, height
        # load display if requested
        self.screen_changed = True


    ###########################################################################
    # signal handlers

    def set_mode(self, mode_info):
        """ Initialise a given text or graphics mode. """
        self.text_mode = mode_info.is_text_mode
        # unpack mode info struct
        self.font_height = mode_info.font_height
        self.font_width = mode_info.font_width
        self.num_pages = mode_info.num_pages
        self.mode_has_blink = mode_info.has_blink
        self.mode_has_artifacts = False
        if not self.text_mode:
            self.bitsperpixel = mode_info.bitsperpixel
            self.mode_has_artifacts = mode_info.supports_artifacts
        # logical size
        self.size = (mode_info.pixel_width, mode_info.pixel_height)
        self._resize_display(*self._find_display_size(
                                self.size[0], self.size[1], self.border_width))
        # set standard cursor
        self.set_cursor_shape(self.font_width, self.font_height,
                              0, self.font_height)
        # whole screen (blink on & off)
        self.canvas = [ pygame.Surface(self.size, depth=8)
                        for _ in range(self.num_pages)]
        for i in range(self.num_pages):
            self.canvas[i].set_palette(self.work_palette)
        # initialise clipboard
        self.clipboard = video_graphical.ClipboardInterface(self,
                mode_info.width, mode_info.height)
        self.screen_changed = True

    def set_caption_message(self, msg):
        """ Add a message to the window caption. """
        if msg:
            pygame.display.set_caption(self.caption + ' - ' + msg)
        else:
            pygame.display.set_caption(self.caption)

    def set_clipboard_text(self, text, mouse):
        """ Put text on the clipboard. """
        self.clipboard_handler.copy(text, mouse)

    def set_palette(self, rgb_palette_0, rgb_palette_1):
        """ Build the palette. """
        self.num_fore_attrs = min(16, len(rgb_palette_0))
        self.num_back_attrs = min(8, self.num_fore_attrs)
        rgb_palette_1 = rgb_palette_1 or rgb_palette_0
        # fill up the 8-bit palette with all combinations we need
        # blink states: 0 light up, 1 light down
        # bottom 128 are non-blink, top 128 blink to background
        self.show_palette[0] = rgb_palette_0[:self.num_fore_attrs] * (256//self.num_fore_attrs)
        self.show_palette[1] = rgb_palette_1[:self.num_fore_attrs] * (128//self.num_fore_attrs)
        for b in rgb_palette_1[:self.num_back_attrs] * (128//self.num_fore_attrs//self.num_back_attrs):
            self.show_palette[1] += [b]*self.num_fore_attrs
        self.screen_changed = True

    def set_border_attr(self, attr):
        """ Change the border attribute. """
        self.border_attr = attr
        self.screen_changed = True

    def set_colorburst(self, on, rgb_palette, rgb_palette1):
        """ Change the NTSC colorburst setting. """
        self.set_palette(rgb_palette, rgb_palette1)
        self.composite_artifacts = on and self.mode_has_artifacts and self.composite_monitor

    def clear_rows(self, back_attr, start, stop):
        """ Clear a range of screen rows. """
        bg = (0, 0, back_attr)
        scroll_area = pygame.Rect(0, (start-1)*self.font_height,
                                  self.size[0], (stop-start+1)*self.font_height)
        self.canvas[self.apagenum].fill(bg, scroll_area)
        self.screen_changed = True

    def set_page(self, vpage, apage):
        """ Set the visible and active page. """
        self.vpagenum, self.apagenum = vpage, apage
        self.screen_changed = True

    def copy_page(self, src, dst):
        """ Copy source to destination page. """
        self.canvas[dst].blit(self.canvas[src], (0, 0))
        self.screen_changed = True

    def show_cursor(self, cursor_on):
        """ Change visibility of cursor. """
        self.cursor_visible = cursor_on
        self.screen_changed = True

    def move_cursor(self, crow, ccol):
        """ Move the cursor to a new position. """
        self.cursor_row, self.cursor_col = crow, ccol

    def set_cursor_attr(self, attr):
        """ Change attribute of cursor. """
        self.cursor_attr = attr % self.num_fore_attrs
        self.cursor.set_palette_at(254,
                            pygame.Color(0, self.cursor_attr, self.cursor_attr))

    def scroll_up(self, from_line, scroll_height, back_attr):
        """ Scroll the screen up between from_line and scroll_height. """
        temp_scroll_area = pygame.Rect(
                0, (from_line-1)*self.font_height,
                self.size[0], (scroll_height-from_line+1) * self.font_height)
        # scroll
        self.canvas[self.apagenum].set_clip(temp_scroll_area)
        self.canvas[self.apagenum].scroll(0, -self.font_height)
        # empty new line
        bg = (0, 0, back_attr)
        self.canvas[self.apagenum].fill(bg, (
                                   0, (scroll_height-1) * self.font_height,
                                   self.size[0], self.font_height))
        self.canvas[self.apagenum].set_clip(None)
        self.screen_changed = True

    def scroll_down(self, from_line, scroll_height, back_attr):
        """ Scroll the screen down between from_line and scroll_height. """
        temp_scroll_area = pygame.Rect(
                0, (from_line-1) * self.font_height,
                self.size[0], (scroll_height-from_line+1) * self.font_height)
        self.canvas[self.apagenum].set_clip(temp_scroll_area)
        self.canvas[self.apagenum].scroll(0, self.font_height)
        # empty new line
        bg = (0, 0, back_attr)
        self.canvas[self.apagenum].fill(bg, (
                                    0, (from_line-1) * self.font_height,
                                    self.size[0], self.font_height))
        self.canvas[self.apagenum].set_clip(None)
        self.screen_changed = True

    def put_glyph(self, pagenum, row, col, cp, is_fullwidth, fore, back, blink, underline, for_keys):
        """ Put a single-byte character at a given position. """
        if not self.text_mode:
            # in graphics mode, a put_rect call does the actual drawing
            return
        color = (0, 0, fore + self.num_fore_attrs*back + 128*blink)
        bg = (0, 0, back)
        x0, y0 = (col-1)*self.font_width, (row-1)*self.font_height
        if cp == '\0':
            # guaranteed to be blank, saves time on some BLOADs
            self.canvas[pagenum].fill(bg,
                                    (x0, y0, self.font_width, self.font_height))
        else:
            try:
                glyph = self.glyph_dict[cp]
            except KeyError:
                if '\0' not in self.glyph_dict:
                    logging.error('No glyph received for code point 0')
                    return
                logging.warning('No glyph received for code point %s', cp.encode('hex'))
                glyph = self.glyph_dict['\0']
            if glyph.get_palette_at(0) != bg:
                glyph.set_palette_at(0, bg)
            if glyph.get_palette_at(1) != color:
                glyph.set_palette_at(1, color)
            self.canvas[pagenum].blit(glyph, (x0, y0))
        if underline:
            self.canvas[pagenum].fill(color, (x0, y0 + self.font_height - 1,
                                                            self.font_width, 1))
        self.screen_changed = True

    def build_glyphs(self, new_dict):
        """ Build a dict of glyphs for use in text mode. """
        for char, glyph in new_dict.iteritems():
            self.glyph_dict[char] = glyph_to_surface(glyph)

    def set_cursor_shape(self, width, height, from_line, to_line):
        """ Build a sprite for the cursor. """
        self.cursor_width = width
        self.cursor_from, self.cursor_to = from_line, to_line
        self.cursor = pygame.Surface((width, height), depth=8)
        color, bg = 254, 255
        self.cursor.set_colorkey(bg)
        self.cursor.fill(bg)
        self.cursor.fill(color, (0, from_line, width,
                                    min(to_line-from_line+1, height-from_line)))
        self.screen_changed = True

    def put_pixel(self, pagenum, x, y, index):
        """ Put a pixel on the screen; callback to empty character buffer. """
        self.canvas[pagenum].set_at((x,y), index)
        self.screen_changed = True

    def fill_rect(self, pagenum, x0, y0, x1, y1, index):
        """ Fill a rectangle in a solid attribute. """
        rect = pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)
        self.canvas[pagenum].fill(index, rect)
        self.screen_changed = True

    def fill_interval(self, pagenum, x0, x1, y, index):
        """ Fill a scanline interval in a solid attribute. """
        dx = x1 - x0 + 1
        self.canvas[pagenum].fill(index, (x0, y, dx, 1))
        self.screen_changed = True

    def put_interval(self, pagenum, x, y, colours):
        """ Write a list of attributes to a scanline interval. """
        # reference the interval on the canvas
        pygame.surfarray.pixels2d(self.canvas[pagenum]
                )[x:x+len(colours), y] = numpy.array(colours).astype(int)
        self.screen_changed = True

    def put_rect(self, pagenum, x0, y0, x1, y1, array):
        """ Apply numpy array [y][x] of attribytes to an area. """
        if (x1 < x0) or (y1 < y0):
            return
        # reference the destination area
        pygame.surfarray.pixels2d(self.canvas[pagenum].subsurface(
            pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)))[:] = numpy.array(array).T
        self.screen_changed = True

###############################################################################
# clipboard handling

class PygameClipboard(clipboard.Clipboard):
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
        """ Put unicode text on clipboard. """
        if mouse:
            pygame.scrap.set_mode(pygame.SCRAP_SELECTION)
        else:
            pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        try:
            if plat.system == 'Windows':
                # on Windows, encode as utf-16 without FF FE byte order mark and null-terminate
                # but give it a utf-8 MIME type, because that's how Windows likes it
                pygame.scrap.put('text/plain;charset=utf-8', text.encode('utf-16le', 'replace') + '\0\0')
            else:
                pygame.scrap.put(pygame.SCRAP_TEXT, text.encode('utf-8', 'replace'))
        except KeyError:
            logging.debug('Clipboard copy failed for clip %s', repr(text))

    def paste(self, mouse=False):
        """ Return unicode text from clipboard. """
        if mouse:
            pygame.scrap.set_mode(pygame.SCRAP_SELECTION)
        else:
            pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        us = ''
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
                us = us.decode('utf-16le', errors='replace')
            # remove null-terminator
            us = us[:us.find(u'\0')]
        else:
            us = us.decode('utf-8', errors='replace')
        return us or u''

def get_clipboard_handler():
    """ Get a working Clipboard handler object. """
    # Pygame.Scrap doesn't work on OSX and is buggy on Linux; avoid if we can
    if plat.system == 'OSX':
        handler = clipboard.MacClipboard()
    elif plat.system in ('Linux', 'Unknown_OS') and clipboard.XClipboard().ok:
        handler = clipboard.XClipboard()
    else:
        handler = PygameClipboard()
    if not handler.ok:
        logging.warning('Clipboard copy and paste not available.')
        handler = clipboard.Clipboard()
    return handler

def create_feedback(surface, selection_rects):
    """ Create visual feedback for selection onto a surface. """
    for r in selection_rects:
        work_area = surface.subsurface(pygame.Rect(r))
        orig = work_area.copy()
        # add 1 to the color as a highlight
        orig.fill(pygame.Color(0, 0, 1))
        work_area.blit(orig, (0, 0), special_flags=pygame.BLEND_ADD)


###############################################################################


if pygame:
    # these are PC keyboard scancodes
    key_to_scan = {
        # top row
        pygame.K_ESCAPE: scancode.ESCAPE, pygame.K_1: scancode.N1,
        pygame.K_2: scancode.N2, pygame.K_3: scancode.N3,
        pygame.K_4: scancode.N4, pygame.K_5: scancode.N5,
        pygame.K_6: scancode.N6, pygame.K_7: scancode.N7,
        pygame.K_8: scancode.N8, pygame.K_9: scancode.N9,
        pygame.K_0: scancode.N0, pygame.K_MINUS: scancode.MINUS,
        pygame.K_EQUALS: scancode.EQUALS,
        pygame.K_BACKSPACE: scancode.BACKSPACE,
        # row 1
        pygame.K_TAB: scancode.TAB, pygame.K_q: scancode.q,
        pygame.K_w: scancode.w, pygame.K_e: scancode.e, pygame.K_r: scancode.r,
        pygame.K_t: scancode.t, pygame.K_y: scancode.y, pygame.K_u: scancode.u,
        pygame.K_i: scancode.i, pygame.K_o: scancode.o, pygame.K_p: scancode.p,
        pygame.K_LEFTBRACKET: scancode.LEFTBRACKET,
        pygame.K_RIGHTBRACKET: scancode.RIGHTBRACKET,
        pygame.K_RETURN: scancode.RETURN, pygame.K_KP_ENTER: scancode.RETURN,
        # row 2
        pygame.K_RCTRL: scancode.CTRL, pygame.K_LCTRL: scancode.CTRL,
        pygame.K_a: scancode.a, pygame.K_s: scancode.s, pygame.K_d: scancode.d,
        pygame.K_f: scancode.f, pygame.K_g: scancode.g, pygame.K_h: scancode.h,
        pygame.K_j: scancode.j, pygame.K_k: scancode.k, pygame.K_l: scancode.l,
        pygame.K_SEMICOLON: scancode.SEMICOLON, pygame.K_QUOTE: scancode.QUOTE,
        pygame.K_BACKQUOTE: scancode.BACKQUOTE,
        # row 3
        pygame.K_LSHIFT: scancode.LSHIFT,
        pygame.K_BACKSLASH: scancode.BACKSLASH,
        pygame.K_z: scancode.z, pygame.K_x: scancode.x, pygame.K_c: scancode.c,
        pygame.K_v: scancode.v, pygame.K_b: scancode.b, pygame.K_n: scancode.n,
        pygame.K_m: scancode.m, pygame.K_COMMA: scancode.COMMA,
        pygame.K_PERIOD: scancode.PERIOD, pygame.K_SLASH: scancode.SLASH,
        pygame.K_RSHIFT: scancode.RSHIFT, pygame.K_PRINT: scancode.PRINT,
        pygame.K_SYSREQ: scancode.SYSREQ,
        pygame.K_LALT: scancode.ALT,
        pygame.K_SPACE: scancode.SPACE, pygame.K_CAPSLOCK: scancode.CAPSLOCK,
        # function key row
        pygame.K_F1: scancode.F1, pygame.K_F2: scancode.F2,
        pygame.K_F3: scancode.F3, pygame.K_F4: scancode.F4,
        pygame.K_F5: scancode.F5, pygame.K_F6: scancode.F6,
        pygame.K_F7: scancode.F7, pygame.K_F8: scancode.F8,
        pygame.K_F9: scancode.F9, pygame.K_F10: scancode.F10,
        pygame.K_F11: scancode.F11, pygame.K_F12: scancode.F12,
        # top middle
        pygame.K_NUMLOCK: scancode.NUMLOCK,
        pygame.K_SCROLLOCK: scancode.SCROLLOCK,
        # keypad
        pygame.K_KP7: scancode.KP7, pygame.K_HOME: scancode.HOME,
        pygame.K_KP8: scancode.KP8, pygame.K_UP: scancode.UP,
        pygame.K_KP9: scancode.KP9, pygame.K_PAGEUP: scancode.PAGEUP,
        pygame.K_KP_MINUS: scancode.KPMINUS,
        pygame.K_KP4: scancode.KP4, pygame.K_LEFT: scancode.LEFT,
        pygame.K_KP5: scancode.KP5,
        pygame.K_KP6: scancode.KP6, pygame.K_RIGHT: scancode.RIGHT,
        pygame.K_KP_PLUS: scancode.KPPLUS,
        pygame.K_KP1: scancode.KP1, pygame.K_END: scancode.END,
        pygame.K_KP2: scancode.KP2, pygame.K_DOWN: scancode.DOWN,
        pygame.K_KP3: scancode.KP3, pygame.K_PAGEDOWN: scancode.PAGEDOWN,
        pygame.K_KP0: scancode.KP0, pygame.K_INSERT: scancode.INSERT,
        # keypad dot, times, div, enter ?
        # various
        pygame.K_DELETE: scancode.DELETE,
        pygame.K_PAUSE: scancode.BREAK,
        pygame.K_BREAK: scancode.BREAK,
    }


    key_to_eascii = {
        pygame.K_F1: uea.F1,
        pygame.K_F2: uea.F2,
        pygame.K_F3: uea.F3,
        pygame.K_F4: uea.F4,
        pygame.K_F5: uea.F5,
        pygame.K_F6: uea.F6,
        pygame.K_F7: uea.F7,
        pygame.K_F8: uea.F8,
        pygame.K_F9: uea.F9,
        pygame.K_F10: uea.F10,
        pygame.K_F11: uea.F11,
        pygame.K_F12: uea.F12,
        pygame.K_HOME: uea.HOME,
        pygame.K_UP: uea.UP,
        pygame.K_PAGEUP: uea.PAGEUP,
        pygame.K_LEFT: uea.LEFT,
        pygame.K_RIGHT: uea.RIGHT,
        pygame.K_END: uea.END,
        pygame.K_DOWN: uea.DOWN,
        pygame.K_PAGEDOWN: uea.PAGEDOWN,
        pygame.K_ESCAPE: uea.ESCAPE,
        pygame.K_BACKSPACE: uea.BACKSPACE,
        pygame.K_TAB: uea.TAB,
        pygame.K_RETURN: uea.RETURN,
        pygame.K_KP_ENTER: uea.RETURN,
        pygame.K_SPACE: uea.SPACE,
        pygame.K_INSERT: uea.INSERT,
        pygame.K_DELETE: uea.DELETE,
    }

    shift_key_to_eascii = {
        pygame.K_F1: uea.SHIFT_F1,
        pygame.K_F2: uea.SHIFT_F2,
        pygame.K_F3: uea.SHIFT_F3,
        pygame.K_F4: uea.SHIFT_F4,
        pygame.K_F5: uea.SHIFT_F5,
        pygame.K_F6: uea.SHIFT_F6,
        pygame.K_F7: uea.SHIFT_F7,
        pygame.K_F8: uea.SHIFT_F8,
        pygame.K_F9: uea.SHIFT_F9,
        pygame.K_F10: uea.SHIFT_F10,
        pygame.K_F11: uea.SHIFT_F11,
        pygame.K_F12: uea.SHIFT_F12,
        pygame.K_HOME: uea.SHIFT_HOME,
        pygame.K_UP: uea.SHIFT_UP,
        pygame.K_PAGEUP: uea.SHIFT_PAGEUP,
        pygame.K_LEFT: uea.SHIFT_LEFT,
        pygame.K_RIGHT: uea.SHIFT_RIGHT,
        pygame.K_END: uea.SHIFT_END,
        pygame.K_DOWN: uea.SHIFT_DOWN,
        pygame.K_PAGEDOWN: uea.SHIFT_PAGEDOWN,
        pygame.K_ESCAPE: uea.SHIFT_ESCAPE,
        pygame.K_BACKSPACE: uea.SHIFT_BACKSPACE,
        pygame.K_TAB: uea.SHIFT_TAB,
        pygame.K_RETURN: uea.SHIFT_RETURN,
        pygame.K_KP_ENTER: uea.SHIFT_RETURN,
        pygame.K_SPACE: uea.SHIFT_SPACE,
        pygame.K_INSERT: uea.SHIFT_INSERT,
        pygame.K_DELETE: uea.SHIFT_DELETE,
        pygame.K_KP5: uea.SHIFT_KP5,
    }

    ctrl_key_to_eascii = {
        pygame.K_F1: uea.CTRL_F1,
        pygame.K_F2: uea.CTRL_F2,
        pygame.K_F3: uea.CTRL_F3,
        pygame.K_F4: uea.CTRL_F4,
        pygame.K_F5: uea.CTRL_F5,
        pygame.K_F6: uea.CTRL_F6,
        pygame.K_F7: uea.CTRL_F7,
        pygame.K_F8: uea.CTRL_F8,
        pygame.K_F9: uea.CTRL_F9,
        pygame.K_F10: uea.CTRL_F10,
        pygame.K_F11: uea.CTRL_F11,
        pygame.K_F12: uea.CTRL_F12,
        pygame.K_HOME: uea.CTRL_HOME,
        pygame.K_PAGEUP: uea.CTRL_PAGEUP,
        pygame.K_LEFT: uea.CTRL_LEFT,
        pygame.K_RIGHT: uea.CTRL_RIGHT,
        pygame.K_END: uea.CTRL_END,
        pygame.K_PAGEDOWN: uea.CTRL_PAGEDOWN,
        pygame.K_ESCAPE: uea.CTRL_ESCAPE,
        pygame.K_BACKSPACE: uea.CTRL_BACKSPACE,
        pygame.K_TAB: uea.CTRL_TAB,
        pygame.K_RETURN: uea.CTRL_RETURN,
        pygame.K_KP_ENTER: uea.CTRL_RETURN,
        pygame.K_SPACE: uea.CTRL_SPACE,
        pygame.K_PRINT: uea.CTRL_PRINT,
        pygame.K_2: uea.CTRL_2,
        pygame.K_6: uea.CTRL_6,
        pygame.K_MINUS: uea.CTRL_MINUS,
    }

    alt_key_to_eascii = {
        pygame.K_1: uea.ALT_1,
        pygame.K_2: uea.ALT_2,
        pygame.K_3: uea.ALT_3,
        pygame.K_4: uea.ALT_4,
        pygame.K_5: uea.ALT_5,
        pygame.K_6: uea.ALT_6,
        pygame.K_7: uea.ALT_7,
        pygame.K_8: uea.ALT_8,
        pygame.K_9: uea.ALT_9,
        pygame.K_0: uea.ALT_0,
        pygame.K_MINUS: uea.ALT_MINUS,
        pygame.K_EQUALS: uea.ALT_EQUALS,
        pygame.K_q: uea.ALT_q,
        pygame.K_w: uea.ALT_w,
        pygame.K_e: uea.ALT_e,
        pygame.K_r: uea.ALT_r,
        pygame.K_t: uea.ALT_t,
        pygame.K_y: uea.ALT_y,
        pygame.K_u: uea.ALT_u,
        pygame.K_i: uea.ALT_i,
        pygame.K_o: uea.ALT_o,
        pygame.K_p: uea.ALT_p,
        pygame.K_a: uea.ALT_a,
        pygame.K_s: uea.ALT_s,
        pygame.K_d: uea.ALT_d,
        pygame.K_f: uea.ALT_f,
        pygame.K_g: uea.ALT_g,
        pygame.K_h: uea.ALT_h,
        pygame.K_j: uea.ALT_j,
        pygame.K_k: uea.ALT_k,
        pygame.K_l: uea.ALT_l,
        pygame.K_z: uea.ALT_z,
        pygame.K_x: uea.ALT_x,
        pygame.K_c: uea.ALT_c,
        pygame.K_v: uea.ALT_v,
        pygame.K_b: uea.ALT_b,
        pygame.K_n: uea.ALT_n,
        pygame.K_m: uea.ALT_m,
        pygame.K_F1: uea.ALT_F1,
        pygame.K_F2: uea.ALT_F2,
        pygame.K_F3: uea.ALT_F3,
        pygame.K_F4: uea.ALT_F4,
        pygame.K_F5: uea.ALT_F5,
        pygame.K_F6: uea.ALT_F6,
        pygame.K_F7: uea.ALT_F7,
        pygame.K_F8: uea.ALT_F8,
        pygame.K_F9: uea.ALT_F9,
        pygame.K_F10: uea.ALT_F10,
        pygame.K_F11: uea.ALT_F11,
        pygame.K_F12: uea.ALT_F12,
        pygame.K_BACKSPACE: uea.ALT_BACKSPACE,
        pygame.K_TAB: uea.ALT_TAB,
        pygame.K_RETURN: uea.ALT_RETURN,
        pygame.K_KP_ENTER: uea.ALT_RETURN,
        pygame.K_SPACE: uea.ALT_SPACE,
        pygame.K_PRINT: uea.ALT_PRINT,
        pygame.K_KP5: uea.ALT_KP5,
    }

    mod_to_scan = {
        pygame.KMOD_LSHIFT: scancode.LSHIFT,
        pygame.KMOD_RSHIFT: scancode.RSHIFT,
        pygame.KMOD_LCTRL: scancode.CTRL,
        pygame.KMOD_RCTRL: scancode.CTRL,
        pygame.KMOD_LALT: scancode.ALT,
    }

    key_to_eascii_num = {
        pygame.K_KP0: u'0',
        pygame.K_KP1: u'1',
        pygame.K_KP2: u'2',
        pygame.K_KP3: u'3',
        pygame.K_KP4: u'4',
        pygame.K_KP5: u'5',
        pygame.K_KP6: u'6',
        pygame.K_KP7: u'7',
        pygame.K_KP8: u'8',
        pygame.K_KP9: u'9',
    }


def apply_composite_artifacts(screen, pixels=4):
    """ Process the canvas to apply composite colour artifacts. """
    src_array = pygame.surfarray.array2d(screen)
    return pygame.surfarray.make_surface(
                    video_graphical.apply_composite_artifacts(src_array, pixels))


def glyph_to_surface(glyph):
    """ Build a sprite surface for the given character glyph. """
    glyph = numpy.asarray(glyph).T
    surf = pygame.Surface(glyph.shape, depth=8)
    pygame.surfarray.pixels2d(surf)[:] = glyph
    return surf


prepare()
