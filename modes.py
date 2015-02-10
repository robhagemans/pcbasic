"""
PC-BASIC 3.23 - modes.py
Emulated video modes

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import config
import state
import error
import vartypes

try:
    import numpy
except ImportError:
    numpy = None

def prepare():
    """ Prepare the video modes. """
    global video_capabilities, mono_monitor
    global circle_aspect
    video_capabilities = config.options['video']
    if video_capabilities == 'tandy':
        circle_aspect = (3072, 2000)
    else:
        circle_aspect = (4, 3)
    mono_monitor = config.options['monitor'] == 'mono'
    if video_capabilities == 'ega' and mono_monitor:
        video_capabilities = 'ega_mono'
    cga_low = config.options['cga-low']
    # set monochrome tint
    mono_tint = config.options['mono-tint']
    # build colour sets
    prepare_colours(mono_monitor, mono_tint)
    # initialise the 4-colour CGA palette    
    prepare_default_palettes(cga_low)


###############################################################################
# colour set

# CGA colours
colours16_colour = (    
    (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
    (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0x55,0x00), (0xaa,0xaa,0xaa), 
    (0x55,0x55,0x55), (0x55,0x55,0xff), (0x55,0xff,0x55), (0x55,0xff,0xff),
    (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff) )
# EGA colours
colours64 = (
    (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
    (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0xaa,0x00), (0xaa,0xaa,0xaa), 
    (0x00,0x00,0x55), (0x00,0x00,0xff), (0x00,0xaa,0x55), (0x00,0xaa,0xff),
    (0xaa,0x00,0x55), (0xaa,0x00,0xff), (0xaa,0xaa,0x55), (0xaa,0xaa,0xff),
    (0x00,0x55,0x00), (0x00,0x55,0xaa), (0x00,0xff,0x00), (0x00,0xff,0xaa),
    (0xaa,0x55,0x00), (0xaa,0x55,0xaa), (0xaa,0xff,0x00), (0xaa,0xff,0xaa),
    (0x00,0x55,0x55), (0x00,0x55,0xff), (0x00,0xff,0x55), (0x00,0xff,0xff),
    (0xaa,0x55,0x55), (0xaa,0x55,0xff), (0xaa,0xff,0x55), (0xaa,0xff,0xff),
    (0x55,0x00,0x00), (0x55,0x00,0xaa), (0x55,0xaa,0x00), (0x55,0xaa,0xaa),
    (0xff,0x00,0x00), (0xff,0x00,0xaa), (0xff,0xaa,0x00), (0xff,0xaa,0xaa),
    (0x55,0x00,0x55), (0x55,0x00,0xff), (0x55,0xaa,0x55), (0x55,0xaa,0xff),
    (0xff,0x00,0x55), (0xff,0x00,0xff), (0xff,0xaa,0x55), (0xff,0xaa,0xff),
    (0x55,0x55,0x00), (0x55,0x55,0xaa), (0x55,0xff,0x00), (0x55,0xff,0xaa),
    (0xff,0x55,0x00), (0xff,0x55,0xaa), (0xff,0xff,0x00), (0xff,0xff,0xaa),
    (0x55,0x55,0x55), (0x55,0x55,0xff), (0x55,0xff,0x55), (0x55,0xff,0xff),
    (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff) )

# mono intensities
# CGA mono
intensity16_mono = range(0x00, 0x100, 0x11) 
# SCREEN 10 EGA pseudocolours, blink state 0 and 1
intensity_ega_mono_0 = (0x00, 0x00, 0x00, 0xaa, 0xaa, 0xaa, 0xff, 0xff, 0xff)
intensity_ega_mono_1 = (0x00, 0xaa, 0xff, 0x00, 0xaa, 0xff, 0x00, 0xaa, 0xff)
# MDA/EGA mono text intensity (blink is attr bit 7, like in colour mode)
intensity_mda_mono = (0x00, 0xaa, 0xff)


def prepare_colours(mono_monitor, mono_tint):
    """ Prepare the colour sets. """
    global colours16, colours16_mono, colours_ega_mono_0, colours_ega_mono_1
    global colours_mda_mono
    # initialise tinted monochrome palettes
    colours16_mono = tuple(tuple(tint*i//255 for tint in mono_tint)
                           for i in intensity16_mono)
    colours_ega_mono_0 = tuple(tuple(tint*i//255 for tint in mono_tint)
                               for i in intensity_ega_mono_0)
    colours_ega_mono_1 = tuple(tuple(tint*i//255 for tint in mono_tint)
                               for i in intensity_ega_mono_1)
    colours_mda_mono = tuple(tuple(tint*i//255 for tint in mono_tint)
                             for i in intensity_mda_mono)
    if mono_monitor:
        colours16 = list(colours16_mono)
    else:
        colours16 = list(colours16_colour)


###############################################################################
# CGA default 4-colour palette

def get_cga4_palettes(cga_low):
    """ Get the default CGA palette according to palette number & mode. """
    # palette 1: Black, Ugh, Yuck, Bleah, choice of low & high intensity
    # palette 0: Black, Green, Red, Brown/Yellow, low & high intensity
    # tandy/pcjr have high-intensity white, but low-intensity colours
    # mode 5 (SCREEN 1 + colorburst on RGB) has red instead of magenta
    if video_capabilities in ('pcjr', 'tandy'):
        # pcjr does not have mode 5
        return {0: (0, 2, 4, 6), 1: (0, 3, 5, 15), 5: None}
    elif cga_low:
        return {0: (0, 2, 4, 6), 1: (0, 3, 5, 7), 5: (0, 3, 4, 7)}
    else:
        return {0: (0, 10, 12, 14), 1: (0, 11, 13, 15), 5: (0, 11, 12, 15)}


def prepare_default_palettes(cga_low):
    """ Set the default palettes. """
    global cga4_palettes
    global cga16_palette, ega_palette, ega_mono_palette
    global mda_palette, ega_mono_text_palette
    cga4_palettes = get_cga4_palettes(cga_low)
    # default 16-color and ega palettes
    cga16_palette = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)
    ega_palette = (0, 1, 2, 3, 4, 5, 20, 7, 56, 57, 58, 59, 60, 61, 62, 63)
    ega_mono_palette = (0, 4, 1, 8)
    # MDA text attributes: http://www.seasip.info/VintagePC/mda.html
    # see also http://support.microsoft.com/KB/35148
    # MDA palette is currently something of a hack; 
    # half-hardcoded in in video_curses. 
    # As a consequence ega_mono_text_palette is unused.
    mda_palette = (0, 1, 1, 1, 1, 1, 1, 1, 0, 2, 2, 2, 2, 2, 2, 2)
    # http://qbhlp.uebergeord.net/screen-statement-details-colors.html
    # underline/intensity/reverse video attributes are slightly different from mda
    # attributes 1, 9 should have underlining. 
    ega_mono_text_palette = (0, 1, 1, 1, 1, 1, 1, 1, 0, 2, 2, 2, 2, 2, 2, 0)


###############################################################################
# video modes

def get_modes(screen, cga4_palette, video_mem_size):
    """ Build lists of allowed graphics modes. """
    # Tandy/PCjr pixel aspect ratio is different from normal
    # suggesting screen aspect ratio is not 4/3.
    # Tandy pixel aspect ratios, experimentally found with CIRCLE:
    # screen 2, 6:     48/100   normal if aspect = 3072, 2000
    # screen 1, 4, 5:  96/100   normal if aspect = 3072, 2000
    # screen 3:      1968/1000 
    # screen 3 is strange, slighly off the 192/100 you'd expect
    graphics_mode = {
        # 04h 320x200x4  16384B 2bpp 0xb8000    screen 1
        # tandy:2 pages if 32k memory; ega: 1 page only 
        '320x200x4': 
            CGAMode(screen, '320x200x4', 320, 200, 25, 40, 3,
                    cga4_palette, colours16, bitsperpixel=2, 
                    interleave_times=2, bank_size=0x2000, 
                    num_pages=(
                        video_mem_size // (2*0x2000)
                        if video_capabilities in ('pcjr', 'tandy') 
                        else 1)),
        # 06h 640x200x2  16384B 1bpp 0xb8000    screen 2
        '640x200x2': 
            CGAMode(screen, '640x200x2', 640, 200, 25, 80, 1,
                    palette=(0, 15), colours=colours16, bitsperpixel=1,
                    interleave_times=2, bank_size=0x2000, num_pages=1,
                    supports_artifacts=True),
        # 08h 160x200x16 16384B 4bpp 0xb8000    PCjr/Tandy screen 3
        '160x200x16': 
            CGAMode(screen, '160x200x16', 160, 200, 25, 20, 15,
                    cga16_palette, colours16, bitsperpixel=4,
                    interleave_times=2, bank_size=0x2000,
                    num_pages=video_mem_size//(2*0x2000),
                    pixel_aspect=(1968, 1000), cursor_index=3),
        #     320x200x4  16384B 2bpp 0xb8000   Tandy/PCjr screen 4
        '320x200x4pcjr': 
            CGAMode(screen, '320x200x4pcjr', 320, 200, 25, 40, 3,
                    cga4_palette, colours16, bitsperpixel=2,
                    interleave_times=2, bank_size=0x2000,
                    num_pages=video_mem_size//(2*0x2000),
                    cursor_index=3),
        # 09h 320x200x16 32768B 4bpp 0xb8000    Tandy/PCjr screen 5
        '320x200x16pcjr': 
            CGAMode(screen, '320x200x16pcjr', 320, 200, 25, 40, 15,
                    cga16_palette, colours16, bitsperpixel=4,
                    interleave_times=4, bank_size=0x2000,
                    num_pages=video_mem_size//(4*0x2000),
                    cursor_index=3),
        # 0Ah 640x200x4  32768B 2bpp 0xb8000   Tandy/PCjr screen 6
        '640x200x4': 
            Tandy6Mode(screen, '640x200x4', 640, 200, 25, 80, 3,
                        cga4_palette, colours16, bitsperpixel=2,
                        interleave_times=4, bank_size=0x2000,
                        num_pages=video_mem_size//(4*0x2000),
                        cursor_index=3),
        # 0Dh 320x200x16 32768B 4bpp 0xa0000    EGA screen 7
        '320x200x16': 
            EGAMode(screen, '320x200x16', 320, 200, 25, 40, 15,
                    cga16_palette, colours16, bitsperpixel=4,
                    num_pages=video_mem_size//(4*0x2000),
                    interleave_times=1, bank_size=0x2000),                 
        # 0Eh 640x200x16    EGA screen 8
        '640x200x16': 
            EGAMode(screen, '640x200x16', 640, 200, 25, 80, 15,
                    cga16_palette, colours16, bitsperpixel=4,
                    num_pages=video_mem_size//(4*0x4000),
                    interleave_times=1, bank_size=0x4000),                 
        # 10h 640x350x16    EGA screen 9
        '640x350x16': 
            EGAMode(screen, '640x350x16', 640, 350, 25, 80, 15,
                    ega_palette, colours64, bitsperpixel=4,
                    num_pages=video_mem_size//(4*0x8000),
                    interleave_times=1, bank_size=0x8000),                 
        # 0Fh 640x350x4     EGA monochrome screen 10
        '640x350x4': 
            EGAMode(screen, '640x350x16', 640, 350, 25, 80, 1,
                    ega_mono_palette, colours_ega_mono_0, bitsperpixel=2,
                    interleave_times=1, bank_size=0x8000,
                    num_pages=video_mem_size//(2*0x8000),
                    colours1=colours_ega_mono_1, has_blink=True,
                    planes_used=(1, 3)),                 
        # 40h 640x400x2   1bpp  olivetti screen 3
        '640x400x2': 
            CGAMode(screen, '640x400x2', 640, 400, 25, 80, 1,
                    palette=(0, 15), colours=colours16, bitsperpixel=1,
                    interleave_times=4, bank_size=0x2000,
                    num_pages=1,
                    has_blink=True),
        # hercules screen 3
        '720x348x2': 
            # TODO hercules - this actually produces 350, not 348
            # two scan lines must be left out somewhere, somehow
            CGAMode(screen, '720x348x2', 720, 350, 25, 80, 1,
                    palette=(0, 15), colours=colours16_mono, bitsperpixel=1,
                    interleave_times=4, bank_size=0x2000,
                    num_pages=2,
                    has_blink=True),
        }
    if video_capabilities == 'vga':    
        # technically, VGA text does have underline 
        # but it's set to an invisible scanline
        # so not, so long as we're not allowing to set the scanline
        text_data = {
            40: TextMode(screen, 'vgatext40', 25, 40, 16, 9, 7, 
                         ega_palette, colours64, num_pages=8),            
            80: TextMode(screen, 'vgatext80', 25, 80, 16, 9, 7, 
                         ega_palette, colours64, num_pages=4)}
        mode_data = {
            1: graphics_mode['320x200x4'],
            2: graphics_mode['640x200x2'],
            7: graphics_mode['320x200x16'],
            8: graphics_mode['640x200x16'],
            9: graphics_mode['640x350x16']}
    elif video_capabilities == 'ega':    
        text_data = {
            40: TextMode(screen, 'egatext40', 25, 40, 14, 8, 7, 
                         ega_palette, colours64, num_pages=8),
            80: TextMode(screen, 'egatext80', 25, 80, 14, 8, 7, 
                         ega_palette, colours64, num_pages=4)}
        mode_data = {
            1: graphics_mode['320x200x4'],
            2: graphics_mode['640x200x2'],
            7: graphics_mode['320x200x16'],
            8: graphics_mode['640x200x16'],
            9: graphics_mode['640x350x16']}
    elif video_capabilities == 'ega_mono': 
        text_data = {
            40: TextMode(screen, 'ega_monotext40', 25, 40, 14, 8, 7, 
                         mda_palette, colours_mda_mono, 
                         is_mono=True, has_underline=True, num_pages=8),
            80: TextMode(screen, 'ega_monotext80', 25, 80, 14, 8, 7, 
                         mda_palette, colours_mda_mono, 
                         is_mono=True, has_underline=True, num_pages=4)}
        mode_data = {
            10: graphics_mode['640x350x4']}
    elif video_capabilities == 'mda': 
        text_data = {
            40: TextMode(screen, 'mdatext40', 25, 40, 14, 9, 7,
                         mda_palette, colours_mda_mono,
                         is_mono=True, has_underline=True, num_pages=1),
            80: TextMode(screen, 'mdatext80', 25, 80, 14, 9, 7,
                         mda_palette, colours_mda_mono,
                         is_mono=True, has_underline=True, num_pages=1) }
        mode_data = {}
    elif video_capabilities in ('cga', 'cga_old', 'pcjr', 'tandy'):    
        if video_capabilities == 'tandy': 
            text_data = {
                40: TextMode(screen, 'tandytext40', 25, 40, 9, 8, 7, 
                              cga16_palette, colours16, num_pages=8),
                80: TextMode(screen, 'tandytext80', 25, 80, 9, 8, 7, 
                              cga16_palette, colours16, num_pages=4)}
        else:
            text_data = {
                40: TextMode(screen, 'cgatext40', 25, 40, 8, 8, 7, 
                             cga16_palette, colours16, num_pages=8),
                80: TextMode(screen, 'cgatext80', 25, 80, 8, 8, 7, 
                             cga16_palette, colours16, num_pages=4)}
        if video_capabilities in ('cga', 'cga_old'):                     
            mode_data = {
                1: graphics_mode['320x200x4'],
                2: graphics_mode['640x200x2']}
        else:
            mode_data = {
                1: graphics_mode['320x200x4'],
                2: graphics_mode['640x200x2'],
                3: graphics_mode['160x200x16'],
                4: graphics_mode['320x200x4pcjr'],
                5: graphics_mode['320x200x16pcjr'],
                6: graphics_mode['640x200x4']}
    elif video_capabilities == 'hercules': 
        # herc attributes shld distinguish black, dim, normal, bright
        # see http://www.seasip.info/VintagePC/hercplus.html
        text_data = {
            40: TextMode(screen, 'herculestext40', 25, 40, 14, 9, 7, 
                         mda_palette, colours_mda_mono,
                         is_mono=True, has_underline=True, num_pages=2),
            80: TextMode(screen, 'herculestext80', 25, 80, 14, 9, 7, 
                         mda_palette, colours_mda_mono,
                         is_mono=True, has_underline=True, num_pages=2) }
        mode_data = {
            3: graphics_mode['720x348x2']}
    elif video_capabilities == 'olivetti': 
        text_data = {
            40: TextMode(screen, 'olivettitext40', 25, 40, 16, 8, 7,
                          cga16_palette, colours16, num_pages=8),
            80: TextMode(screen, 'olivettitext80', 25, 80, 16, 8, 7,
                          cga16_palette, colours16, num_pages=4) }
        mode_data = {
            1: graphics_mode['320x200x4'],
            2: graphics_mode['640x200x2'],
            3: graphics_mode['640x400x2']}
        # on Olivetti M24, all numbers 3-255 give the same altissima risoluzione
        for mode in range(4, 256):
            mode_data[mode] = graphics_mode['640x400x2']
    return text_data, mode_data


class VideoMode(object):
    """ Base class for video modes. """
    def __init__(self, screen, name, height, width,
                  font_height, font_width, 
                  attr, palette, colours, 
                  num_pages,
                  has_underline, has_blink,
                  video_segment, page_size
                  ):
        """ Initialise video mode settings. """
        self.screen = screen
        self.is_text_mode = False
        self.name = name
        self.height = int(height)
        self.width = int(width)
        self.font_height = int(font_height)
        self.font_width = int(font_width)
        self.pixel_height = self.height*self.font_height
        self.pixel_width = self.width*self.font_width
        self.attr = int(attr)
        # palette is a reference (changes with cga_mode_5 and cga4_palette_num)
        self.palette = palette
        self.num_attr = len(palette)
        # colours is a reference (changes with colorburst on composite)
        self.colours = colours
        # colours1 is only used by EGA mono mode
        self.colours1 = None
        self.has_blink = has_blink
        self.has_underline = has_underline
        self.video_segment = int(video_segment)
        self.page_size = int(page_size)
        self.num_pages = int(num_pages) # or video_mem_size // self.page_size)

    
class TextMode(VideoMode):
    """ Default settings for a text mode. """
    
    def __init__(self, screen, name, height, width,
                  font_height, font_width, 
                  attr, palette, colours, 
                  num_pages,
                  is_mono=False, has_underline=False, has_blink=True):
        """ Initialise video mode settings. """
        video_segment = 0xb000 if is_mono else 0xb800
        page_size = 0x1000 if width == 80 else 0x800
        VideoMode.__init__(self, screen, name, height, width,
                  font_height, font_width, 
                  attr, palette, colours, 
                  num_pages, has_underline, has_blink, 
                  video_segment, page_size)
        self.is_text_mode = True
        self.num_attr = 32
        self.has_underline = has_underline

    def get_memory(self, addr, num_bytes):
        """ Retrieve bytes from textmode video memory. """
        addr -= self.video_segment*0x10
        bytes = [0]*num_bytes
        for i in xrange(num_bytes):
            page = (addr+i) // self.page_size
            offset = (addr+i) % self.page_size
            ccol = (offset % (self.width*2)) // 2
            crow = offset // (self.width*2)
            try:
                c = self.screen.text.pages[page].row[crow].buf[ccol][(addr+i)%2]  
                bytes[i] = c if (addr+i)%2==1 else ord(c)
            except IndexError:
                pass
        return bytes    
    
    def set_memory(self, addr, bytes):
        """ Set bytes in textmode video memory. """
        addr -= self.video_segment*0x10
        last_row = -1
        for i in xrange(len(bytes)):
            page = (addr+i) // self.page_size
            offset = (addr+i) % self.page_size
            ccol = (offset % (self.width*2)) // 2
            crow = offset // (self.width*2)
            try:
                c, a = self.screen.text.pages[page].row[crow].buf[ccol]
                if (addr+i)%2 == 0:
                    c = chr(bytes[i])
                else:
                    a = bytes[i]
                self.screen.text.pages[page].put_char_attr(crow+1, ccol+1, c, a, one_only=False)
                if last_row != crow:
                    # set for_keys to true to avoid echoing to text terminal
                    self.screen.refresh_range(page, last_row+1, 1, self.width, for_keys=True)
            except IndexError:
                pass
            last_row = crow
        if last_row >= 0 and last_row < 25 and page >= 0 and page < self.num_pages:
            self.screen.refresh_range(page, last_row+1, 1, self.width, for_keys=True)


# helper functions: convert between attribute lists and byte arrays

if numpy:
    def bytes_to_interval(bytes, pixels_per_byte, mask=1):
        """ Convert masked attributes packed into bytes to a scanline interval. """
        bpp = 8//pixels_per_byte
        attrmask = (1<<bpp) - 1
        bitval = numpy.array([128, 64, 32, 16, 8, 4, 2, 1], dtype=numpy.uint8)
        bitmask = bitval[0::bpp]
        for i in xrange(1, bpp):
            bitmask |= bitval[i::bpp]
        pre_mask = numpy.tile(bitmask, len(bytes))
        post_shift = numpy.tile(
                        numpy.array([7, 6, 5, 4, 3, 2, 1, 0])[(bpp-1)::bpp], 
                        len(bytes))
        attrs = numpy.right_shift(
                    numpy.repeat(numpy.array(bytes).astype(int), 
                                 pixels_per_byte) & pre_mask,
                    post_shift) & attrmask
        return numpy.array(attrs) * mask

    def interval_to_bytes(colours, pixels_per_byte, plane=0):
        """ Convert a scanline interval into masked attributes packed into bytes. """
        num_pixels = len(colours)
        num_bytes, odd_out = divmod(num_pixels, pixels_per_byte)
        if odd_out:
            num_bytes += 1
        bpp = 8//pixels_per_byte
        attrmask = (1<<bpp) - 1
        colours = numpy.array(colours).astype(int)
        if odd_out:
            colours.resize(len(colours)+pixels_per_byte-odd_out)
        shift = numpy.tile(numpy.array([7, 6, 5, 4, 3, 2, 1, 0])[(bpp-1)::bpp], 
                           num_bytes)
        attrs = numpy.right_shift(colours, plane)
        attrs = numpy.left_shift(attrs & attrmask, shift)
        # below is much faster than:
        #   return list([ sum(attrs[i:i+pixels_per_byte]) 
        #                 for i in xrange(0, len(attrs), pixels_per_byte) ])
        # and anything involving numpy.array_split or numpy.dot is even slower.
        # numpy.roll is ok but this is the fastest I've found:
        nattrs = attrs[0::pixels_per_byte]
        for i in xrange(1, pixels_per_byte):
            nattrs |= attrs[i::pixels_per_byte]
        return list(nattrs)

else:
    def bytes_to_interval(bytes, pixels_per_byte, mask=1):
        """ Convert masked attributes packed into bytes to a scanline interval. """
        bpp = 8//pixels_per_byte
        attrmask = (1<<bpp) - 1
        return [((byte >> (8-bpp-shift)) & attrmask) * mask
                    for byte in bytes for shift in xrange(0, 8, bpp)]

    def interval_to_bytes(colours, pixels_per_byte, plane=0):
        """ Convert a scanline interval into masked attributes packed into bytes. """
        num_pixels = len(colours)
        num_bytes, odd_out = divmod(num_pixels, pixels_per_byte)
        if odd_out:
            num_bytes += 1
        bpp = 8//pixels_per_byte
        attrmask = (1<<bpp) - 1
        colours = list(colours)
        byte_list = [0]*num_bytes
        shift, byte = -1, -1
        for x in xrange(num_pixels):
            if shift < 0:
                shift = 8 - bpp
                byte += 1
            byte_list[byte] |= ((colours[x] >> plane) & attrmask) << shift
            shift -= bpp
        return byte_list            

def set_memory_ega(self, addr, bytes, mask, factor=1):
    """ Set bytes in EGA video memory (helper). """
    ppb = 8
    row_bytes = self.screen.mode.pixel_width // ppb
    # if first row is incomplete, do a slow draw till the end of row.
    # length of short or full first row
    page, x, y = self.get_coords(addr)
    short_row = min(row_bytes - x//ppb, len(bytes))
    # short first row
    if self.coord_ok(page, x, y):
        colours = bytes_to_interval(bytes[:short_row], ppb, mask)
        self.screen.put_interval(page, 0, y, colours, mask)
    offset = short_row
    # full rows
    bank_offset = 0
    while bank_offset + offset < len(bytes):
        y += 1
        if offset > self.bank_size//factor:
            bank_offset += self.bank_size//factor
            offset = 0
            y = 0
            page += 1
        if self.coord_ok(page, x, y):
            ofs = bank_offset + offset
            colours = bytes_to_interval(bytes[ofs:ofs+row_bytes], ppb, mask)
            self.screen.put_interval(page, 0, y, colours, mask) 
        offset += row_bytes

def get_memory_ega(self, addr, num_bytes, plane, factor=1):
    """ Set bytes in EGA video memory (helper). """
    row_bytes = self.screen.mode.pixel_width // 8 
    # if first row is incomplete, do a slow draw till the end of row.
    # length of short or full first row
    page, x, y = self.get_coords(addr)
    byteshift = min(self.bytes_per_row - x//8, num_bytes)
    # first row, may be short
    attrs = self.screen.get_interval(page, 0, y, byteshift*8) 
    bytes = interval_to_bytes(attrs, 8, plane)
    offset = byteshift
    # full rows
    bank_offset = 0
    while bank_offset + offset < num_bytes:
        y += 1
        # not an integer number of rows in a bank
        if offset > self.bank_size//factor:
            bytes += [0] * (offset - self.bank_size//factor)
            bank_offset += self.bank_size//factor
            offset = 0
            y = 0
            page += 1
        if self.coord_ok(page, 0, y):
            attrs = self.screen.get_interval(page, 0, y, self.pixel_width)
            bytes += interval_to_bytes(attrs, 8, plane)
        else:
            bytes += [0] * self.bytes_per_row
        offset += self.bytes_per_row
    offset += self.bytes_per_row
    return bytes

def sprite_size_to_record_ega(self, dx, dy):
    """ Write 4-byte record of sprite size in EGA modes. """
    return vartypes.value_to_uint(dx) + vartypes.value_to_uint(dy)

def record_to_sprite_size_ega(self, byte_array):
    """ Read 4-byte record of sprite size in EGA modes. """
    dx = vartypes.uint_to_value(byte_array[0:2])
    dy = vartypes.uint_to_value(byte_array[2:4])
    return dx, dy

def sprite_to_array_ega(self, attrs, dx, dy, byte_array, offset):
    """ Build the sprite byte array in EGA modes. """
    # for EGA modes, sprites have 8 pixels per byte 
    # with colour planes in consecutive rows
    # each new row is aligned on a new byte
    #
    # this is much faster for wide selections 
    # but for narrow selections storing in an array and indexing take longer
    # than just getting each pixel separately
    row_bytes = (dx+7) // 8
    length = dy * self.bitsperpixel * row_bytes
    byte_array[offset:offset+length] = '\x00'*length
    for row in attrs:
        for plane in range(self.bitsperpixel):
            byte_array[offset:offset+row_bytes] = (
                    bytearray(interval_to_bytes(row, 8, plane)))
            offset += row_bytes

# elementwise OR, in-place if possible
if numpy:
    or_i = numpy.ndarray.__ior__
else:    
    def or_i(list0, list1):
        return [ x | y for x, y in zip(list0, list1) ]

def array_to_sprite_ega(self, byte_array, offset, dx, dy):
    """ Build sprite from byte_array in EGA modes. """
    row_bytes = (dx+7) // 8
    attrs = []
    for y in range(dy):
        row = bytes_to_interval(byte_array[offset:offset+row_bytes], 8, 1)
        offset += row_bytes
        for plane in range(1, self.bitsperpixel):
            row = or_i(row, bytes_to_interval(
                            byte_array[offset:offset+row_bytes], 8, 1 << plane))
            offset += row_bytes
        attrs.append(row[:dx])
    return attrs
    
def build_tile_cga(self, pattern):
    """ Build a flood-fill tile for CGA screens. """
    tile = []    
    bpp = self.bitsperpixel
    strlen = len(pattern)
    # in modes 1, (2), 3, 4, 5, 6 colours are encoded in consecutive bits
    # each byte represents one scan line
    mask = 8 - bpp
    for y in range(strlen):
        line = []
        for x in range(8): # width is 8//bpp
            c = 0
            for b in range(bpp-1, -1, -1):
                c = (c<<1) + ((pattern[y] >> (mask+b)) & 1) 
            mask -= bpp
            if mask < 0:
                mask = 8 - bpp
            line.append(c)    
        tile.append(line)
    return tile


class GraphicsMode(VideoMode):
    """ Default settings for a graphics mode. """
    
    def __init__(self, screen, name, pixel_width, pixel_height,
                  text_height, text_width, 
                  attr, palette, colours, bitsperpixel, 
                  interleave_times, bank_size,
                  num_pages=None,
                  has_blink=False,
                  supports_artifacts=False,
                  cursor_index=None,
                  pixel_aspect=None,
                  video_segment=0xb800,
                  ):
        """ Initialise video mode settings. """
        font_width = int(pixel_width // text_width)
        font_height = int(pixel_height // text_height)
        self.interleave_times = int(interleave_times)
        # cga bank_size = 0x2000 interleave_times=2
        self.bank_size = int(bank_size)
        page_size = self.interleave_times * self.bank_size
        VideoMode.__init__(self, screen, name, text_height, text_width, 
                          font_height, font_width, attr, palette, colours,
                          num_pages, False, has_blink, video_segment, page_size)
        self.is_text_mode = False
        self.bitsperpixel = int(bitsperpixel)
        self.num_attr = 2**self.bitsperpixel
        self.bytes_per_row = int(pixel_width) * self.bitsperpixel // 8
        self.supports_artifacts = supports_artifacts
        self.cursor_index = cursor_index
        if pixel_aspect:
            self.pixel_aspect = pixel_aspect
        else:      
            self.pixel_aspect = (self.pixel_height * circle_aspect[0], 
                                 self.pixel_width * circle_aspect[1])

    def coord_ok(self, page, x, y):
        """ Check if a page and coordinates are within limits. """
        return (page >= 0 and page < self.num_pages and
                x >= 0 and x < self.pixel_width and
                y >= 0 and y < self.pixel_height)

    def cutoff_coord(self, x, y):
        """ Ensure coordinates are within screen + 1 pixel. """
        return min(self.pixel_width, max(-1, x)), min(self.pixel_height, max(-1, y))

    def set_plane(self, plane):
        """ Set the current colour plane (EGA only). """
        pass

    def set_plane_mask(self, mask):
        """ Set the current colour plane mask (EGA only). """
        pass    

class CGAMode(GraphicsMode):
    """ Default settings for a CGA graphics mode. """

    def get_coords(self, addr):
        """ Get video page and coordinates for address. """
        addr = int(addr) - self.video_segment * 0x10
        # modes 1-5: interleaved scan lines, pixels sequentially packed into bytes
        page, addr = addr//self.page_size, addr%self.page_size
        # 2 x interleaved scan lines of 80bytes
        bank, offset = addr//self.bank_size, addr%self.bank_size
        row, col = offset//self.bytes_per_row, offset%self.bytes_per_row
        x = col * 8 // self.bitsperpixel
        y = bank + self.interleave_times * row
        return page, x, y        
        
    def get_memory(self, addr, num_bytes):
        """ Retrieve a byte from CGA memory. """
        page, x, y = self.get_coords(addr)
        ppb = 8//self.bitsperpixel
        byteshift = min(self.bytes_per_row - x//ppb, num_bytes)
        if self.coord_ok(page, x, y):
            attrs = self.screen.get_interval(page, x, y, byteshift*ppb)
            bytes = interval_to_bytes(attrs, ppb)
        else: 
            bytes = [0]*byteshift
        offset = byteshift        
        bank_offset = 0
        page_offset = 0
        i = 0
        while page_offset + bank_offset + offset < num_bytes:
            y += self.interleave_times
            # not an integer number of rows in a bank
            if offset > self.bank_size:
                bytes = bytes[:self.bank_size-offset]
                bank_offset += self.bank_size
                offset = 0
                i += 1
                y = i
                if bank_offset > self.page_size:
                    page_offset += self.page_size
                    bank_offset = 0
                    offset = 0
                    page += 1
                    y = 0
                    i = 0
            if self.coord_ok(page, 0, y):
                attrs = self.screen.get_interval(page, 0, y, self.pixel_width)
                bytes += interval_to_bytes(attrs, ppb)
            else:
                bytes += [0] * self.bytes_per_row
            offset += self.bytes_per_row
        return bytes[:num_bytes]

    def set_memory(self, addr, bytes):
        """ Set a list of bytes in CGA memory. """
        # draw (potentially incomplete) first row
        page, x, y = self.get_coords(addr)
        ppb = 8//self.bitsperpixel
        byteshift = min(self.bytes_per_row - x//ppb, len(bytes))
        if self.coord_ok(page, x, y):
            interval = bytes_to_interval(bytes[:byteshift], ppb)
            self.screen.put_interval(page, x, y, interval) 
        offset = byteshift        
        bank_offset = 0
        page_offset = 0
        i = 0
        while page_offset + bank_offset + offset < len(bytes):
            y += self.interleave_times
            if offset > self.bank_size:
                bank_offset += self.bank_size
                offset = 0
                i += 1
                y = i
                if bank_offset > self.page_size:
                    page_offset += self.page_size
                    bank_offset = 0
                    offset = 0
                    page += 1
                    y = 0
                    i = 0
            if self.coord_ok(page, 0, y):
                offs = page_offset + bank_offset + offset
                interval = bytes_to_interval(bytes[offs:offs+self.bytes_per_row], ppb)
                self.screen.put_interval(page, 0, y, interval) 
            offset += self.bytes_per_row

    def sprite_size_to_record(self, dx, dy):
        """ Write 4-byte record of sprite size. """
        return vartypes.value_to_uint(dx*self.bitsperpixel) + vartypes.value_to_uint(dy)

    def record_to_sprite_size(self, byte_array):
        """ Read 4-byte record of sprite size. """
        dx = vartypes.uint_to_value(byte_array[0:2]) / self.bitsperpixel
        dy = vartypes.uint_to_value(byte_array[2:4])
        return dx, dy

    def sprite_to_array(self, attrs, dx, dy, byte_array, offset):
        """ Build the sprite byte array. """
        row_bytes = (dx * self.bitsperpixel + 7) // 8
        length = row_bytes*dy
        byte_array[offset:offset+length] = '\x00'*length
        for row in attrs:
            byte_array[offset:offset+row_bytes] = (
                bytearray(interval_to_bytes(row, 8//self.bitsperpixel, 0)))
            offset += row_bytes
        
    def array_to_sprite(self, byte_array, offset, dx, dy):
        """ Build sprite from byte_array. """
        row_bytes = (dx * self.bitsperpixel + 7) // 8
        # illegal fn call if outside screen boundary
        attrs = []
        for y in range(dy):
            row = bytes_to_interval(byte_array[offset:offset+row_bytes], 
                                      8//self.bitsperpixel, 1)
            offset += row_bytes
            attrs.append(row[:dx])
        return attrs

    build_tile = build_tile_cga


class EGAMode(GraphicsMode):
    """ Default settings for a EGA graphics mode. """

    def __init__(self, screen, name, pixel_width, pixel_height,
                  text_height, text_width, 
                  attr, palette, colours, bitsperpixel, 
                  interleave_times, bank_size, num_pages, 
                  colours1=None, has_blink=False, planes_used=range(4), 
                  ):
        """ Initialise video mode settings. """
        GraphicsMode.__init__(self, screen, name, pixel_width, pixel_height,
                  text_height, text_width, 
                  attr, palette, colours, bitsperpixel, 
                  interleave_times, bank_size,
                  num_pages, has_blink)
        # EGA uses colour planes, 1 bpp for each plane
        self.bytes_per_row = pixel_width // 8
        self.video_segment = 0xa000
        self.planes_used = planes_used
        # additional colour plane mask
        self.master_plane_mask = sum([ 2**x for x in planes_used ])
        # this is a reference
        self.colours1 = colours1
        # current ega memory colour plane to read
        self.plane = 0
        # current ega memory colour planes to write to
        self.plane_mask = 0xff

    def set_plane(self, plane):
        """ Set the current colour plane. """
        self.plane = plane

    def set_plane_mask(self, mask):
        """ Set the current colour plane mask. """
        self.plane_mask = mask

    def get_coords(self, addr):
        """ Get video page and coordinates for address. """
        addr = int(addr) - self.video_segment * 0x10
        # modes 7-9: 1 bit per pixel per colour plane                
        page, addr = addr//self.page_size, addr%self.page_size
        x, y = (addr%self.bytes_per_row)*8, addr//self.bytes_per_row
        return page, x, y

    def get_memory(self, addr, num_bytes):
        """ Retrieve a byte from EGA memory. """
        plane = self.plane % (max(self.planes_used)+1)
        if plane not in self.planes_used:
            return [0]*num_bytes
        return get_memory_ega(self, addr, num_bytes, plane)    
        
    def set_memory(self, addr, bytes):
        """ Set bytes in EGA video memory. """
        # EGA memory is planar with memory-mapped colour planes.
        # Within a plane, 8 pixels are encoded into each byte.
        # The colour plane is set through a port OUT and
        # determines which bit of each pixel's attribute is affected.
        mask = self.plane_mask & self.master_plane_mask
        # return immediately for unused colour planes
        if mask == 0:
            return
        set_memory_ega(self, addr, bytes, mask)

    sprite_to_array = sprite_to_array_ega
    array_to_sprite = array_to_sprite_ega

    sprite_size_to_record = sprite_size_to_record_ega
    record_to_sprite_size = record_to_sprite_size_ega

    def build_tile(self, pattern):
        """ Build a flood-fill tile. """
        tile = []    
        bpp = self.bitsperpixel
        while len(pattern) % bpp != 0:
            # finish off the pattern with zeros
            pattern.append(0)
        strlen = len(pattern)
        # in modes (2), 7, 8, 9 each byte represents 8 bits
        # colour planes encoded in consecutive bytes
        mask = 7
        for y in range(strlen//bpp):
            line = []
            for x in range(8):
                c = 0
                for b in range(bpp-1, -1, -1):
                    c = (c<<1) + ((pattern[(y*bpp+b)%strlen] >> mask) & 1)
                mask -= 1
                if mask < 0:
                    mask = 7
                line.append(c)
            tile.append(line)    
        return tile


class Tandy6Mode(GraphicsMode):
    """ Default settings for Tandy graphics mode 6. """

    def __init__(self, *args, **kwargs):
        """ Initialise video mode settings. """
        GraphicsMode.__init__(self, *args, **kwargs)
        # mode 6: 4x interleaved scan lines, 8 pixels per two bytes, 
        # low attribute bits stored in even bytes, high bits in odd bytes.        
        self.bytes_per_row = self.pixel_width * 2 // 8
        self.video_segment = 0xb800

    def get_coords(self, addr):
        """ Get video page and coordinates for address. """
        addr =  int(addr) - self.video_segment * 0x10
        page, addr = addr//self.page_size, addr%self.page_size
        # 4 x interleaved scan lines of 160bytes
        bank, offset = addr//self.bank_size, addr%self.bank_size
        row, col = offset//self.bytes_per_row, offset%self.bytes_per_row
        x = (col // 2) * 8
        y = bank + 4 * row
        return page, x, y

    def get_memory(self, addr, num_bytes):
        """ Retrieve a byte from Tandy 640x200x4 """
        # 8 pixels per 2 bytes
        # low attribute bits stored in even bytes, high bits in odd bytes.        
        num_odd, num_even = num_bytes // 2
        page, x, y = self.get_coords(addr)
        if addr%2:
            num_even -= num_bytes%2
        else:
            num_odd -= num_bytes%2
        even_bytes = get_memory_ega(self, addr, num_even, 0, factor=2)
        odd_bytes = get_memory_ega(self, addr, num_odd, 1, factor=2)
        if addr%2:
            even_bytes, odd_bytes = odd_bytes, even_bytes
        return [item for pair in zip(even_bytes, odd_bytes) for item in pair]
        
    def set_memory(self, addr, bytes):
        """ Set a byte in Tandy 640x200x4 memory. """
        # page, x, y = self.get_coords(addr)
        # if self.coord_ok(page, x, y):
        #     set_pixel_byte(self.screen, page, x, y, 1<<(addr%2), val) 
        even_bytes = bytes[0::2]
        odd_bytes = bytes[1::2]
        if addr%2:
            even_bytes, odd_bytes = odd_bytes, even_bytes
        # Tandy-6 encodes 8 pixels per byte, alternating colour planes.
        # I.e. even addresses are 'colour plane 0', odd ones are 'plane 1'
        set_memory_ega(self, addr, even_bytes, 1, factor=2)
        set_memory_ega(self, addr, odd_bytes, 2, factor=2)

    sprite_to_array = sprite_to_array_ega
    array_to_sprite = array_to_sprite_ega

    sprite_size_to_record = sprite_size_to_record_ega
    record_to_sprite_size = record_to_sprite_size_ega

    build_tile = build_tile_cga


prepare()

