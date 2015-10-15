"""
PC-BASIC - video_sdl2.py
Graphical interface based on PySDL2

(c) 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import logging
import Queue

try:
    import sdl2
    import sdl2.ext
except ImportError:
    sdl2 = None
import ctypes



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

if plat.system == 'Windows':
    # Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
    # see https://bitbucket.org/pygame/pygame/issues/245/wrong-resolution-unless-you-use-ctypes
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        # old versions of Windows don't have this in user32.dll
        pass


###############################################################################

# screen size parameters
fullscreen = False
smooth = False
force_square_pixel = False
force_display_size = None
border_width = 0
# percentage of the screen to leave unused for window decorations etc.
display_slack = 15
# screen aspect ratio x, y
aspect = (4, 3)
# ignore ALT+F4 (and consequently window X button)
noquit = False
# window title
caption = ''
# mouse button functions
mousebutton_copy = 1
mousebutton_paste = 2
mousebutton_pen = 3


def prepare():
    """ Initialise video_sdl2 module. """
    global fullscreen, smooth, noquit, force_display_size
    global border_width
    global mousebutton_copy, mousebutton_paste, mousebutton_pen
    global aspect, force_square_pixel
    global caption
    global composite_monitor, composite_colors
    # display dimensions
    force_display_size = config.get('dimensions')
    aspect = config.get('aspect') or aspect
    border_width = config.get('border')
    force_square_pixel = (config.get('scaling') == 'native')
    fullscreen = config.get('fullscreen')
    smooth = (config.get('scaling') == 'smooth')
    # don't catch Alt+F4
    noquit = config.get('nokill')
    # mouse setups
    if sdl2:
        buttons = {'left': sdl2.SDL_BUTTON_LEFT, 'middle': sdl2.SDL_BUTTON_MIDDLE,
                   'right': sdl2.SDL_BUTTON_RIGHT, 'none': None}
        mousebutton_copy = buttons[config.get('copy-paste')[0]]
        mousebutton_paste = buttons[config.get('copy-paste')[1]]
        mousebutton_pen = buttons[config.get('pen')]
    # window caption/title
    caption = config.get('caption')
    # if no composite palette available for this card, ignore.
    composite_monitor = (config.get('monitor') == 'composite' and
                         config.get('video') in composite_640)
    try:
        composite_colors = composite_640[config.get('video')]
    except KeyError:
        composite_colors = composite_640['cga']
    video.plugin_dict['sdl2'] = VideoSDL2

###############################################################################

class VideoSDL2(video.VideoPlugin):
    """ SDL2-based graphical interface. """

    def __init__(self):
        """ Initialise SDL2 interface. """
        global smooth
        if not sdl2:
            logging.debug('PySDL2 module not found.')
            raise video.InitFailed()
        if not numpy:
            logging.debug('NumPy module not found.')
            raise video.InitFailed()
        sdl2.ext.init()
        # display & border
        # border attribute
        self.border_attr = 0
        # border widh in pixels
        self.border_width = border_width
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
        self.fullscreen = fullscreen
        # load the icon
        self.set_icon(backend.icon)
        # create the window initially, size will be corrected later
        self._do_create_window(640, 400)
        # load an all-black 16-colour game palette to get started
        self.set_palette([(0,0,0)]*16, None)
        self.move_cursor(1, 1)
        self.set_page(0, 0)
        self.set_mode(backend.initial_mode)
        # support for CGA composite
        self.composite_palette = sdl2.SDL_AllocPalette(256)
        colors = (sdl2.SDL_Color * 256)(*[sdl2.SDL_Color(r, g, b, 255) for (r, g, b) in composite_colors])
        sdl2.SDL_SetPaletteColors(self.composite_palette, colors, 0, 256)

        # joystick and mouse
        # available joysticks
        num_joysticks = sdl2.SDL_NumJoysticks()
        for j in range(num_joysticks):
            sdl2.SDL_JoystickOpen(j)
            # if a joystick is present, its axes report 128 for mid, not 0
            for axis in (0, 1):
                backend.input_queue.put(backend.Event(backend.STICK_MOVED,
                                                      (j, axis, 128)))

        ###
        # if smooth and self.display.get_bitsize() < 24:
        #     logging.warning("Smooth scaling not available on this display (depth %d < 24)", self.display.get_bitsize())
        #     smooth = False
        ###

        self.f11_active = False
        video.VideoPlugin.__init__(self)


    def close(self):
        """ Close the SDL2 interface. """
        video.VideoPlugin.close(self)
        if sdl2 and numpy:
            #TODO: free surfaces
            # free palettes
            for p in self.show_palette:
                sdl2.SDL_FreePalette(p)
            sdl2.SDL_FreePalette(self.composite_palette)
            # close SDL2
            sdl2.ext.quit()
            # if using SDL_Init():
            #sdl2.SDL_Quit()

    def set_icon(self, mask):
        """ Set the window icon. """
        self.icon = mask

    def _do_set_icon(self):
        """ Actually set the icon on the SDL window. """
        mask = numpy.array(self.icon).T.repeat(2, 0).repeat(2, 1)
        icon = sdl2.SDL_CreateRGBSurface(0, mask.shape[0], mask.shape[1], 8, 0, 0, 0, 0)
        sdl2.ext.pixels2d(icon.contents)[:] = mask
        # icon palette (black & white)
        icon_palette = sdl2.SDL_AllocPalette(256)
        icon_colors = [ sdl2.SDL_Color(x, x, x, 255) for x in [0, 255] + [255]*254 ]
        sdl2.SDL_SetPaletteColors(icon_palette, (sdl2.SDL_Color * 256)(*icon_colors), 0, 2)
        sdl2.SDL_SetSurfacePalette(icon, icon_palette)
        sdl2.SDL_SetWindowIcon(self.display.window, icon)
        sdl2.SDL_FreeSurface(icon)
        sdl2.SDL_FreePalette(icon_palette)

    def _do_create_window(self, width, height):
        """ Create a new SDL window """
        flags = sdl2.SDL_WINDOW_RESIZABLE | sdl2.SDL_WINDOW_SHOWN
        if self.fullscreen:
             flags |= sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_BORDERLESS
        self.display = sdl2.ext.Window(caption, size=(width, height), flags=flags)
        self._do_set_icon()
        self.display_surface = self.display.get_surface()
        self.screen_changed = True


    ###########################################################################
    # input cycle


    def _check_input(self):
        """ Handle screen and interface events. """
        # check and handle input events
        for event in sdl2.ext.get_events():
            if event.type == sdl2.SDL_KEYDOWN:
                self._handle_key_down(event)
            elif event.type == sdl2.SDL_KEYUP:
                self._handle_key_up(event)

            # elif event.type == sdl2.SDL_TEXTINPUT:
            #     #this is where input methods would come in
            #     #FIXME: do we get both a textinput and a keydown event? how shall we deal?
            #     backend.input_queue.put(backend.Event(backend.KEYB_CHAR, event.text.text))

            elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                pos = self._normalise_pos(event.button.x, event.button.y)
                # copy, paste and pen may be on the same button, so no elifs
                if event.button.button == mousebutton_copy:
                    # LEFT button: copy
                    self.clipboard.start(1 + pos[1] // self.font_height,
                            1 + (pos[0]+self.font_width//2) // self.font_width)
                if event.button.button == mousebutton_paste:
                    # MIDDLE button: paste
                    self.clipboard.paste(mouse=True)
                if event.button.button == mousebutton_pen:
                    # right mouse button is a pen press
                    backend.input_queue.put(backend.Event(backend.PEN_DOWN, pos))
            elif event.type == sdl2.SDL_MOUSEBUTTONUP:
                backend.input_queue.put(backend.Event(backend.PEN_UP))
                if event.button.button == mousebutton_copy:
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
                if noquit:
                    self.set_caption_message('to exit type <CTRL+BREAK> <ESC> SYSTEM')
                else:
                    backend.input_queue.put(backend.Event(backend.KEYB_QUIT))

    def _handle_key_down(self, e):
        """ Handle key-down event. """
        c = ''
        mods = sdl2.SDL_GetModState()
        if e.key.keysym.sym == sdl2.SDLK_F11:
            self.f11_active = True
            self.clipboard.start(self.cursor_row, self.cursor_col)
        elif self.f11_active:
            # F11+f to toggle fullscreen mode
            if e.key.keysym.sym == sdl2.SDLK_f:
                self.fullscreen = not self.fullscreen
                self._do_create_window(*self._find_display_size(
                                self.size[0], self.size[1], self.border_width))
            self.clipboard.handle_key(e)
        else:
            ###
            # utf8 = e.unicode.encode('utf-8')
            # try:
            #     c = unicodepage.from_utf8(utf8)
            # except KeyError:
            #     # no codepage encoding found, ignore
            #     # this happens for control codes like '\r' since
            #     # unicodepage defines the special graphic characters for those
            #     # let control codes be handled by scancode
            #     # as e.unicode isn't always the correct thing for ascii controls
            #     # e.g. ctrl+enter should be '\n' but has e.unicode=='\r'
            #     pass
            # double NUL characters, as single NUL signals scan code
            # if len(c) == 1 and ord(c) == 0:
            #     c = '\0\0'
            # current key pressed; modifiers handled by backend interface
            ###

            try:
                scan = key_to_scan[e.key.keysym.sym]
            except KeyError:
                scan = None
            if plat.system == 'Windows':
                # Windows 7 and above send AltGr as Ctrl+RAlt
                # if 'altgr' option is off, Ctrl+RAlt is sent.
                # if 'altgr' is on, the RAlt key is being ignored
                # but a Ctrl keydown event has already been sent
                # so send keyup event to tell backend to release Ctrl modifier
                if e.key.keysym.sym == sdl2.SDLK_RALT:
                    backend.input_queue.put(backend.Event(backend.KEYB_UP,
                                                          scancode.CTRL))
            # insert into keyboard queue
            backend.input_queue.put(backend.Event(backend.KEYB_DOWN, (scan, c)))

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
        screen = self.canvas[self.vpagenum]
        pixels = self.pixels[self.vpagenum]

        # if self.composite_artifacts:
        #     pixels[:] = apply_composite_artifacts(pixels, 4//self.bitsperpixel)
        #     sdl2.SDL_SetSurfacePalette(screen, self.composite_palette)
        # else:

        sdl2.SDL_SetSurfacePalette(screen, self.show_palette[self.blink_state])
        self._show_cursor(True)

        ###
        #if smooth:
        #    pygame.transform.smoothscale(screen.convert(self.display),
        #                                 self.display.get_size(), self.display)
        #else:
        #    pygame.transform.scale(screen.convert(self.display),
        #                           self.display.get_size(), self.display)
        ###
        conv = sdl2.SDL_ConvertSurface(screen, self.display_surface.format, 0)


        # TODO: do this on resizing and store values
        # get window size
        w, h = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetWindowSize(self.display.window, ctypes.byref(w), ctypes.byref(h))
        w, h = w.value, h.value
        # get scaled canvas size
        border_factor = (1 + self.border_width/100.)
        dst_w = int(w / border_factor)
        dst_h = int(h / border_factor)
        dst_rect = sdl2.SDL_Rect((w - dst_w) // 2, (h-dst_h) // 2, dst_w, dst_h)

        # fill display with border colour
        # get RGB out of surface palette
        r, g, b = ctypes.c_ubyte(), ctypes.c_ubyte(), ctypes.c_ubyte()
        sdl2.SDL_GetRGB(self.border_attr, screen.contents.format, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b))
        sdl2.SDL_FillRect(self.display_surface, None, sdl2.SDL_MapRGB(self.display_surface.format, r, g, b))

        # blit canvas onto display
        sdl2.SDL_BlitScaled(conv, None, self.display_surface, dst_rect)

        # create clipboard feedback
        if self.clipboard.active():
            rects = [sdl2.SDL_Rect(*r) for r in self.clipboard.selection_rect]
            #sdl2.SDL_FillRects(self.overlay, (sdl2.SDL_rect*len(rects))(rects), len(rects), 1)
            sdl2.SDL_FillRect(self.overlay, None, sdl2.SDL_MapRGBA(
                                        self.overlay.contents.format, 0, 0, 0, 0))
            for r in rects:
                sdl2.SDL_FillRect(self.overlay, r, sdl2.SDL_MapRGBA(
                                        self.overlay.contents.format, 128, 0, 128, 0))
            sdl2.SDL_BlitScaled(self.overlay, None, self.display_surface, dst_rect)

        self.display.refresh() #sdl2.SDL_UpdateWindowSurface(self.display.window)
        self._show_cursor(False)

    def _show_cursor(self, do_show):
        """ Draw or remove the cursor on the visible page. """
        if not self.cursor_visible or self.vpagenum != self.apagenum:
            return
        screen = self.canvas[self.vpagenum]
        pixels = self.pixels[self.vpagenum]
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
                    left, top + self.cursor_from,
                    self.font_width, curs_height)
                sdl2.SDL_FillRect(screen, curs_rect, self.cursor_attr)
        else:
            pixels[ left : left+self.cursor_width,
                    top + self.cursor_from : top + self.cursor_to + 1
                ] ^= self.cursor_attr
        self.last_row = self.cursor_row
        self.last_col = self.cursor_col



    ###########################################################################
    # miscellaneous helper functions

    #MOVE outside of class
    def _find_display_size(self, canvas_x, canvas_y, border_width):
        """ Determine the optimal size for the display. """
        # comply with requested size unless we're fullscreening
        if force_display_size and not self.fullscreen:
            return force_display_size
        if not force_square_pixel:
            # this assumes actual display aspect ratio is wider than 4:3
            # scale y to fit screen
            canvas_y = (1 - display_slack/100.) * (
                        self.physical_size[1] // int(1 + border_width/100.))
            # scale x to match aspect ratio
            canvas_x = (canvas_y * aspect[0]) / aspect[1]
            # add back border
            pixel_x = int(canvas_x * (1 + border_width/100.))
            pixel_y = int(canvas_y * (1 + border_width/100.))
            return pixel_x, pixel_y
        else:
            pixel_x = int(canvas_x * (1 + border_width/100.))
            pixel_y = int(canvas_y * (1 + border_width/100.))
            # leave part of the screen either direction unused
            # to account for task bars, window decorations, etc.
            xmult = max(1, int((100.-display_slack) *
                                        self.physical_size[0] / (100.*pixel_x)))
            ymult = max(1, int((100.-display_slack) *
                                        self.physical_size[1] / (100.*pixel_y)))
            # find the multipliers mx <= xmult, my <= ymult
            # such that mx * pixel_x / my * pixel_y
            # is multiplicatively closest to aspect[0] / aspect[1]
            target = aspect[0]/(1.0*aspect[1])
            current = xmult*canvas_x / (1.0*ymult*canvas_y)
            # find the absolute multiplicative distance (always > 1)
            best = max(current, target) / min(current, target)
            apx = xmult, ymult
            for mx in range(1, xmult+1):
                my = min(ymult,
                         int(round(mx*canvas_x*aspect[1] / (1.0*canvas_y*aspect[0]))))
                current = mx*pixel_x / (1.0*my*pixel_y)
                dist = max(current, target) / min(current, target)
                # prefer larger multipliers if distance is equal
                if dist <= best:
                    best = dist
                    apx = mx, my
            return apx[0] * pixel_x, apx[1] * pixel_y

    def _resize_display(self, width, height):
        """ Change the display size. """
        maximised = sdl2.SDL_GetWindowFlags(self.display.window) & sdl2.SDL_WINDOW_MAXIMIZED
        # workaround for maximised state not reporting correctly (at least on Ubuntu Unity)
        # detect if window is very large compared to screen; force maximise if so.
        to_maximised = (width >= 0.95*self.physical_size[0] and height >= 0.9*self.physical_size[1])
        if not maximised:
            if to_maximised:
                # force maximise for large windows
                sdl2.SDL_MaximizeWindow(self.display.window)
            else:
                # regular resize on non-maximised windows
                sdl2.SDL_SetWindowSize(self.display.window, width, height)
        else:
            # resizing throws us out of maximised mode
            if not to_maximised:
                sdl2.SDL_RestoreWindow(self.display.window)
        self.display_surface = self.display.get_surface()
        self.screen_changed = True

    def _normalise_pos(self, x, y):
        """ Convert physical to logical coordinates within screen bounds. """
        border_x = int(self.size[0] * self.border_width / 200.)
        border_y = int(self.size[1] * self.border_width / 200.)
        xscale = self.physical_size[0] / (1.*(self.size[0]+2*border_x))
        yscale = self.physical_size[1] / (1.*(self.size[1]+2*border_y))
        xpos = min(self.size[0]-1, max(0, int(x//xscale - border_x)))
        ypos = min(self.size[1]-1, max(0, int(y//yscale - border_y)))
        return xpos, ypos


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
                sdl2.ext.pixels2d(canvas.contents)
                for canvas in self.canvas]
        # create overlay for clipboard selection feedback
        # use convertsurface to create a copy of the display surface format
        self.overlay = sdl2.SDL_ConvertSurface(
                        self.canvas[0], self.display_surface.format, 0)
        sdl2.SDL_SetSurfaceBlendMode(self.overlay, sdl2.SDL_BLENDMODE_ADD)
        # initialise clipboard
        self.clipboard = ClipboardInterface(self, mode_info.width, mode_info.height)
        self.screen_changed = True

    def set_caption_message(self, msg):
        """ Add a message to the window caption. """
        if msg:
            self.display.title = caption + ' - ' + msg
        else:
            self.display.title = caption

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
        self.composite_artifacts = on and self.mode_has_artifacts and composite_monitor

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



#MOVE to sdl2/pygame agnostic place
class ClipboardInterface(object):
    """ Clipboard user interface. """

    def __init__(self, videoplugin, width, height):
        """ Initialise clipboard feedback handler. """
        self._active = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        self.width = width
        self.height = height
        self.font_width = videoplugin.font_width
        self.font_height = videoplugin.font_height
        self.size = videoplugin.size
        self.videoplugin = videoplugin
        #SDL2
        self.clipboard_handler = SDL2Clipboard()

    def active(self):
        """ True if clipboard mode is active. """
        return self._active

    def start(self, r, c):
        """ Enter clipboard mode (clipboard key pressed). """
        self._active = True
        self.select_start = [r, c]
        self.select_stop = [r, c]
        self.selection_rect = []

    def stop(self):
        """ Leave clipboard mode (clipboard key released). """
        self._active = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        self.videoplugin.screen_changed = True

    def copy(self, mouse=False):
        """ Copy screen characters from selection into clipboard. """
        start, stop = self.select_start, self.select_stop
        if not start or not stop:
            return
        if start[0] == stop[0] and start[1] == stop[1]:
            return
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        text_rows = self.videoplugin.text[self.videoplugin.vpagenum][start[0]-1:stop[0]]
        text_rows[0] = text_rows[0][start[1]-1:]
        if stop[1] < self.width:
            text_rows[-1] = text_rows[-1][:stop[1]-self.width-1]
        text = '\n'.join(''.join(row) for row in text_rows)
        self.clipboard_handler.copy(text, mouse)

    def paste(self, mouse=False):
        """ Paste from clipboard into keyboard buffer. """
        text = self.clipboard_handler.paste(mouse)
        backend.input_queue.put(backend.Event(backend.CLIP_PASTE, text))

    def move(self, r, c):
        """ Move the head of the selection and update feedback. """
        self.select_stop = [r, c]
        start, stop = self.select_start, self.select_stop
        if stop[1] < 1:
            stop[0] -= 1
            stop[1] = self.width+1
        if stop[1] > self.width+1:
            stop[0] += 1
            stop[1] = 1
        if stop[0] > self.height:
            stop[:] = [self.height, self.width+1]
        if stop[0] < 1:
            stop[:] = [1, 1]
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        rect_left = (start[1] - 1) * self.font_width
        rect_top = (start[0] - 1) * self.font_height
        rect_right = (stop[1] - 1) * self.font_width
        rect_bot = stop[0] * self.font_height
        if start[0] == stop[0]:
            # single row selection
            self.selection_rect = [(rect_left, rect_top,
                                    rect_right-rect_left, rect_bot-rect_top)]
        else:
            # multi-row selection
            self.selection_rect = [
                (rect_left, rect_top,
                      self.size[0]-rect_left, self.font_height),
                (0, rect_top + self.font_height,
                      self.size[0], rect_bot - rect_top - 2*self.font_height),
                (0, rect_bot - self.font_height,
                      rect_right, self.font_height)]
        self.videoplugin.screen_changed = True

    def handle_key(self, e):
        """ Handle keyboard clipboard commands. """
        if not self._active:
            return
        if e.key.keysym.sym == sdl2.SDLK_c:
            self.copy()
        elif e.key.keysym.sym == sdl2.SDLK_v:
            self.paste()
        elif e.key.keysym.sym == sdl2.SDLK_a:
            # select all
            self.select_start = [1, 1]
            self.move(self.height, self.width+1)
        elif e.key.keysym.sym == sdl2.SDLK_LEFT:
            # move selection head left
            self.move(self.select_stop[0], self.select_stop[1]-1)
        elif e.key.keysym.sym == sdl2.SDLK_RIGHT:
            # move selection head right
            self.move(self.select_stop[0], self.select_stop[1]+1)
        elif e.key.keysym.sym == sdl2.SDLK_UP:
            # move selection head up
            self.move(self.select_stop[0]-1, self.select_stop[1])
        elif e.key.keysym.sym == sdl2.SDLK_DOWN:
            # move selection head down
            self.move(self.select_stop[0]+1, self.select_stop[1])



###############################################################################


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
#        sdl2.SDLK_PRINT: scancode.PRINT,
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
#        sdl2.SDLK_NUMLOCK: scancode.NUMLOCK,
#        sdl2.SDLK_SCROLLOCK: scancode.SCROLLOCK,
        # keypad
#        sdl2.SDLK_KP7: scancode.KP7,
        sdl2.SDLK_HOME: scancode.HOME,
#        sdl2.SDLK_KP8: scancode.KP8,
        sdl2.SDLK_UP: scancode.UP,
#        sdl2.SDLK_KP9: scancode.KP9,
        sdl2.SDLK_PAGEUP: scancode.PAGEUP,
        sdl2.SDLK_KP_MINUS: scancode.KPMINUS,
#        sdl2.SDLK_KP4: scancode.KP4,
        sdl2.SDLK_LEFT: scancode.LEFT,
#        sdl2.SDLK_KP5: scancode.KP5,
#        sdl2.SDLK_KP6: scancode.KP6,
        sdl2.SDLK_RIGHT: scancode.RIGHT,
        sdl2.SDLK_KP_PLUS: scancode.KPPLUS,
#        sdl2.SDLK_KP1: scancode.KP1,
        sdl2.SDLK_END: scancode.END,
#        sdl2.SDLK_KP2: scancode.KP2,
        sdl2.SDLK_DOWN: scancode.DOWN,
#        sdl2.SDLK_KP3: scancode.KP3,
        sdl2.SDLK_PAGEDOWN: scancode.PAGEDOWN,
#        sdl2.SDLK_KP0: scancode.KP0,
        sdl2.SDLK_INSERT: scancode.INSERT,
        # keypad dot, times, div, enter ?
        # various
        sdl2.SDLK_DELETE: scancode.DELETE,
        sdl2.SDLK_PAUSE: scancode.BREAK,
#        sdl2.SDLK_BREAK: scancode.BREAK,
    }

# composite palettes, see http://nerdlypleasures.blogspot.co.uk/2013_11_01_archive.html
composite_640 = {
    'cga_old': [
        (0x00, 0x00, 0x00),        (0x00, 0x71, 0x00),        (0x00, 0x3f, 0xff),        (0x00, 0xab, 0xff),
        (0xc3, 0x00, 0x67),        (0x73, 0x73, 0x73),        (0xe6, 0x39, 0xff),        (0x8c, 0xa8, 0xff),
        (0x53, 0x44, 0x00),        (0x00, 0xcd, 0x00),        (0x73, 0x73, 0x73),        (0x00, 0xfc, 0x7e),
        (0xff, 0x39, 0x00),        (0xe2, 0xca, 0x00),        (0xff, 0x7c, 0xf4),        (0xff, 0xff, 0xff)    ],
    'cga': [
        (0x00, 0x00, 0x00),        (0x00, 0x6a, 0x2c),        (0x00, 0x39, 0xff),        (0x00, 0x94, 0xff),
        (0xca, 0x00, 0x2c),        (0x77, 0x77, 0x77),        (0xff, 0x31, 0xff),        (0xc0, 0x98, 0xff),
        (0x1a, 0x57, 0x00),        (0x00, 0xd6, 0x00),        (0x77, 0x77, 0x77),        (0x00, 0xf4, 0xb8),
        (0xff, 0x57, 0x00),        (0xb0, 0xdd, 0x00),        (0xff, 0x7c, 0xb8),        (0xff, 0xff, 0xff)    ],
    'tandy': [
        (0x00, 0x00, 0x00),        (0x7c, 0x30, 0x00),        (0x00, 0x75, 0x00),        (0x00, 0xbe, 0x00),
        (0x00, 0x47, 0xee),        (0x77, 0x77, 0x77),        (0x00, 0xbb, 0xc4),        (0x00, 0xfb, 0x3f),
        (0xb2, 0x0f, 0x9d),        (0xff, 0x1e, 0x0f),        (0x77, 0x77, 0x77),        (0xff, 0xb8, 0x00),
        (0xb2, 0x44, 0xff),        (0xff, 0x78, 0xff),        (0x4b, 0xba, 0xff),        (0xff, 0xff, 0xff)    ],
    'pcjr': [
        (0x00, 0x00, 0x00),
        (0x98, 0x20, 0xcb),        (0x9f, 0x1c, 0x00),        (0xff, 0x11, 0x71),        (0x00, 0x76, 0x00),
        (0x77, 0x77, 0x77),        (0x5b, 0xaa, 0x00),        (0xff, 0xa5, 0x00),        (0x00, 0x4e, 0xcb),
        (0x74, 0x53, 0xff),        (0x77, 0x77, 0x77),        (0xff, 0x79, 0xff),        (0x00, 0xc8, 0x71),
        (0x00, 0xcc, 0xff),        (0x00, 0xfa, 0x00),        (0xff, 0xff, 0xff) ]        }

#MOVE to sdl2/pygame agnostic place
def apply_composite_artifacts(src_array, pixels=4):
    """ Process the canvas to apply composite colour artifacts. """
    width, height = src_array.shape
    s = [None]*pixels
    for p in range(pixels):
        s[p] = src_array[p:width:pixels]&(4//pixels)
    for p in range(1,pixels):
        s[0] = s[0]*2 + s[p]
    return numpy.repeat(s[0], pixels, axis=0)

prepare()
