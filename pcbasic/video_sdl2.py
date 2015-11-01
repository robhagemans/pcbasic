"""
PC-BASIC - video_sdl2.py
Graphical interface based on PySDL2

(c) 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import logging
import Queue
import ctypes

try:
    import sdl2
except ImportError:
    sdl2 = None

try:
    import sdl2.sdlgfx
except ImportError:
    pass

try:
    import numpy
except ImportError:
    numpy = None

import plat
import config
import unicodepage
import backend
import typeface
import scancode
# for operation tokens for PUT
import basictoken as tk
import clipboard
import video
import video_graphical


###############################################################################

def prepare():
    """ Initialise video_sdl2 module. """
    video.plugin_dict['sdl2'] = VideoSDL2


###############################################################################

class VideoSDL2(video_graphical.VideoGraphical):
    """ SDL2-based graphical interface. """

    def __init__(self, **kwargs):
        """ Initialise SDL2 interface. """
        if not sdl2:
            logging.debug('PySDL2 module not found.')
            raise video.InitFailed()
        if not numpy:
            logging.debug('NumPy module not found.')
            raise video.InitFailed()
        video_graphical.VideoGraphical.__init__(self, **kwargs)
        # initialise SDL
        sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
        # display & border
        # border attribute
        self.border_attr = 0
        # palette and colours
        # composite colour artifacts
        self.composite_artifacts = False
        # display palettes for blink states 0, 1
        self.show_palette = [sdl2.SDL_AllocPalette(256), sdl2.SDL_AllocPalette(256)]
        # update cycle
        # refresh cycle parameters
        self.cycle = 0
        self.last_cycle = 0
        self.cycle_time = 120
        self.blink_cycles = 5
        # cursor
        # current cursor location
        self.last_row = 1
        self.last_col = 1
        # cursor is visible
        self.cursor_visible = True
        # get physical screen dimensions (needs to be called before set_mode)
        display_mode = sdl2.SDL_DisplayMode()
        sdl2.SDL_GetCurrentDisplayMode(0, ctypes.byref(display_mode))
        self.physical_size = display_mode.w, display_mode.h
        # load the icon
        self.icon = kwargs['icon']
        # create the window initially, size will be corrected later
        self.display = None
        self._do_create_window(640, 400)
        # load an all-black 16-colour game palette to get started
        self.set_palette([(0,0,0)]*16, None)
        self.move_cursor(1, 1)
        self.set_page(0, 0)
        self.set_mode(kwargs['initial_mode'])
        # support for CGA composite
        self.composite_palette = sdl2.SDL_AllocPalette(256)
        composite_colors = video_graphical.composite_640.get(
                self.composite_card, video_graphical.composite_640['cga'])
        colors = (sdl2.SDL_Color * 256)(*[sdl2.SDL_Color(r, g, b, 255) for (r, g, b) in composite_colors])
        sdl2.SDL_SetPaletteColors(self.composite_palette, colors, 0, 256)
        # check if we can honour scaling=smooth
        if self.smooth:
            pixelformat = self.display_surface.contents.format
            if pixelformat.contents.BitsPerPixel != 32:
                logging.warning('Smooth scaling not available on this display of %d-bit colour depth: needs 32-bit', self.display_surface.format.contents.BitsPerPixel)
                self.smooth = False
            if not hasattr(sdl2, 'sdlgfx'):
                logging.warning('Smooth scaling not available: SDL_GFX extension not found.')
                self.smooth = False
        # mouse setups
        buttons = {'left': sdl2.SDL_BUTTON_LEFT, 'middle': sdl2.SDL_BUTTON_MIDDLE,
                   'right': sdl2.SDL_BUTTON_RIGHT, 'none': None}
        copy_paste = kwargs.get('copy-paste', ('left', 'middle'))
        self.mousebutton_copy = buttons[copy_paste[0]]
        self.mousebutton_paste = buttons[copy_paste[1]]
        self.mousebutton_pen = buttons[kwargs.get('pen', 'right')]
        # available joysticks
        num_joysticks = sdl2.SDL_NumJoysticks()
        for j in range(num_joysticks):
            sdl2.SDL_JoystickOpen(j)
            # if a joystick is present, its axes report 128 for mid, not 0
            for axis in (0, 1):
                backend.input_queue.put(backend.Event(backend.STICK_MOVED,
                                                      (j, axis, 128)))
        self.f11_active = False

    def close(self):
        """ Close the SDL2 interface. """
        video.VideoPlugin.close(self)
        if sdl2 and numpy:
            # free windows
            sdl2.SDL_DestroyWindow(self.display)
            # free surfaces
            for s in self.canvas:
                sdl2.SDL_FreeSurface(s)
            sdl2.SDL_FreeSurface(self.work_surface)
            sdl2.SDL_FreeSurface(self.overlay)
            # free palettes
            for p in self.show_palette:
                sdl2.SDL_FreePalette(p)
            sdl2.SDL_FreePalette(self.composite_palette)
            # close SDL2
            sdl2.SDL_Quit()

    def _set_icon(self):
        """ Set the icon on the SDL window. """
        mask = numpy.array(self.icon).T.repeat(2, 0).repeat(2, 1)
        icon = sdl2.SDL_CreateRGBSurface(0, mask.shape[0], mask.shape[1], 8, 0, 0, 0, 0)
        pixels2d(icon.contents)[:] = mask
        # icon palette (black & white)
        icon_palette = sdl2.SDL_AllocPalette(256)
        icon_colors = [ sdl2.SDL_Color(x, x, x, 255) for x in [0, 255] + [255]*254 ]
        sdl2.SDL_SetPaletteColors(icon_palette, (sdl2.SDL_Color * 256)(*icon_colors), 0, 2)
        sdl2.SDL_SetSurfacePalette(icon, icon_palette)
        sdl2.SDL_SetWindowIcon(self.display, icon)
        sdl2.SDL_FreeSurface(icon)
        sdl2.SDL_FreePalette(icon_palette)

    def _do_create_window(self, width, height):
        """ Create a new SDL window """
        flags = sdl2.SDL_WINDOW_RESIZABLE | sdl2.SDL_WINDOW_SHOWN
        if self.fullscreen:
             flags |= sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_BORDERLESS
        sdl2.SDL_DestroyWindow(self.display)
        self.display = sdl2.SDL_CreateWindow(self.caption,
                    sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED,
                    width, height, flags)
        self._set_icon()
        self.display_surface = sdl2.SDL_GetWindowSurface(self.display)
        self.screen_changed = True


    ###########################################################################
    # input cycle

    def _check_input(self):
        """ Handle screen and interface events. """
        # check and handle input events
        self.last_down = None
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_KEYDOWN:
                self._handle_key_down(event)
            elif event.type == sdl2.SDL_KEYUP:
                self._handle_key_up(event)
            elif event.type == sdl2.SDL_TEXTINPUT:
                self._handle_text_input(event)
            elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                pos = self._normalise_pos(event.button.x, event.button.y)
                # copy, paste and pen may be on the same button, so no elifs
                if event.button.button == self.mousebutton_copy:
                    # LEFT button: copy
                    self.clipboard.start(1 + pos[1] // self.font_height,
                            1 + (pos[0]+self.font_width//2) // self.font_width)
                if event.button.button == self.mousebutton_paste:
                    # MIDDLE button: paste
                    self.clipboard.paste(mouse=True)
                if event.button.button == self.mousebutton_pen:
                    # right mouse button is a pen press
                    backend.input_queue.put(backend.Event(backend.PEN_DOWN, pos))
            elif event.type == sdl2.SDL_MOUSEBUTTONUP:
                backend.input_queue.put(backend.Event(backend.PEN_UP))
                if event.button.button == self.mousebutton_copy:
                    self.clipboard.copy(mouse=True)
                    self.clipboard.stop()
            elif event.type == sdl2.SDL_MOUSEMOTION:
                pos = self._normalise_pos(event.motion.x, event.motion.y)
                backend.input_queue.put(backend.Event(backend.PEN_MOVED, pos))
                if self.clipboard.active():
                    self.clipboard.move(1 + pos[1] // self.font_height,
                           1 + (pos[0]+self.font_width//2) // self.font_width)
            elif event.type == sdl2.SDL_JOYBUTTONDOWN:
                backend.input_queue.put(backend.Event(backend.STICK_DOWN,
                                    (event.jbutton.which, event.jbutton.button)))
            elif event.type == sdl2.SDL_JOYBUTTONUP:
                backend.input_queue.put(backend.Event(backend.STICK_UP,
                                    (event.jbutton.which, event.jbutton.button)))
            elif event.type == sdl2.SDL_JOYAXISMOTION:
                backend.input_queue.put(backend.Event(backend.STICK_MOVED,
                                    (event.jaxis.which, event.jaxis.axis,
                                    int((event.jaxis.value/32768.)*127 + 128))))
            elif event.type == sdl2.SDL_WINDOWEVENT:
                if event.window.event == sdl2.SDL_WINDOWEVENT_RESIZED:
                    self._resize_display(event.window.data1, event.window.data2)
            elif event.type == sdl2.SDL_QUIT:
                if self.nokill:
                    self.set_caption_message('to exit type <CTRL+BREAK> <ESC> SYSTEM')
                else:
                    backend.input_queue.put(backend.Event(backend.KEYB_QUIT))
        self._flush_keypress()

    def _handle_key_down(self, e):
        """ Handle key-down event. """
        mods = sdl2.SDL_GetModState()
        try:
            scan = key_to_scan[e.key.keysym.sym]
        except KeyError:
            scan = None
        if e.key.keysym.sym == sdl2.SDLK_F11:
            self.f11_active = True
            self.clipboard.start(self.cursor_row, self.cursor_col)
        elif self.f11_active:
            self.clipboard.handle_key(scan, '')
        else:
            if plat.system == 'Windows':
                # Windows 7 and above send AltGr as Ctrl+RAlt
                # if 'altgr' option is off, Ctrl+RAlt is sent.
                # if 'altgr' is on, the RAlt key is being ignored
                # but a Ctrl keydown event has already been sent
                # so send keyup event to tell backend to release Ctrl modifier
                if e.key.keysym.sym == sdl2.SDLK_RALT:
                    backend.input_queue.put(backend.Event(backend.KEYB_UP,
                                                          scancode.CTRL))
            # keep scancode in buffer
            # to combine with text event
            # flush buffer on next key down, text event or end of loop
            if scan is not None:
                self._flush_keypress()
                self.last_down = scan, e.key.timestamp

    def _flush_keypress(self):
        """ Flush last keypress from buffer. """
        if self.last_down is not None:
            # insert into keyboard queue; no text event
            scan, _ = self.last_down
            backend.input_queue.put(backend.Event(backend.KEYB_DOWN, (scan, '')))
            self.last_down = None

    def _handle_key_up(self, e):
        """ Handle key-up event. """
        if e.key.keysym.sym == sdl2.SDLK_F11:
            self.clipboard.stop()
            self.f11_active = False
        # last key released gets remembered
        try:
            backend.input_queue.put(backend.Event(backend.KEYB_UP,
                                                  key_to_scan[e.key.keysym.sym]))
        except KeyError:
            pass

    def _handle_text_input(self, event):
        """ Handle text-input event. """
        c = event.text.text
        if self.f11_active:
            # F11+f to toggle fullscreen mode
            if c.upper() == 'F':
                self.fullscreen = not self.fullscreen
                self._do_create_window(*self._find_display_size(
                                self.size[0], self.size[1], self.border_width))
            self.clipboard.handle_key(None, c)
        # the text input event follows the key down event immediately
        elif self.last_down is None:
            # no key down event waiting: other input method
            backend.input_queue.put(backend.Event(
                    backend.KEYB_CHAR, c))
        else:
            scan, ts = self.last_down
            self.last_down = None
            if ts == event.text.timestamp:
                # combine if same time stamp
                backend.input_queue.put(backend.Event(
                        backend.KEYB_DOWN, (scan, c)))
            else:
                # two separate events
                backend.input_queue.put(backend.Event(
                        backend.KEYB_DOWN, (scan, '')))
                backend.input_queue.put(backend.Event(
                        backend.KEYB_CHAR, c))


    ###########################################################################
    # screen drawing cycle

    def _check_display(self):
        """ Check screen and blink events; update screen if necessary. """
        self.blink_state = 0
        if self.mode_has_blink:
            self.blink_state = 0 if self.cycle < self.blink_cycles * 2 else 1
            if self.cycle % self.blink_cycles == 0:
                self.screen_changed = True
        if self.cursor_visible and (
                (self.cursor_row != self.last_row) or
                (self.cursor_col != self.last_col)):
            self.screen_changed = True
        tock = sdl2.SDL_GetTicks()
        if (tock - self.last_cycle) >= (self.cycle_time/self.blink_cycles):
            self.last_cycle = tock
            self.cycle += 1
            if self.cycle == self.blink_cycles*4:
                self.cycle = 0
            if self.screen_changed:
                self._do_flip()
                self.screen_changed = False

    def _do_flip(self):
        """ Draw the canvas to the screen. """
        sdl2.SDL_FillRect(self.work_surface, None, self.border_attr)
        if self.composite_artifacts:
            self.work_pixels[:] = video_graphical.apply_composite_artifacts(
                            self.pixels[self.vpagenum], 4//self.bitsperpixel)
            sdl2.SDL_SetSurfacePalette(self.work_surface, self.composite_palette)
        else:
            self.work_pixels[:] = self.pixels[self.vpagenum]
            sdl2.SDL_SetSurfacePalette(self.work_surface, self.show_palette[self.blink_state])
        # apply cursor to work surface
        self._show_cursor(True)
        # convert 8-bit work surface to (usually) 32-bit display surface format
        pixelformat = self.display_surface.contents.format
        conv = sdl2.SDL_ConvertSurface(self.work_surface, pixelformat, 0)
        # scale converted surface and blit onto display
        if not self.smooth:
            sdl2.SDL_BlitScaled(conv, None, self.display_surface, None)
        else:
            # smooth-scale converted surface
            w, h = self.window_width, self.window_height
            zoomx = ctypes.c_double(w/(self.size[0] + 2.0*self.border_x))
            zoomy = ctypes.c_double(h/(self.size[1] + 2.0*self.border_y))
            zoomed = sdl2.sdlgfx.zoomSurface(conv, zoomx, zoomy, sdl2.sdlgfx.SMOOTHING_ON)
            # blit onto display
            sdl2.SDL_BlitSurface(zoomed, None, self.display_surface, None)
            sdl2.SDL_FreeSurface(zoomed)
        # create clipboard feedback
        if self.clipboard.active():
            rects = (sdl2.SDL_Rect(
                        r[0]+self.border_x, r[1]+self.border_y, r[2], r[3])
                        for r in self.clipboard.selection_rect)
            sdl_rects = (sdl2.SDL_Rect*len(self.clipboard.selection_rect))(*rects)
            sdl2.SDL_FillRect(self.overlay, None,
                sdl2.SDL_MapRGBA(self.overlay.contents.format, 0, 0, 0, 0))
            sdl2.SDL_FillRects(self.overlay, sdl_rects, len(sdl_rects),
                sdl2.SDL_MapRGBA(self.overlay.contents.format, 128, 0, 128, 0))
            sdl2.SDL_BlitScaled(self.overlay, None, self.display_surface, None)
        # flip the display
        sdl2.SDL_UpdateWindowSurface(self.display)

    def _show_cursor(self, do_show):
        """ Draw or remove the cursor on the visible page. """
        if not self.cursor_visible or self.vpagenum != self.apagenum:
            return
        screen = self.work_surface
        pixels = self.work_pixels
        top = (self.cursor_row-1) * self.font_height
        left = (self.cursor_col-1) * self.font_width
        if not do_show:
            pixels[left : left+self.font_width, top : top+self.font_height
                    ] = self.under_cursor
            return
        # copy area under cursor
        self.under_cursor = numpy.copy(
                pixels[left : left+self.font_width, top : top+self.font_height])
        if self.text_mode:
            # cursor is visible - to be done every cycle between 5 and 10, 15 and 20
            if self.cycle/self.blink_cycles in (1, 3):
                curs_height = min(self.cursor_to - self.cursor_from+1,
                                  self.font_height - self.cursor_from)
                curs_rect = sdl2.SDL_Rect(
                    self.border_x + left, self.border_y + top + self.cursor_from,
                    self.font_width, curs_height)
                sdl2.SDL_FillRect(screen, curs_rect, self.cursor_attr)
        else:
            pixels[ left : left+self.cursor_width,
                    top + self.cursor_from : top + self.cursor_to + 1
                ] ^= self.cursor_attr
        self.last_row = self.cursor_row
        self.last_col = self.cursor_col

    def _resize_display(self, width, height):
        """ Change the display size. """
        maximised = sdl2.SDL_GetWindowFlags(self.display) & sdl2.SDL_WINDOW_MAXIMIZED
        # workaround for maximised state not reporting correctly (at least on Ubuntu Unity)
        # detect if window is very large compared to screen; force maximise if so.
        to_maximised = (width >= 0.95*self.physical_size[0] and height >= 0.9*self.physical_size[1])
        if not maximised:
            if to_maximised:
                # force maximise for large windows
                sdl2.SDL_MaximizeWindow(self.display)
            else:
                # regular resize on non-maximised windows
                sdl2.SDL_SetWindowSize(self.display, width, height)
        else:
            # resizing throws us out of maximised mode
            if not to_maximised:
                sdl2.SDL_RestoreWindow(self.display)
        # get window size
        w, h = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetWindowSize(self.display, ctypes.byref(w), ctypes.byref(h))
        self.window_width, self.window_height = w.value, h.value
        self.display_surface = sdl2.SDL_GetWindowSurface(self.display)
        self.screen_changed = True


    ###########################################################################
    # signal handlers

    def set_mode(self, mode_info):
        """ Initialise a given text or graphics mode. """
        self.text_mode = mode_info.is_text_mode
        # unpack mode info struct
        self.font_height = mode_info.font_height
        self.font_width = mode_info.font_width
        # prebuilt glyphs
        # NOTE: [x][y] format - change this if we change pixels2d
        self.glyph_dict = {'\0': numpy.zeros((self.font_width, self.font_height))}
        self.num_pages = mode_info.num_pages
        self.mode_has_blink = mode_info.has_blink
        self.text = [[[' ']*mode_info.width
                        for _ in range(mode_info.height)]
                        for _ in range(self.num_pages)]
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
        # screen pages
        canvas_width, canvas_height = self.size
        self.canvas = [
            sdl2.SDL_CreateRGBSurface(0, canvas_width, canvas_height, 8, 0, 0, 0, 0)
            for _ in range(self.num_pages)]
        self.pixels = [
                pixels2d(canvas.contents)
                for canvas in self.canvas]
        # create work surface for border and composite
        self.border_x = int(canvas_width * self.border_width // 200)
        self.border_y = int(canvas_height * self.border_width // 200)
        work_width = canvas_width + 2*self.border_x
        work_height = canvas_height + 2*self.border_y
        self.work_surface = sdl2.SDL_CreateRGBSurface(
                                0, work_width, work_height, 8, 0, 0, 0, 0)
        self.work_pixels = pixels2d(self.work_surface.contents)[
                self.border_x : work_width-self.border_x,
                self.border_y : work_height-self.border_y]
        # create overlay for clipboard selection feedback
        # use convertsurface to create a copy of the display surface format
        pixelformat = self.display_surface.contents.format
        self.overlay = sdl2.SDL_ConvertSurface(self.work_surface, pixelformat, 0)
        sdl2.SDL_SetSurfaceBlendMode(self.overlay, sdl2.SDL_BLENDMODE_ADD)
        # initialise clipboard
        self.clipboard = video_graphical.ClipboardInterface(self,
                mode_info.width, mode_info.height, SDL2Clipboard())
        self.screen_changed = True

    def set_caption_message(self, msg):
        """ Add a message to the window caption. """
        title = self.caption + (' - ' + msg if msg else '')
        sdl2.SDL_SetWindowTitle(self.display, title)

    def set_palette(self, rgb_palette_0, rgb_palette_1):
        """ Build the palette. """
        self.num_fore_attrs = min(16, len(rgb_palette_0))
        self.num_back_attrs = min(8, self.num_fore_attrs)
        rgb_palette_1 = rgb_palette_1 or rgb_palette_0
        # fill up the 8-bit palette with all combinations we need
        # blink states: 0 light up, 1 light down
        # bottom 128 are non-blink, top 128 blink to background
        show_palette_0 = rgb_palette_0[:self.num_fore_attrs] * (256//self.num_fore_attrs)
        show_palette_1 = rgb_palette_1[:self.num_fore_attrs] * (128//self.num_fore_attrs)
        for b in rgb_palette_1[:self.num_back_attrs] * (128//self.num_fore_attrs//self.num_back_attrs):
            show_palette_1 += [b]*self.num_fore_attrs
        colors_0 = (sdl2.SDL_Color * 256)(*(sdl2.SDL_Color(r, g, b, 255) for (r, g, b) in show_palette_0))
        colors_1 = (sdl2.SDL_Color * 256)(*(sdl2.SDL_Color(r, g, b, 255) for (r, g, b) in show_palette_1))
        sdl2.SDL_SetPaletteColors(self.show_palette[0], colors_0, 0, 256)
        sdl2.SDL_SetPaletteColors(self.show_palette[1], colors_1, 0, 256)
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
        self.text[self.apagenum][start-1:stop] = [
            [' ']*len(self.text[self.apagenum][0]) for _ in range(start-1, stop)]
        scroll_area = sdl2.SDL_Rect(
                0, (start-1)*self.font_height,
                self.size[0], (stop-start+1)*self.font_height)
        sdl2.SDL_FillRect(self.canvas[self.apagenum], scroll_area, back_attr)
        self.screen_changed = True

    def set_page(self, vpage, apage):
        """ Set the visible and active page. """
        self.vpagenum, self.apagenum = vpage, apage
        self.screen_changed = True

    def copy_page(self, src, dst):
        """ Copy source to destination page. """
        self.text[dst] = [row[:] for row in self.text[src]]
        self.pixels[dst][:] = self.pixels[src][:]
        # alternative:
        # sdl2.SDL_BlitSurface(self.canvas[src], None, self.canvas[dst], None)
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

    def scroll_up(self, from_line, scroll_height, back_attr):
        """ Scroll the screen up between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                self.text[self.apagenum][from_line:scroll_height]
                + [[' ']*len(self.text[self.apagenum][0])])
        pixels = self.pixels[self.apagenum]
        # these are exclusive ranges [x0, x1) etc
        x0, x1 = 0, self.size[0]
        new_y0, new_y1 = (from_line-1)*self.font_height, (scroll_height-1)*self.font_height
        old_y0, old_y1 = from_line*self.font_height, scroll_height*self.font_height
        pixels[x0:x1, new_y0:new_y1] = pixels[x0:x1, old_y0:old_y1]
        pixels[x0:x1, new_y1:old_y1] = numpy.zeros((x1-x0, old_y1-new_y1))
        self.screen_changed = True

    def scroll_down(self, from_line, scroll_height, back_attr):
        """ Scroll the screen down between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                [[' ']*len(self.text[self.apagenum][0])] +
                self.text[self.apagenum][from_line-1:scroll_height-1])
        pixels = self.pixels[self.apagenum]
        # these are exclusive ranges [x0, x1) etc
        x0, x1 = 0, self.size[0]
        old_y0, old_y1 = (from_line-1)*self.font_height, (scroll_height-1)*self.font_height
        new_y0, new_y1 = from_line*self.font_height, scroll_height*self.font_height
        pixels[x0:x1, new_y0:new_y1] = pixels[x0:x1, old_y0:old_y1]
        pixels[x0:x1, old_y0:new_y0] = numpy.zeros((x1-x0, new_y0-old_y0))
        self.screen_changed = True

    def put_glyph(self, pagenum, row, col, c, fore, back, blink, underline, for_keys):
        """ Put a single-byte character at a given position. """
        self.text[pagenum][row-1][col-1] = unicodepage.cp_to_utf8[c]
        if len(c) > 1:
            self.text[pagenum][row-1][col] = ''
        if not self.text_mode:
            # in graphics mode, a put_rect call does the actual drawing
            return
        attr = fore + self.num_fore_attrs*back + 128*blink
        x0, y0 = (col-1)*self.font_width, (row-1)*self.font_height
        # NOTE: in pygame plugin we used a surface fill for the NUL character
        # which was an optimisation early on -- consider if we need speedup.
        try:
            glyph = self.glyph_dict[c]
        except KeyError:
            logging.warning('No glyph received for code point %s', repr(c))
            try:
                glyph = self.glyph_dict['\0']
            except KeyError:
                logging.error('No glyph received for code point 0')
                return
        # pixels2d uses column-major mode and hence [x][y] indexing (we can change this)
        # changle glyph color by numpy scalar mult (is there a better way?)
        self.pixels[pagenum][
            x0:x0+self.font_width, y0:y0+self.font_height] = (
                                                    glyph*(attr-back) + back)
        if underline:
            sdl2.SDL_FillRect(
                self.canvas[self.apagenum], sdl2.SDL_Rect(
                    x0, y0 + self.font_height - 1,
                    self.font_width, 1)
                , attr)
        self.screen_changed = True

    def build_glyphs(self, new_dict):
        """ Build a dict of glyphs for use in text mode. """
        for char, glyph in new_dict.iteritems():
            # transpose because pixels2d uses column-major mode and hence [x][y] indexing (we can change this)
            self.glyph_dict[char] = numpy.asarray(glyph).T

    def set_cursor_shape(self, width, height, from_line, to_line):
        """ Build a sprite for the cursor. """
        self.cursor_width = width
        self.cursor_from, self.cursor_to = from_line, to_line
        self.under_cursor = numpy.zeros((width, height))

    def put_pixel(self, pagenum, x, y, index):
        """ Put a pixel on the screen; callback to empty character buffer. """
        self.pixels[pagenum][x, y] = index
        self.screen_changed = True

    def fill_rect(self, pagenum, x0, y0, x1, y1, index):
        """ Fill a rectangle in a solid attribute. """
        rect = sdl2.SDL_Rect(x0, y0, x1-x0+1, y1-y0+1)
        sdl2.SDL_FillRect(self.canvas[pagenum], rect, index)
        self.screen_changed = True

    def fill_interval(self, pagenum, x0, x1, y, index):
        """ Fill a scanline interval in a solid attribute. """
        rect = sdl2.SDL_Rect(x0, y, x1-x0+1, 1)
        sdl2.SDL_FillRect(self.canvas[pagenum], rect, index)
        self.screen_changed = True

    def put_interval(self, pagenum, x, y, colours):
        """ Write a list of attributes to a scanline interval. """
        # reference the interval on the canvas
        self.pixels[pagenum][x:x+len(colours), y] = numpy.array(colours).astype(int)
        self.screen_changed = True

    def put_rect(self, pagenum, x0, y0, x1, y1, array):
        """ Apply numpy array [y][x] of attribytes to an area. """
        if (x1 < x0) or (y1 < y0):
            return
        # reference the destination area
        self.pixels[pagenum][x0:x1+1, y0:y1+1] = numpy.array(array).T
        self.screen_changed = True


###############################################################################
# clipboard handling


class SDL2Clipboard(clipboard.Clipboard):
    """ Clipboard handling interface using SDL2. """

    def __init__(self):
        """ Initialise the clipboard handler. """
        self.ok = (sdl2 is not None)

    def copy(self, text_utf8, mouse=False):
        """ Put text on clipboard. """
        sdl2.SDL_SetClipboardText(text_utf8)

    def paste(self, mouse=False):
        """ Return text from clipboard. """
        text = sdl2.SDL_GetClipboardText()
        if text is None:
            return ''
        return text


###############################################################################


def pixels2d(source):
    """ Creates a 2D pixel array from the passed 8-bit surface. """
    # limited, specialised version of pysdl2.ext.pixels2d by Marcus von Appen
    # original is CC0 public domain with zlib fallback licence
    # https://bitbucket.org/marcusva/py-sdl2
    psurface = source
    strides = (psurface.pitch, 1)
    srcsize = psurface.h * psurface.pitch
    shape = psurface.h, psurface.w
    pxbuf = ctypes.cast(psurface.pixels,
                        ctypes.POINTER(ctypes.c_ubyte * srcsize)).contents
    # NOTE: transpose() brings it on [x][y] form - we may prefer [y][x] instead
    return numpy.ndarray(shape, numpy.uint8, pxbuf, 0, strides, "C").transpose()


if sdl2:
    # these are PC keyboard scancodes
    key_to_scan = {
        # top row
        sdl2.SDLK_ESCAPE: scancode.ESCAPE, sdl2.SDLK_1: scancode.N1,
        sdl2.SDLK_2: scancode.N2, sdl2.SDLK_3: scancode.N3,
        sdl2.SDLK_4: scancode.N4, sdl2.SDLK_5: scancode.N5,
        sdl2.SDLK_6: scancode.N6, sdl2.SDLK_7: scancode.N7,
        sdl2.SDLK_8: scancode.N8, sdl2.SDLK_9: scancode.N9,
        sdl2.SDLK_0: scancode.N0, sdl2.SDLK_MINUS: scancode.MINUS,
        sdl2.SDLK_EQUALS: scancode.EQUALS,
        sdl2.SDLK_BACKSPACE: scancode.BACKSPACE,
        # row 1
        sdl2.SDLK_TAB: scancode.TAB, sdl2.SDLK_q: scancode.q,
        sdl2.SDLK_w: scancode.w, sdl2.SDLK_e: scancode.e, sdl2.SDLK_r: scancode.r,
        sdl2.SDLK_t: scancode.t, sdl2.SDLK_y: scancode.y, sdl2.SDLK_u: scancode.u,
        sdl2.SDLK_i: scancode.i, sdl2.SDLK_o: scancode.o, sdl2.SDLK_p: scancode.p,
        sdl2.SDLK_LEFTBRACKET: scancode.LEFTBRACKET,
        sdl2.SDLK_RIGHTBRACKET: scancode.RIGHTBRACKET,
        sdl2.SDLK_RETURN: scancode.RETURN, sdl2.SDLK_KP_ENTER: scancode.RETURN,
        # row 2
        sdl2.SDLK_RCTRL: scancode.CTRL, sdl2.SDLK_LCTRL: scancode.CTRL,
        sdl2.SDLK_a: scancode.a, sdl2.SDLK_s: scancode.s, sdl2.SDLK_d: scancode.d,
        sdl2.SDLK_f: scancode.f, sdl2.SDLK_g: scancode.g, sdl2.SDLK_h: scancode.h,
        sdl2.SDLK_j: scancode.j, sdl2.SDLK_k: scancode.k, sdl2.SDLK_l: scancode.l,
        sdl2.SDLK_SEMICOLON: scancode.SEMICOLON, sdl2.SDLK_QUOTE: scancode.QUOTE,
        sdl2.SDLK_BACKQUOTE: scancode.BACKQUOTE,
        # row 3
        sdl2.SDLK_LSHIFT: scancode.LSHIFT,
        sdl2.SDLK_BACKSLASH: scancode.BACKSLASH,
        sdl2.SDLK_z: scancode.z, sdl2.SDLK_x: scancode.x, sdl2.SDLK_c: scancode.c,
        sdl2.SDLK_v: scancode.v, sdl2.SDLK_b: scancode.b, sdl2.SDLK_n: scancode.n,
        sdl2.SDLK_m: scancode.m, sdl2.SDLK_COMMA: scancode.COMMA,
        sdl2.SDLK_PERIOD: scancode.PERIOD, sdl2.SDLK_SLASH: scancode.SLASH,
        sdl2.SDLK_RSHIFT: scancode.RSHIFT,
        sdl2.SDLK_PRINTSCREEN: scancode.PRINT,
        sdl2.SDLK_SYSREQ: scancode.SYSREQ,
        sdl2.SDLK_LALT: scancode.ALT,
        sdl2.SDLK_SPACE: scancode.SPACE, sdl2.SDLK_CAPSLOCK: scancode.CAPSLOCK,
        # function key row
        sdl2.SDLK_F1: scancode.F1, sdl2.SDLK_F2: scancode.F2,
        sdl2.SDLK_F3: scancode.F3, sdl2.SDLK_F4: scancode.F4,
        sdl2.SDLK_F5: scancode.F5, sdl2.SDLK_F6: scancode.F6,
        sdl2.SDLK_F7: scancode.F7, sdl2.SDLK_F8: scancode.F8,
        sdl2.SDLK_F9: scancode.F9, sdl2.SDLK_F10: scancode.F10,
        sdl2.SDLK_F11: scancode.F11, sdl2.SDLK_F12: scancode.F12,
        # top middle
        sdl2.SDLK_NUMLOCKCLEAR: scancode.NUMLOCK,
        sdl2.SDLK_SCROLLLOCK: scancode.SCROLLOCK,
        # keypad
        sdl2.SDLK_KP_7: scancode.KP7,
        sdl2.SDLK_HOME: scancode.HOME,
        sdl2.SDLK_KP_8: scancode.KP8,
        sdl2.SDLK_UP: scancode.UP,
        sdl2.SDLK_KP_9: scancode.KP9,
        sdl2.SDLK_PAGEUP: scancode.PAGEUP,
        sdl2.SDLK_KP_MINUS: scancode.KPMINUS,
        sdl2.SDLK_KP_4: scancode.KP4,
        sdl2.SDLK_LEFT: scancode.LEFT,
        sdl2.SDLK_KP_5: scancode.KP5,
        sdl2.SDLK_KP_6: scancode.KP6,
        sdl2.SDLK_RIGHT: scancode.RIGHT,
        sdl2.SDLK_KP_PLUS: scancode.KPPLUS,
        sdl2.SDLK_KP_1: scancode.KP1,
        sdl2.SDLK_END: scancode.END,
        sdl2.SDLK_KP_2: scancode.KP2,
        sdl2.SDLK_DOWN: scancode.DOWN,
        sdl2.SDLK_KP_3: scancode.KP3,
        sdl2.SDLK_PAGEDOWN: scancode.PAGEDOWN,
        sdl2.SDLK_KP_0: scancode.KP0,
        sdl2.SDLK_INSERT: scancode.INSERT,
        # keypad dot, times, div, enter ?
        # various
        sdl2.SDLK_DELETE: scancode.DELETE,
        sdl2.SDLK_PAUSE: scancode.BREAK,
    }

prepare()
