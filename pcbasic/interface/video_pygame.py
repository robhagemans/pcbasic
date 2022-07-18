"""
PC-BASIC - video_pygame.py
Graphical interface based on PyGame

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import ctypes

if False:
    # for detection by packagers
    import pygame

from ..compat import iteritems, unichr
from ..basic.base import signals
from ..basic.base import scancode
from ..basic.base import bytematrix
from ..basic.base.eascii import as_unicode as uea
from ..compat import WIN32, MACOS, PY2
from ..compat import set_dpi_aware
from .video import VideoPlugin
from .base import video_plugins, InitFailed, EnvironmentCache, NOKILL_MESSAGE
from . import clipboard
from . import window


# refresh cycle parameters
# number of cycles to change blink state
BLINK_CYCLES = 5
# ms duration of a blink
BLINK_TIME = 120
CYCLE_TIME = BLINK_TIME // BLINK_CYCLES

# blank icon
BLANK_ICON = ((0,) * 16) * 16


@video_plugins.register('pygame')
class VideoPygame(VideoPlugin):
    """Pygame-based graphical interface."""

    def __init__(
            self, input_queue, video_queue,
            caption=u'', icon=BLANK_ICON,
            scaling=None, dimensions=None, aspect_ratio=(4, 3), border_width=0, fullscreen=False,
            prevent_close=False, mouse_clipboard=True,
            **kwargs
        ):
        """Initialise pygame interface."""
        logging.warning('The `pygame` interface is deprecated, please use the `graphics` interface instead.')
        try:
            _import_pygame()
        except ImportError:
            raise InitFailed('Module `pygame` not found')
        VideoPlugin.__init__(self, input_queue, video_queue)
        # request smooth scaling
        self._smooth = scaling == 'smooth'
        # ignore ALT+F4 and window X button
        self._nokill = prevent_close
        # window caption/title
        self.caption = caption
        # start in fullscreen mode
        self.fullscreen = fullscreen
        self._has_window = False
        # set state objects to whatever is now in state (may have been unpickled)
        # Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
        set_dpi_aware()
        # ensure we have the correct video driver for SDL 1.2
        # pygame sets this on import, but if we've tried SDL2 we've had to
        # reset this value
        # ensure window is centred
        self._env = EnvironmentCache()
        self._env.set('SDL_VIDEO_CENTERED', '1')
        pygame.init()
        try:
            # poll the driver to force an exception if not initialised
            pygame.display.get_driver()
        except pygame.error as e:
            self._close_pygame()
            raise InitFailed('No suitable display driver: %s' % e)
        # display & border
        # display buffer
        self.canvas = None
        # border attribute
        self.border_attr = 0
        # palette and colours
        # working palette - attribute index in blue channel
        self.work_palette = [(0, 0, index) for index in range(256)]
        # display palettes for blink states 0, 1
        self._palette = [None, None]
        # composite colour artifacts
        self._pixel_packing = False
        # text attributes supported
        self._palette_blinks = True
        # update cycle
        # update flag
        self.busy = False
        # refresh cycle parameters
        self._cycle = 0
        self.last_cycle = 0
        # cursor
        # cursor shape
        self.cursor = None
        # current cursor location
        self.last_row = 1
        self.last_col = 1
        # cursor is visible
        self.cursor_visible = True
        self.cursor_attr = 7
        # buffer for text under cursor
        self.under_top_left = None
        # fonts
        # joystick and mouse
        # available joysticks
        self.joysticks = []
        # get physical screen dimensions (needs to be called before set_mode)
        display_info = pygame.display.Info()
        self._window_sizer = window.WindowSizer(
            display_info.current_w, display_info.current_h,
            scaling, dimensions, aspect_ratio, border_width,
        )
        # determine initial display size
        self._window_sizer.set_canvas_size(720, 400)
        self._set_icon(icon)
        try:
            self._resize_display()
        except pygame.error as e:
            self._close_pygame()
            raise InitFailed('Could not initialise display: %s' % e)
        if self._smooth and self.display.get_bitsize() < 24:
            logging.warning(
                'Smooth scaling not available on this display (depth %d < 24)',
                self.display.get_bitsize()
            )
            self._smooth = False
        if PY2: # pragma: no cover
            pygame.display.set_caption(self.caption.encode('utf-8', 'replace'))
        else:
            pygame.display.set_caption(self.caption)
        pygame.key.set_repeat(500, 24)
        # load an all-black 16-colour game palette to get started
        self.set_palette([((0,0,0), (0,0,0), False, False)]*16, None)
        pygame.joystick.init()
        self.joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]
        for j in self.joysticks:
            j.init()
        # if a joystick is present, its axes report 128 for mid, not 0
        for joy in range(len(self.joysticks)):
            for axis in (0, 1):
                self._input_queue.put(signals.Event(signals.STICK_MOVED, (joy, axis, 128)))
        # mouse setups
        self._mouse_clip = mouse_clipboard
        self.cursor_row, self.cursor_col = 1, 1
        # set_mode should be first event on queue
        self.f11_active = False
        self.clipboard_handler = get_clipboard_handler()
        # buffer for perceived alt key status, for use by workarounds
        self._alt_key_down = None

    def __exit__(self, type, value, traceback):
        """Close the pygame interface."""
        VideoPlugin.__exit__(self, type, value, traceback)
        self._close_pygame()

    def _close_pygame(self):
        """Close pygame modules and displays."""
        # if pygame import failed, close() is called while pygame is None
        if pygame:
            pygame.joystick.quit()
            pygame.display.quit()
            pygame.quit()
        # put environment variables back as they were
        self._env.close()

    def _set_icon(self, mask):
        """Set the window icon."""
        height, width = len(mask), len(mask[0])
        icon = pygame.Surface((width, height), depth=8) # pylint: disable=E1121,E1123
        icon.fill(0)
        array = bytematrix.ByteMatrix(height, width, mask)
        #icon.blit(glyph_to_surface(mask), (0, 0, width, height))
        pygame.surfarray.blit_array(icon, _BufferWrapper(array))
        icon.set_palette_at(0, (0, 0, 0))
        icon.set_palette_at(1, (0xff, 0xff, 0xff))
        pygame.transform.scale2x(icon)
        pygame.transform.scale2x(icon)
        pygame.display.set_icon(icon)


    ###########################################################################
    # input cycle

    def _check_input(self):
        """Handle screen and interface events."""
        # check and handle pygame events
        if not self._has_window:
            return
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                self._handle_key_down(event)
            elif event.type == pygame.KEYUP:
                self._handle_key_up(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self._mouse_clip:
                    if event.button == 1:
                        # LEFT button: copy
                        pos = self._window_sizer.normalise_pos(*event.pos)
                        self.clipboard.start(
                            1 + pos[1] // self.font_height,
                            1 + (pos[0]+self.font_width//2) // self.font_width
                        )
                    elif event.button == 2:
                        # MIDDLE button: paste
                        text = self.clipboard_handler.paste()
                        self.clipboard.paste(text)
                    self.busy = True
                if event.button == 1:
                    # right mouse button is a pen press
                    self._input_queue.put(signals.Event(
                        signals.PEN_DOWN, self._window_sizer.normalise_pos(*event.pos)
                    ))
            elif event.type == pygame.MOUSEBUTTONUP:
                self._input_queue.put(signals.Event(signals.PEN_UP))
                if self._mouse_clip and event.button == 1:
                    self.clipboard.copy()
                    self.clipboard.stop()
                    self.busy = True
            elif event.type == pygame.MOUSEMOTION:
                pos = self._window_sizer.normalise_pos(*event.pos)
                self._input_queue.put(signals.Event(signals.PEN_MOVED, pos))
                if self.clipboard.active():
                    self.clipboard.move(
                        1 + pos[1] // self.font_height,
                        1 + (pos[0]+self.font_width//2) // self.font_width
                    )
                    self.busy = True
            elif event.type == pygame.JOYBUTTONDOWN:
                self._input_queue.put(signals.Event(
                    signals.STICK_DOWN, (event.joy, event.button)
                ))
            elif event.type == pygame.JOYBUTTONUP:
                self._input_queue.put(signals.Event(
                    signals.STICK_UP, (event.joy, event.button)
                ))
            elif event.type == pygame.JOYAXISMOTION:
                self._input_queue.put(signals.Event(
                    signals.STICK_MOVED, (event.joy, event.axis, int(event.value*127 + 128))
                ))
            elif event.type == pygame.VIDEORESIZE:
                if not self.fullscreen:
                    self._window_sizer.set_display_size(event.w, event.h)
                    self._resize_display()
            elif event.type == pygame.QUIT:
                if self._nokill:
                    self.set_caption_message(NOKILL_MESSAGE)
                else:
                    self._input_queue.put(signals.Event(signals.QUIT))

    def _handle_key_down(self, e):
        """Handle key-down event."""
        # get scancode
        scan = KEY_TO_SCAN.get(e.key, None)
        # get modifiers
        mod = [s for m, s in iteritems(MOD_TO_SCAN) if e.mod & m]
        # compensate for missing l-alt down events (needed at least on Ubuntu Unity)
        if (e.mod & pygame.KMOD_LALT) and not self._alt_key_down:
            # insert an alt keydown event before the alt-modified keydown
            fake_event = pygame.event.Event(
                pygame.KEYDOWN, scancode=0, key=pygame.K_LALT, unicode=u'', mod=0
            )
            self._handle_key_down(fake_event)
        if e.key == pygame.K_LALT:
            self._alt_key_down = True
        # get eascii
        try:
            if e.mod & pygame.KMOD_LALT:
                c = ALT_KEY_TO_EASCII[e.key]
            elif e.mod & pygame.KMOD_CTRL:
                c = CTRL_KEY_TO_EASCII[e.key]
            elif e.mod & pygame.KMOD_SHIFT:
                c = SHIFT_KEY_TO_EASCII[e.key]
            else:
                c = KEY_TO_EASCII[e.key]
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
                self._window_sizer.set_canvas_size(*self.size, fullscreen=self.fullscreen)
                self._resize_display()
            self.clipboard.handle_key(scan, c)
            self.busy = True
        else:
            # double NUL characters, as single NUL signals e-ASCII
            if c == u'\0':
                c = uea.NUL
            # fix missing ascii for numeric keypad on Windows
            if e.mod & pygame.KMOD_NUM:
                try:
                    c = KEY_TO_EASCII_NUM[e.key]
                except KeyError:
                    pass
            # insert into keyboard queue
            self._input_queue.put(signals.Event(signals.KEYB_DOWN, (c, scan, mod)))

    def _handle_key_up(self, e):
        """Handle key-up event."""
        # compensate for missing l-alt down events (needed at least on Ubuntu Unity)
        if (e.key == pygame.K_LALT or e.mod & pygame.KMOD_LALT) and not self._alt_key_down:
            # insert an alt keydown event before the alt-modified keydown
            fake_event = pygame.event.Event(
                pygame.KEYDOWN, scancode=0, key=pygame.K_LALT, unicode=u'', mod=0
            )
            self._handle_key_down(fake_event)
            if e.key != pygame.K_LALT:
                # insert a keydown before the keyup
                if not hasattr(e, 'unicode'):
                    e.unicode = u''
                self._handle_key_down(e)
        if e.key == pygame.K_LALT:
            self._alt_key_down = False
        elif e.key == pygame.K_F11:
            self.clipboard.stop()
            self.busy = True
            self.f11_active = False
        # last key released gets remembered
        try:
            self._input_queue.put(signals.Event(signals.KEYB_UP, (KEY_TO_SCAN[e.key],)))
        except KeyError:
            pass


    ###########################################################################
    # screen drawing cycle

    def sleep(self, ms):
        """Sleep a tick to avoid hogging the cpu."""
        pygame.time.wait(ms)

    def _work(self):
        """Check screen and blink events; update screen if necessary."""
        if not self._has_window:
            return
        self.blink_state = 0
        if self._palette_blinks or self.text_cursor:
            self.blink_state = 0 if self._cycle < BLINK_CYCLES * 2 else 1
            if self._cycle % BLINK_CYCLES == 0:
                self.busy = True
        if self.cursor_visible and (
                (self.cursor_row != self.last_row) or (self.cursor_col != self.last_col)
            ):
            self.busy = True
        tock = pygame.time.get_ticks()
        if tock - self.last_cycle >= CYCLE_TIME:
            self.last_cycle = tock
            self._cycle += 1
            if self._cycle == BLINK_CYCLES * 4:
                self._cycle = 0
        if self.busy:
            self._do_flip()
            self.busy = False

    def _do_flip(self):
        """Draw the canvas to the screen."""
        # create the screen that will be stretched onto the display
        border_x, border_y = self._window_sizer.border_shift
        # surface depth and flags match those of canvas
        # pylint: disable=E1121,E1123
        screen = pygame.Surface(
            (self.size[0] + 2*border_x, self.size[1] + 2*border_y),
            0, self.canvas
        )
        screen.set_palette(self.work_palette)
        # border colour
        border_colour = pygame.Color(0, 0, self.border_attr % self.num_fore_attrs)
        screen.fill(border_colour)
        screen.blit(self.canvas, (border_x, border_y))
        # subsurface referencing the canvas area
        workscreen = screen.subsurface((border_x, border_y, self.size[0], self.size[1]))
        self._draw_cursor(workscreen)
        if self.clipboard.active():
            create_feedback(workscreen, self.clipboard.selection_rect)
        if self._pixel_packing:
            screen = apply_composite_artifacts(screen, *self._pixel_packing)
        screen.set_palette(self._palette[self.blink_state])
        letterbox = pygame.Rect(
            self._window_sizer.letterbox_shift, self._window_sizer.window_size
        )
        if self._smooth:
            # smoothscale to subsurface does not work correctly, so create a new surface and blit
            dest_surf = pygame.Surface(self._window_sizer.window_size) #, self.display)
            pygame.transform.smoothscale(
                screen.convert(dest_surf), self._window_sizer.window_size, dest_surf
            )
            self.display.blit(dest_surf, letterbox)
        else:
            dest_surf = self.display.subsurface(letterbox)
            pygame.transform.scale(
                screen.convert(dest_surf), self._window_sizer.window_size, dest_surf
            )
        pygame.display.flip()

    def _draw_cursor(self, screen):
        """Draw the cursor on the surface provided."""
        if not self.cursor_visible:
            return
        # copy screen under cursor
        self.under_top_left = (
            (self.cursor_col-1) * self.font_width,
            (self.cursor_row-1) * self.font_height
        )
        under_char_area = pygame.Rect(
            (self.cursor_col-1) * self.font_width, (self.cursor_row-1) * self.font_height,
            self.cursor_width, self.font_height
        )
        if self.text_cursor:
            # cursor is visible - to be done every cycle between 5 and 10, 15 and 20
            if self._cycle // BLINK_CYCLES in (1, 3):
                screen.blit(
                    self.cursor,
                    ((self.cursor_col-1) * self.font_width, (self.cursor_row-1) * self.font_height)
                )
        else:
            index = self.cursor_attr % self.num_fore_attrs
            # reference the destination area
            dest_array = pygame.surfarray.pixels2d(
                screen.subsurface(pygame.Rect(
                    (self.cursor_col-1) * self.font_width,
                    (self.cursor_row-1) * self.font_height + self.cursor_from,
                    self.cursor_width,
                    self.cursor_to - self.cursor_from + 1
                ))
            )
            dest_array ^= index
        self.last_row = self.cursor_row
        self.last_col = self.cursor_col

    ###########################################################################
    # miscellaneous helper functions

    def _resize_display(self):
        """Change the display size."""
        if self.fullscreen:
            flags = pygame.NOFRAME
        else:
            flags = pygame.RESIZABLE
        self.display = pygame.display.set_mode(self._window_sizer.display_size, flags)
        # load display if requested
        self.busy = True


    ###########################################################################
    # signal handlers

    def set_mode(self, canvas_height, canvas_width, text_height, text_width):
        """Initialise a given text or graphics mode."""
        # set display geometry
        self.font_height = -(-canvas_height // text_height)
        self.font_width = canvas_width // text_width
        # logical size
        self.size = canvas_width, canvas_height
        self._window_sizer.set_canvas_size(*self.size, fullscreen=self.fullscreen)
        self._resize_display()
        # set standard cursor
        self.cursor_width = self.font_width
        self.set_cursor_shape(0, self.font_height)
        # whole screen (blink on & off)
        self.canvas = pygame.Surface(self.size, depth=8) # pylint: disable=E1121,E1123
        self.canvas.set_palette(self.work_palette)
        # initialise clipboard
        self.clipboard = clipboard.ClipboardInterface(
            self.clipboard_handler, self._input_queue,
            text_width, text_height, self.font_width, self.font_height, self.size
        )
        self.busy = True
        self._has_window = True

    def set_caption_message(self, msg):
        """Add a message to the window caption."""
        title = self.caption + (u' - ' + msg if msg else u'')
        pygame.display.set_caption(title.encode('utf-8', 'replace'))

    def set_clipboard_text(self, text):
        """Put text on the clipboard."""
        self.clipboard_handler.copy(text)

    def set_palette(self, attributes, pack_pixels):
        """Build the palette."""
        self.num_fore_attrs = 16
        self.num_back_attrs = 8
        # fill up the 8-bit palette with all combinations we need
        # blink states: 0 light up, 1 light down
        # bottom 128 are non-blink, top 128 blink to background
        self._palette[0] = [_fore for _fore, _, _, _ in attributes]
        self._palette[1] = [_back if _blink else _fore for _fore, _back, _blink, _ in attributes]
        self._palette_blinks = self._palette[0] != self._palette[1]
        self._pixel_packing = pack_pixels
        self.busy = True

    def set_border_attr(self, attr):
        """Change the border attribute."""
        self.border_attr = attr
        self.busy = True

    def clear_rows(self, back_attr, start, stop):
        """Clear a range of screen rows."""
        bg = (0, 0, back_attr)
        scroll_area = pygame.Rect(
            0, (start-1)*self.font_height, self.size[0], (stop-start+1)*self.font_height
        )
        self.canvas.fill(bg, scroll_area)
        self.busy = True

    def show_cursor(self, cursor_on, cursor_blinks):
        """Change visibility of cursor."""
        self.cursor_visible = cursor_on
        self.text_cursor = cursor_blinks
        self.busy = True

    def move_cursor(self, row, col, attr, width):
        """Move the cursor to a new position."""
        self.cursor_row, self.cursor_col = row, col
        # set attribute
        self.cursor_attr = attr % self.num_fore_attrs
        # set width
        if width != self.cursor_width:
            self.cursor_width = width
            self._rebuild_cursor()
        else:
            self.cursor.set_palette_at(254, pygame.Color(0, self.cursor_attr, self.cursor_attr))

    def scroll(self, direction, from_line, scroll_height, back_attr):
        """Scroll the screen between from_line and scroll_height."""
        temp_scroll_area = pygame.Rect(
            0, (from_line-1)*self.font_height,
            self.size[0], (scroll_height-from_line+1) * self.font_height
        )
        # scroll
        self.canvas.set_clip(temp_scroll_area)
        self.canvas.scroll(0, direction * self.font_height)
        # empty new line
        bg = (0, 0, back_attr)
        self.canvas.fill(
            bg, (0, (scroll_height-1) * self.font_height, self.size[0], self.font_height)
        )
        self.canvas.set_clip(None)
        self.busy = True

    def set_cursor_shape(self, from_line, to_line):
        """Build a sprite for the cursor."""
        self.cursor_from, self.cursor_to = from_line, to_line
        self._rebuild_cursor()

    def _rebuild_cursor(self):
        """Rebuild cursor surface."""
        height = self.font_height
        width = self.cursor_width
        from_line, to_line = self.cursor_from, self.cursor_to
        self.cursor = pygame.Surface((width, height), depth=8) # pylint: disable=E1121,E1123
        color, bg = 254, 255
        self.cursor.set_colorkey(bg)
        self.cursor.fill(bg)
        self.cursor.fill(color, (0, from_line, width, min(to_line-from_line+1, height-from_line)))
        self.cursor.set_palette_at(254, pygame.Color(0, self.cursor_attr, self.cursor_attr))
        self.busy = True

    def update(self, row, col, unicode_matrix, attr_matrix, y0, x0, array):
        """Put text or pixels at a given position."""
        if y0 + array.height > self.size[1] or x0 +array. width > self.size[0]:
            array = array[:self.size[1]-y0, :self.size[0]-x0]
        # reference the destination area
        subsurface = self.canvas.subsurface(pygame.Rect(x0, y0, array.width, array.height))
        pygame.surfarray.blit_array(subsurface, _BufferWrapper(array))
        self.busy = True


class _BufferWrapper(object):

    def __init__(self, array):
        self._buffer = ctypes.create_string_buffer(array.to_bytes())
        self.__array_interface__ = dict(
            shape=(array.width, array.height),
            strides=(1, array.width),
            typestr='|u1', version=3, data=(ctypes.addressof(self._buffer), False)
        )



###############################################################################
# clipboard handling

class PygameClipboard(clipboard.Clipboard):
    """Clipboard handling using Pygame.Scrap."""

    # text type we look for in the clipboard
    text = (
        'UTF8_STRING', 'text/plain;charset=utf-8', 'text/plain',
        'TEXT', 'STRING'
    )

    def __init__(self):
        """Initialise the clipboard handler."""
        try:
            pygame.scrap.init()
            self.ok = True
        except Exception:
            if pygame:
                logging.warning('PyGame.Scrap clipboard handling module not found.')
            self.ok = False

    def copy(self, text):
        """Put unicode text on clipboard."""
        pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        try:
            if WIN32:
                # on Windows, encode as utf-16 without FF FE byte order mark and null-terminate
                # but give it a utf-8 MIME type, because that's how Windows likes it
                pygame.scrap.put(
                    'text/plain;charset=utf-8', text.encode('utf-16le', 'replace') + b'\0\0'
                )
            else:
                pygame.scrap.put(pygame.SCRAP_TEXT, text.encode('utf-8', 'replace'))
        except Exception as e:# KeyError:
            logging.debug('Clipboard copy failed for clip %r: %s', text, e)

    def paste(self):
        """Return unicode text from clipboard."""
        pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        us = u''
        s = b''
        available = pygame.scrap.get_types()
        for text_type in self.text:
            if text_type not in available:
                continue
            s = pygame.scrap.get(text_type)
            if s:
                break
        if WIN32:
            if text_type == 'text/plain;charset=utf-8':
                # it's lying, it's giving us UTF16 little-endian
                # ignore any bad UTF16 characters from outside
                us = s.decode('utf-16le', errors='replace')
            else:
                # fallback
                us = s.decode('ascii', errors='replace')
            # remove null-terminator
            us = us[:us.find(u'\0')]
        else:
            us = s.decode('utf-8', errors='replace')
        if us:
            us = us.replace(u'\r\n', u'\n').replace(u'\n', u'\r')
        return us or u''

def get_clipboard_handler():
    """Get a working Clipboard handler object."""
    # Pygame.Scrap doesn't work on OSX and crashes on Linux
    if MACOS:
        handler = clipboard.MacClipboard()
    elif WIN32:
        handler = PygameClipboard()
    else:
        handler = clipboard.XClipboard()
    if not handler.ok:
        logging.warning('Clipboard copy and paste not available.')
        handler = clipboard.Clipboard()
    return handler

def create_feedback(surface, selection_rects):
    """Create visual feedback for selection onto a surface."""
    for r in selection_rects:
        work_area = surface.subsurface(pygame.Rect(r))
        orig = work_area.copy()
        # add 1 to the color as a highlight
        orig.fill(pygame.Color(0, 0, 1))
        work_area.blit(orig, (0, 0), special_flags=pygame.BLEND_ADD)


###############################################################################
# import PyGame and define constants

pygame = None


def _import_pygame():
    """Import pygame and define constants."""
    global pygame
    global KEY_TO_SCAN, MOD_TO_SCAN, KEY_TO_EASCII_NUM
    global KEY_TO_EASCII, SHIFT_KEY_TO_EASCII, CTRL_KEY_TO_EASCII, ALT_KEY_TO_EASCII

    import pygame

    # these are PC keyboard scancodes
    KEY_TO_SCAN = {
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
        # don't catch right-Alt as it may inhibit AltGr on Windows
        #pygame.K_RALT: scancode.ALT,
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

    KEY_TO_EASCII = {
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

    SHIFT_KEY_TO_EASCII = {
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

    CTRL_KEY_TO_EASCII = {
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

    ALT_KEY_TO_EASCII = {
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

    MOD_TO_SCAN = {
        pygame.KMOD_LSHIFT: scancode.LSHIFT,
        pygame.KMOD_RSHIFT: scancode.RSHIFT,
        pygame.KMOD_LCTRL: scancode.CTRL,
        pygame.KMOD_RCTRL: scancode.CTRL,
        pygame.KMOD_LALT: scancode.ALT,
        # don't catch right-Alt as it may inhibit AltGr on Windows
        #pygame.KMOD_RALT: scancode.ALT,
    }

    KEY_TO_EASCII_NUM = {
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


def apply_composite_artifacts(screen, bpp_out, bpp_in):
    """Process the canvas to apply composite colour artifacts."""
    # not implemented
    return screen
