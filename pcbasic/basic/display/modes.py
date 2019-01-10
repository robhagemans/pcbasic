"""
PC-BASIC - modes.py
Emulated video modes

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import functools
import operator

from ...compat import xrange, int2byte, zip, iterbytes, PY2

from ..base import error
from ..base import bytematrix


###############################################################################
# colourserts and default palettes

# 2-colour CGA (SCREEN 2) palette
CGA2_PALETTE = (0, 15)
# 16 colour CGA palette (CGA text mode)
CGA16_PALETTE = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)
# EGA palette - these are the same colours as 16-colour CGA but picked from different coloursets
EGA_PALETTE = (0, 1, 2, 3, 4, 5, 20, 7, 56, 57, 58, 59, 60, 61, 62, 63)

# CGA 4-colour palettes
# palette 0: Black, Green, Red, Brown/Yellow
# palette 1: Black, Ugh, Yuck, Bleah
# "Mode 5" (SCREEN 1 + colorburst on RGB) has red instead of magenta
# low intensity
CGA4_LO_PALETTE_0 = (0, 2, 4, 6)
CGA4_LO_PALETTE_1 = (0, 3, 5, 7)
CGA4_LO_PALETTE_RED = (0, 3, 4, 7)
# high intensity
CGA4_HI_PALETTE_0 = (0, 10, 12, 14)
CGA4_HI_PALETTE_1 = (0, 11, 13, 15)
CGA4_HI_PALETTE_RED = (0, 11, 12, 15)

# PCjr/Tandy 4-colour palettes
# like CGA 4-colour, but low-intensity colours with high-intensity white
TANDY4_PALETTE_0 = (0, 2, 4, 6)
TANDY4_PALETTE_1 = (0, 3, 5, 15)

# CGA colourset
# note 'CGA brown' in position 6
COLOURS16 = (
    (0x00, 0x00, 0x00), (0x00, 0x00, 0xaa), (0x00, 0xaa, 0x00), (0x00, 0xaa, 0xaa),
    (0xaa, 0x00, 0x00), (0xaa, 0x00, 0xaa), (0xaa, 0x55, 0x00), (0xaa, 0xaa, 0xaa),
    (0x55, 0x55, 0x55), (0x55, 0x55, 0xff), (0x55, 0xff, 0x55), (0x55, 0xff, 0xff),
    (0xff, 0x55, 0x55), (0xff, 0x55, 0xff), (0xff, 0xff, 0x55), (0xff, 0xff, 0xff)
)
# EGA colourset
COLOURS64 = (
    (0x00, 0x00, 0x00), (0x00, 0x00, 0xaa), (0x00, 0xaa, 0x00), (0x00, 0xaa, 0xaa),
    (0xaa, 0x00, 0x00), (0xaa, 0x00, 0xaa), (0xaa, 0xaa, 0x00), (0xaa, 0xaa, 0xaa),
    (0x00, 0x00, 0x55), (0x00, 0x00, 0xff), (0x00, 0xaa, 0x55), (0x00, 0xaa, 0xff),
    (0xaa, 0x00, 0x55), (0xaa, 0x00, 0xff), (0xaa, 0xaa, 0x55), (0xaa, 0xaa, 0xff),
    (0x00, 0x55, 0x00), (0x00, 0x55, 0xaa), (0x00, 0xff, 0x00), (0x00, 0xff, 0xaa),
    (0xaa, 0x55, 0x00), (0xaa, 0x55, 0xaa), (0xaa, 0xff, 0x00), (0xaa, 0xff, 0xaa),
    (0x00, 0x55, 0x55), (0x00, 0x55, 0xff), (0x00, 0xff, 0x55), (0x00, 0xff, 0xff),
    (0xaa, 0x55, 0x55), (0xaa, 0x55, 0xff), (0xaa, 0xff, 0x55), (0xaa, 0xff, 0xff),
    (0x55, 0x00, 0x00), (0x55, 0x00, 0xaa), (0x55, 0xaa, 0x00), (0x55, 0xaa, 0xaa),
    (0xff, 0x00, 0x00), (0xff, 0x00, 0xaa), (0xff, 0xaa, 0x00), (0xff, 0xaa, 0xaa),
    (0x55, 0x00, 0x55), (0x55, 0x00, 0xff), (0x55, 0xaa, 0x55), (0x55, 0xaa, 0xff),
    (0xff, 0x00, 0x55), (0xff, 0x00, 0xff), (0xff, 0xaa, 0x55), (0xff, 0xaa, 0xff),
    (0x55, 0x55, 0x00), (0x55, 0x55, 0xaa), (0x55, 0xff, 0x00), (0x55, 0xff, 0xaa),
    (0xff, 0x55, 0x00), (0xff, 0x55, 0xaa), (0xff, 0xff, 0x00), (0xff, 0xff, 0xaa),
    (0x55, 0x55, 0x55), (0x55, 0x55, 0xff), (0x55, 0xff, 0x55), (0x55, 0xff, 0xff),
    (0xff, 0x55, 0x55), (0xff, 0x55, 0xff), (0xff, 0xff, 0x55), (0xff, 0xff, 0xff)
)

# composite palettes
# see http://nerdlypleasures.blogspot.co.uk/2013_11_01_archive.html
COMPOSITE = {
    'cga_old': (
        (0x00, 0x00, 0x00), (0x00, 0x71, 0x00), (0x00, 0x3f, 0xff), (0x00, 0xab, 0xff),
        (0xc3, 0x00, 0x67), (0x73, 0x73, 0x73), (0xe6, 0x39, 0xff), (0x8c, 0xa8, 0xff),
        (0x53, 0x44, 0x00), (0x00, 0xcd, 0x00), (0x73, 0x73, 0x73), (0x00, 0xfc, 0x7e),
        (0xff, 0x39, 0x00), (0xe2, 0xca, 0x00), (0xff, 0x7c, 0xf4), (0xff, 0xff, 0xff)
    ),
    'cga': (
        (0x00, 0x00, 0x00), (0x00, 0x6a, 0x2c), (0x00, 0x39, 0xff), (0x00, 0x94, 0xff),
        (0xca, 0x00, 0x2c), (0x77, 0x77, 0x77), (0xff, 0x31, 0xff), (0xc0, 0x98, 0xff),
        (0x1a, 0x57, 0x00), (0x00, 0xd6, 0x00), (0x77, 0x77, 0x77), (0x00, 0xf4, 0xb8),
        (0xff, 0x57, 0x00), (0xb0, 0xdd, 0x00), (0xff, 0x7c, 0xb8), (0xff, 0xff, 0xff)
    ),
    'tandy': (
        (0x00, 0x00, 0x00), (0x7c, 0x30, 0x00), (0x00, 0x75, 0x00), (0x00, 0xbe, 0x00),
        (0x00, 0x47, 0xee), (0x77, 0x77, 0x77), (0x00, 0xbb, 0xc4), (0x00, 0xfb, 0x3f),
        (0xb2, 0x0f, 0x9d), (0xff, 0x1e, 0x0f), (0x77, 0x77, 0x77), (0xff, 0xb8, 0x00),
        (0xb2, 0x44, 0xff), (0xff, 0x78, 0xff), (0x4b, 0xba, 0xff), (0xff, 0xff, 0xff)
    ),
    'pcjr': (
        (0x00, 0x00, 0x00), (0x98, 0x20, 0xcb), (0x9f, 0x1c, 0x00), (0xff, 0x11, 0x71),
        (0x00, 0x76, 0x00), (0x77, 0x77, 0x77), (0x5b, 0xaa, 0x00), (0xff, 0xa5, 0x00),
        (0x00, 0x4e, 0xcb), (0x74, 0x53, 0xff), (0x77, 0x77, 0x77), (0xff, 0x79, 0xff),
        (0x00, 0xc8, 0x71), (0x00, 0xcc, 0xff), (0x00, 0xfa, 0x00), (0xff, 0xff, 0xff)
    )
}


###############################################################################
# monochrome coloursets and default palettes

MONO_TINT = {
    'green': (0, 255, 0),
    'amber': (255, 128, 0),
    'grey': (255, 255, 255),
    'mono': (0, 255, 0),
}

# CGA mono intensities
INTENSITY16 = range(0x00, 0x100, 0x11)
# MDA text intensities: black, dark green, green, bright green
INTENSITY_MDA_MONO = (0x00, 0x40, 0xc0, 0xff)
# SCREEN 10 intensities
INTENSITY_EGA_MONO = (0x00, 0xaa, 0xff)

# monochrome EGA, these refer to the fixed pseudocolor palette defined in EGAMonoMode
# from GW-BASIC manual:
# Attribute Value	Displayed Pseudo-Color
# 0	Off
# 1	On, normal intensity
# 2	Blink
# 3	On, high intensity
EGA_MONO_PALETTE = (0, 4, 1, 8)


# ignored, remove after refactoring
NONE_PALETTE = None
# this is actually ignored, see MonoTextMode class
# remove after refactoring
MDA_PALETTE = (0,) * 16


###############################################################################
# Low level video (mainly about colours; mode object factory)

class Video(object):
    """Low-level display operations."""

    def __init__(self, capabilities, monitor, low_intensity, aspect, video_mem_size):
        """Initialise colour sets."""
        # public members - used by VideoMode
        # video adapter type - cga, ega, etc
        if capabilities == 'ega' and monitor in MONO_TINT:
            capabilities = 'ega_mono'
        self.capabilities = capabilities
        # screen aspect ratio, for CIRCLE
        self.aspect = aspect
        # colourset preparations
        # monochrome tint in rgb
        self.mono_tint = MONO_TINT.get(monitor, MONO_TINT['green'])
        # emulated monitor type - rgb, composite, mono
        self.monitor = 'mono' if monitor in MONO_TINT else monitor
        # build 16-greyscale and 16-colour sets
        self.colours16_mono = tuple(
            tuple(tint*i//255 for tint in self.mono_tint) for i in INTENSITY16
        )
        # NTSC colorburst settings
        if monitor == 'mono':
            self.colours16 = list(self.colours16_mono)
        else:
            self.colours16 = list(COLOURS16)
        # set up text_data and mode_data
        self.prepare_modes(video_mem_size)

    def get_mode(self, number, width=None):
        """Retrieve graphical mode by screen number."""
        try:
            if number:
                return self._mode_data[number]
            else:
                return self._text_data[width]
        except KeyError:
            # no such mode
            raise error.BASICError(error.IFC)

    def get_allowed_widths(self):
        """Get allowed screen widths."""
        return set(
            mode.width for mode in list(self._text_data.values()) + list(self._mode_data.values())
        )

    # colourset changes


    # FIXME - move to colourmappers
    def toggle_colour(self, has_colour):
        """Toggle between colour and monochrome (for NTSC colorburst)."""
        # note that colours16 member is only used in certain mode/adapter combinations
        # e.g. in text mode it's only used for 'cga', 'cga_old', 'pcjr', 'tandy'
        if has_colour:
            self.colours16[:] = COLOURS16
        else:
            self.colours16[:] = self.colours16_mono

    # FIXME - move to colourmappers
    def set_colorburst(self, on, is_cga):
        """Set the NTSC colorburst bit."""
        # On a composite monitor with CGA adapter (not EGA, VGA):
        # - on SCREEN 2 this enables artifacting
        # - on SCREEN 1 and 0 this switches between colour and greyscale
        # On an RGB monitor:
        # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
        # - ignored on other screens
        colorburst_capable = self.capabilities in ('cga', 'cga_old', 'tandy', 'pcjr')
        if is_cga and self.monitor != 'composite':
            # ega ignores colorburst; tandy and pcjr have no mode 5
            self.cga_mode_5 = not on
            # FIXME - this is in colourmapper now
            #self.set_cga4_palette(1)
        else:
            self.toggle_colour(self.monitor != 'mono' and (on or self.monitor != 'composite'))
        return on and colorburst_capable



    ###########################################################################
    # video modes

    def prepare_modes(self, video_mem_size):
        """Build lists of allowed graphics modes."""
        video_mem_size = int(video_mem_size)
        # initialise tinted monochrome palettes
        colours_ega_mono = tuple(
            tuple(tint*i//255 for tint in self.mono_tint) for i in INTENSITY_EGA_MONO
        )
        colours_mda_mono = tuple(
            tuple(tint*i//255 for tint in self.mono_tint) for i in INTENSITY_MDA_MONO
        )
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
            '320x200x4': CGA4Mode(
                '320x200x4', 320, 200, 25, 40, 3,
                NONE_PALETTE, self.colours16, bitsperpixel=2,
                interleave_times=2, bank_size=0x2000,
                aspect=self.aspect,
                num_pages=(
                    video_mem_size // (2*0x2000)
                    if self.capabilities in ('pcjr', 'tandy')
                    else 1
                )
            ),
            # 06h 640x200x2  16384B 1bpp 0xb8000    screen 2
            '640x200x2': CGAMode(
                '640x200x2', 640, 200, 25, 80, 1,
                CGA2_PALETTE, self.colours16, bitsperpixel=1,
                interleave_times=2, bank_size=0x2000, num_pages=1,
                aspect=self.aspect,
                supports_artifacts=True
            ),
            # 08h 160x200x16 16384B 4bpp 0xb8000    PCjr/Tandy screen 3
            '160x200x16': CGAMode(
                '160x200x16', 160, 200, 25, 20, 15,
                CGA16_PALETTE, self.colours16, bitsperpixel=4,
                interleave_times=2, bank_size=0x2000,
                num_pages=video_mem_size//(2*0x2000),
                pixel_aspect=(1968, 1000), cursor_index=3
            ),
            #     320x200x4  16384B 2bpp 0xb8000   Tandy/PCjr screen 4
            '320x200x4pcjr': CGA4Mode(
                '320x200x4pcjr', 320, 200, 25, 40, 3,
                NONE_PALETTE, self.colours16, bitsperpixel=2,
                interleave_times=2, bank_size=0x2000,
                num_pages=video_mem_size//(2*0x2000),
                aspect=self.aspect,
                cursor_index=3
            ),
            # 09h 320x200x16 32768B 4bpp 0xb8000    Tandy/PCjr screen 5
            '320x200x16pcjr': CGAMode(
                '320x200x16pcjr', 320, 200, 25, 40, 15,
                CGA16_PALETTE, self.colours16, bitsperpixel=4,
                interleave_times=4, bank_size=0x2000,
                num_pages=video_mem_size//(4*0x2000),
                aspect=self.aspect,
                cursor_index=3
            ),
            # 0Ah 640x200x4  32768B 2bpp 0xb8000   Tandy/PCjr screen 6
            '640x200x4': Tandy6Mode(
                '640x200x4', 640, 200, 25, 80, 3,
                NONE_PALETTE, self.colours16, bitsperpixel=2,
                interleave_times=4, bank_size=0x2000,
                num_pages=video_mem_size//(4*0x2000),
                aspect=self.aspect,
                cursor_index=3
            ),
            # 0Dh 320x200x16 32768B 4bpp 0xa0000    EGA screen 7
            '320x200x16': EGAMode(
                '320x200x16', 320, 200, 25, 40, 15,
                CGA16_PALETTE, self.colours16, bitsperpixel=4,
                num_pages=video_mem_size//(4*0x2000),
                aspect=self.aspect,
                interleave_times=1, bank_size=0x2000
            ),
            # 0Eh 640x200x16    EGA screen 8
            '640x200x16': EGAMode(
                '640x200x16', 640, 200, 25, 80, 15,
                CGA16_PALETTE, self.colours16, bitsperpixel=4,
                num_pages=video_mem_size//(4*0x4000),
                aspect=self.aspect,
                interleave_times=1, bank_size=0x4000
            ),
            # 10h 640x350x16    EGA screen 9
            '640x350x16': EGAMode(
                '640x350x16', 640, 350, 25, 80, 15,
                EGA_PALETTE, COLOURS64, bitsperpixel=4,
                num_pages=video_mem_size//(4*0x8000),
                aspect=self.aspect,
                interleave_times=1, bank_size=0x8000
            ),
            # 0Fh 640x350x4     EGA monochrome screen 10
            '640x350x4': EGAMonoMode(
                '640x350x16', 640, 350, 25, 80, 1,
                EGA_MONO_PALETTE, colours_ega_mono, bitsperpixel=2,
                interleave_times=1, bank_size=0x8000,
                num_pages=video_mem_size//(2*0x8000),
                aspect=self.aspect,
                has_blink=True,
                planes_used=(1, 3)
            ),
            # 40h 640x400x2   1bpp  olivetti screen 3
            '640x400x2': CGAMode(
                '640x400x2', 640, 400, 25, 80, 1,
                CGA2_PALETTE, self.colours16, bitsperpixel=1,
                interleave_times=4, bank_size=0x2000,
                num_pages=1,
                aspect=self.aspect,
                has_blink=True
            ),
            # hercules screen 3
            '720x348x2': CGAMode(
                # this actually produces 350, not 348
                '720x348x2', 720, 350, 25, 80, 1,
                CGA2_PALETTE, self.colours16_mono, bitsperpixel=1,
                interleave_times=4, bank_size=0x2000,
                num_pages=2,
                aspect=self.aspect,
                has_blink=True
            ),
        }
        if self.capabilities == 'vga':
            # technically, VGA text does have underline
            # but it's set to an invisible scanline
            # so not, so long as we're not allowing to set the scanline
            self._text_data = {
                40: TextMode('vgatext40', 25, 40, 16, 9, 7, EGA_PALETTE, COLOURS64, num_pages=8),
                80: TextMode('vgatext80', 25, 80, 16, 9, 7, EGA_PALETTE, COLOURS64, num_pages=4)
            }
            self._mode_data = {
                1: graphics_mode['320x200x4'],
                2: graphics_mode['640x200x2'],
                7: graphics_mode['320x200x16'],
                8: graphics_mode['640x200x16'],
                9: graphics_mode['640x350x16']
            }
        elif self.capabilities == 'ega':
            self._text_data = {
                40: TextMode('egatext40', 25, 40, 14, 8, 7, EGA_PALETTE, COLOURS64, num_pages=8),
                80: TextMode('egatext80', 25, 80, 14, 8, 7, EGA_PALETTE, COLOURS64, num_pages=4)
            }
            self._mode_data = {
                1: graphics_mode['320x200x4'],
                2: graphics_mode['640x200x2'],
                7: graphics_mode['320x200x16'],
                8: graphics_mode['640x200x16'],
                9: graphics_mode['640x350x16']
            }
        elif self.capabilities == 'ega_mono':
            self._text_data = {
                40: MonoTextMode(
                    'ega_monotext40', 25, 40, 14, 8, 7,
                    MDA_PALETTE, colours_mda_mono, is_mono=True, num_pages=8
                ),
                80: MonoTextMode(
                    'ega_monotext80', 25, 80, 14, 8, 7,
                    MDA_PALETTE, colours_mda_mono, is_mono=True, num_pages=4
                )
            }
            self._mode_data = {
                10: graphics_mode['640x350x4']
            }
        elif self.capabilities == 'mda':
            self._text_data = {
                40: MonoTextMode(
                    'mdatext40', 25, 40, 14, 9, 7,
                    MDA_PALETTE, colours_mda_mono, is_mono=True, num_pages=1
                ),
                80: MonoTextMode(
                    'mdatext80', 25, 80, 14, 9, 7,
                    MDA_PALETTE, colours_mda_mono, is_mono=True, num_pages=1
                )
            }
            self._mode_data = {}
        elif self.capabilities in ('cga', 'cga_old', 'pcjr', 'tandy'):
            if self.capabilities == 'tandy':
                self._text_data = {
                    40: TextMode(
                        'tandytext40', 25, 40, 9, 8, 7, CGA16_PALETTE, self.colours16, num_pages=8
                    ),
                    80: TextMode(
                        'tandytext80', 25, 80, 9, 8, 7, CGA16_PALETTE, self.colours16, num_pages=4
                    )
                }
            else:
                self._text_data = {
                    40: TextMode(
                        'cgatext40', 25, 40, 8, 8, 7,
                        CGA16_PALETTE, self.colours16, num_pages=8
                    ),
                    80: TextMode(
                        'cgatext80', 25, 80, 8, 8, 7,
                        CGA16_PALETTE, self.colours16, num_pages=4
                    )
                }
            if self.capabilities in ('cga', 'cga_old'):
                self._mode_data = {
                    1: graphics_mode['320x200x4'],
                    2: graphics_mode['640x200x2']
                }
            else:
                self._mode_data = {
                    1: graphics_mode['320x200x4'],
                    2: graphics_mode['640x200x2'],
                    3: graphics_mode['160x200x16'],
                    4: graphics_mode['320x200x4pcjr'],
                    5: graphics_mode['320x200x16pcjr'],
                    6: graphics_mode['640x200x4']
                }
        elif self.capabilities == 'hercules':
            # herc attributes shld distinguish black, dim, normal, bright
            # see http://www.seasip.info/VintagePC/hercplus.html
            self._text_data = {
                40: MonoTextMode(
                    'herculestext40', 25, 40, 14, 9, 7,
                    MDA_PALETTE, colours_mda_mono, is_mono=True, num_pages=2
                ),
                80: MonoTextMode(
                    'herculestext80', 25, 80, 14, 9, 7,
                    MDA_PALETTE, colours_mda_mono, is_mono=True, num_pages=2
                )
            }
            self._mode_data = {
                3: graphics_mode['720x348x2']
            }
        elif self.capabilities == 'olivetti':
            self._text_data = {
                40: TextMode(
                    'olivettitext40', 25, 40, 16, 8, 7, CGA16_PALETTE, self.colours16, num_pages=8
                ),
                80: TextMode(
                    'olivettitext80', 25, 80, 16, 8, 7, CGA16_PALETTE, self.colours16, num_pages=4
                )
            }
            self._mode_data = {
                1: graphics_mode['320x200x4'],
                2: graphics_mode['640x200x2'],
                3: graphics_mode['640x400x2']
            }
            # on Olivetti M24, all numbers 3-255 give the same altissima risoluzione
            for mode in range(4, 256):
                self._mode_data[mode] = graphics_mode['640x400x2']



##############################################################################
# palettes & coloursets

class ColourMapper(object):
    """Palette and colourset."""

    def __init__(self, palette, colours, has_blink, num_attr):
        """Initialise colour mapper."""
        # palette - maps the valid attributes to colour values
        # these are "palette attributes" - e.g. the 16 foreground attributes for text mode.
        self._default_palette = palette
        # number of true attribute bytes. This is 256 for text modes.
        self.num_attr = num_attr
        # colour set - maps the valid colour values to RGB
        # can be used as the right hand side of a palette assignment
        # colours is a reference (changes with colorburst on composite)
        self._colours = colours
        # this mode has blinking attributes
        self.has_blink = has_blink

    @property
    def default_palette(self):
        """Default palette."""
        return self._default_palette

    @property
    def num_palette(self):
        """Number of values in palette."""
        return len(self._default_palette)

    @property
    def num_colours(self):
        """Number of colour values."""
        return len(self._colours)

    def split_attr(self, attr):
        """Split textmode attribute byte into constituent parts."""
        # 7  6 5 4  3 2 1 0
        # Bl b b b  f f f f
        back = (attr >> 4) & 7
        blink = (attr >> 7) == 1
        fore = attr & 0xf
        underline = False
        return fore, back, blink, underline

    def join_attr(self, fore, back, blink, underline):
        """Join constituent parts into textmode attribute byte."""
        return ((blink & 1) << 7) + ((back & 7) << 4) + (fore & 0xf)

    def attr_to_rgb(self, attr, palette):
        """Convert colour attribute to RGB/blink/underline, given a palette."""
        fore, back, blink, underline = self.split_attr(attr)
        fore_rgb = self._colours[palette[fore]]
        back_rgb = self._colours[palette[back]]
        return fore_rgb, back_rgb, blink, underline

    def get_cga4_palette(self):
        """CGA palette setting (accessible from memory)."""
        return 1

    def set_cga4_palette(self, num):
        """Set the default 4-colour CGA palette."""


class CGA4ColourMapper(ColourMapper):
    """CGA 4-colour palettes."""

    def __init__(self, palette, colours, has_blink, num_attr):
        """Initialise colour mapper."""
        ColourMapper.__init__(self, palette, colours, has_blink, num_attr)
        self._tandy = False
        self._low_intensity = False
        self._has_mode_5 = True
        self._palette_number = 1
        self._mode_5 = False

    #FIXME - not being called
    def set_defaults(capabilities, low_intensity):
        """CGA 4-colour palette / mode 5 settings"""
        self._tandy = capabilities not in ('pcjr', 'tandy')
        # pcjr does not have mode 5
        self._has_mode_5 = capabilities in ('cga', 'cga_old')
        self._low_intensity = low_intensity
        # start with the cyan-magenta-white palette
        self._palette_number = 1
        self._mode_5 = False

    def get_cga4_palette(self):
        """CGA palette setting (accessible from memory)."""
        return self._palette_number

    def set_cga4_palette(self, num):
        """Set the default 4-colour CGA palette."""
        self._palette_number = num % 2

    @property
    def default_palette(self):
        """Default palette."""
        if self._tandy:
            if self._palette_number:
                return TANDY4_PALETTE_1
            else:
                return TANDY4_PALETTE_0
        elif self._mode_5 and self._has_mode_5:
            if self._low_intensity:
                return CGA4_LO_PALETTE_RED
            else:
                return CGA4_HI_PALETTE_RED
        elif self._low_intensity:
            if self._palette_number:
                return CGA4_LO_PALETTE_1
            else:
                return CGA4_LO_PALETTE_0
        else:
            if self._palette_number:
                return CGA4_HI_PALETTE_1
            else:
                return CGA4_HI_PALETTE_0


class MonoTextColourMapper(ColourMapper):
    """Attribute mapper for MDA-style text mode with underlining."""

    # MDA text attributes: http://www.seasip.info/VintagePC/mda.html
    # The attribute bytes mostly behave like a bitmap:
    #
    # Bit 1: Underline.
    # Bit 3: High intensity.
    # Bit 7: Blink
    # but there are eight exceptions:
    #
    # Attributes 00h, 08h, 80h and 88h display as black space.
    # Attribute 70h displays as black on green.
    # Attribute 78h displays as dark green on green. In fact, depending on timing and on the design of the monitor, it may have a bright green 'halo' where the dark green and bright green bits meet.
    # Attribute F0h displays as a blinking version of 70h (if blinking is enabled); as black on bright green otherwise.
    # Attribute F8h displays as a blinking version of 78h (if blinking is enabled); as dark green on bright green otherwise.

    # see also http://support.microsoft.com/KB/35148
    # --> archived on https://github.com/jeffpar/kbarchive/tree/master/kb/035/Q35148

    # https://www.pcjs.org/pubs/pc/reference/microsoft/kb/Q44412/

    # this should agree with palettes for EGA mono for COLOR values, see:
    # http://qbhlp.uebergeord.net/screen-statement-details-colors.html

    # EGA mono attributes are actually different on the intermediate, non-standard byte attributes
    # see https://nerdlypleasures.blogspot.com/2014/03/the-monochrome-experience-cga-ega-and.html
    # and http://www.vcfed.org/forum/showthread.php?50674-EGA-Monochrome-Compatibility

    @property
    def num_palette(self):
        """Number of foreground attributes is the same as in colour text modes."""
        return 16

    def split_attr(self, attr):
        """Split attribute byte into constituent parts."""
        underline = (attr % 8) == 1
        blink = (attr & 0x80) != 0
        # background is almost always black
        back = 0
        # intensity set by bit 3
        fore = 2 if not (attr & 0x8) else 3
        # exceptions
        if attr in (0x00, 0x08, 0x80, 0x88):
            fore, back = 0, 0
        elif attr in (0x70, 0xf0):
            fore, back = 0, 2
        elif attr in (0x78, 0xf8):
            fore, back = 1, 3
        return fore, back, blink, underline

    def attr_to_rgb(self, attr, dummy_palette):
        """Convert colour attribute to RGB/blink/underline, given a palette."""
        fore, back, blink, underline = self.split_attr(attr)
        # palette is ignored
        fore_rgb = self._colours[fore]
        back_rgb = self._colours[back]
        return fore_rgb, back_rgb, blink, underline


class EGAMonoColourMapper(ColourMapper):
    """Colour mapper for EGA monochrome graphics mode (mode 10)."""

    # from GW-BASIC manual:
    # Color Value	Displayed Pseudo-Color
    # 0	Off
    # 1	Blink, off to on
    # 2	Blink, off to high intensity
    # 3	Blink, on to off
    # 4	On
    # 5	Blink, on to high intensity
    # 6	Blink, high intensity to off
    # 7	Blink, high intensity to on
    # 8	High intensity

    # fore, back intensities. blink is from fore to back
    _pseudocolours = (
        (0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)
    )

    @property
    def num_colours(self):
        """Number of colour values."""
        return len(self._pseudocolours)

    def attr_to_rgb(self, attr, palette):
        """Convert colour attribute to RGB/blink/underline, given a palette."""
        fore, back = self._pseudocolours[palette[attr] % len(self._pseudocolours)]
        # intensity 0, 1, 2 to RGB; apply mono tint
        fore_rgb = self._colours[fore]
        back_rgb = self._colours[back]
        # fore, back, blink, underline
        return fore_rgb, back_rgb, fore != back, False


##############################################################################
# sprites & tiles

class PackedTileBuilder(object):
    """Packed-pixel (CGA) tiles."""

    def __init__(self, bits_per_pixel):
        """Initialise tile builder."""
        self._bitsperpixel = bits_per_pixel

    def __call__(self, pattern):
        """Build a flood-fill tile for CGA screens."""
        # in modes 1, (2), 3, 4, 5, 6 colours are encoded in consecutive bits
        # each byte represents one scan line
        return bytematrix.ByteMatrix.frompacked(
            pattern, height=len(pattern), items_per_byte=8//self._bitsperpixel
        )


class PlanedTileBuilder(object):
    """Interlaced-plane (EGA) tiles."""

    def __init__(self, number_planes):
        """Initialise sprite builder."""
        # number of colour planes
        self._number_planes = number_planes

    def __call__(self, pattern):
        """Build a flood-fill tile."""
        # append nulls until we can cleanly partition into planes
        extra_chars = len(pattern) % self._number_planes
        if extra_chars:
            pattern.extend(bytearray(self._number_planes - extra_chars))
        # unpack bytes into pattern
        allplanes = bytematrix.ByteMatrix.frompacked(
            pattern, height=len(pattern), items_per_byte=8
        )
        planes = (
            allplanes[_plane::self._number_planes, :] << _plane
            for _plane in range(self._number_planes)
        )
        tile = functools.reduce(operator.__ior__, planes)
        return tile


class PackedSpriteBuilder(object):
    """Packed-pixel (CGA) sprite builder."""

    def __init__(self, bits_per_pixel):
        self._bitsperpixel = bits_per_pixel

    def pack(self, sprite):
        """Pack the sprite into bytearray."""
        # sprite size record
        size_record = struct.pack('<HH', sprite.width * self._bitsperpixel, sprite.height)
        # interval_to_bytes
        packed = sprite.packed(items_per_byte=8 // self._bitsperpixel)
        return size_record + packed

    def unpack(self, array):
        """Unpack bytearray into sprite."""
        row_bits, height = struct.unpack('<HH', array[0:4])
        width = row_bits // self._bitsperpixel
        row_bytes = (width * self._bitsperpixel + 7) // 8
        byte_size = row_bytes * height
        # bytes_to_interval
        packed = array[4:4+byte_size]
        # ensure iterations over memoryview yield int, not bytes, in Python 2
        # frompacked can't take interators, would need a width argument
        #packed = iterbytes(packed)
        if PY2:
            packed = bytearray(packed)
        sprite = bytematrix.ByteMatrix.frompacked(
            packed, height, items_per_byte=8 // self._bitsperpixel
        )
        return sprite


class PlanedSpriteBuilder(object):
    """Sprite builder with interlaced colour planes (EGA sprites)."""

    # ** byte mapping for sprites in EGA modes
    # sprites have 8 pixels per byte
    # with colour planes in consecutive rows
    # each new row is aligned on a new byte

    def __init__(self, number_planes):
        """Initialise sprite builder."""
        # number of colour planes
        self._number_planes = number_planes

    def pack(self, sprite):
        """Pack the sprite into bytearray."""
        # extract colour planes
        # note that to get the plane this should be bit-masked - (s >> _p) & 1
        # but bytematrix.packbytes will do this for us
        sprite_planes = (
            (sprite >> _plane)  # & 1
            for _plane in range(self._number_planes)
        )
        # pack the bits into bytes
        #interval_to_bytes
        packed_planes = list(
            _sprite.packed(items_per_byte=8)
            for _sprite in sprite_planes
        )
        # interlace row-by-row
        row_bytes = (sprite.width + 7) // 8
        length = sprite.height * self._number_planes * row_bytes
        interlaced = bytearray().join(
            _packed[_row_offs : _row_offs+row_bytes]
            for _row_offs in range(0, length, row_bytes)
            for _packed in packed_planes
        )
        size_record = struct.pack('<HH', sprite.width, sprite.height)
        return size_record + interlaced

    def unpack(self, array):
        """Build sprite from bytearray in EGA modes."""
        width, height = struct.unpack('<HH', array[0:4])
        row_bytes = (width + 7) // 8
        packed = array[4:4+row_bytes]
        # ensure iterations over memoryview yield int, not bytes, in Python 2
        packed = iterbytes(packed)
        # unpack all planes
        #bytes_to_interval
        allplanes = bytematrix.ByteMatrix.frompacked(
            packed, height=height*self._number_planes, items_per_byte=8
        )
        # de-interlace planes
        sprite_planes = (
            allplanes[_plane::height, :] << _plane
            for _plane in range(self._number_planes)
        )
        # combine planes
        sprite = functools.reduce(operator.__ior__, sprite_planes)
        return sprite


##############################################################################
# video mode base class

class VideoMode(object):
    """Base class for video modes."""

    _colourmapper = ColourMapper

    def __init__(
                self, name, height, width,
                font_height, font_width,
                attr, palette, colours,
                num_pages, has_blink,
                video_segment, page_size,
                num_attr
            ):
        """Initialise video mode settings."""
        self.is_text_mode = False
        self.name = name
        self.height = int(height)
        self.width = int(width)
        self.font_height = int(font_height)
        self.font_width = int(font_width)
        self.pixel_height = self.height*self.font_height
        self.pixel_width = self.width*self.font_width
        self.attr = int(attr)
        self.video_segment = int(video_segment)
        self.page_size = int(page_size)
        self.num_pages = int(num_pages) # or video_mem_size // self.page_size)
        self.colourmap = self._colourmapper(palette, colours, has_blink, num_attr)

    def pixel_to_text_pos(self, x, y):
        """Convert pixel position to text position."""
        return 1 + y // self.font_height, 1 + x // self.font_width

    def pixel_to_text_area(self, x0, y0, x1, y1):
        """Convert from pixel area to text area."""
        col0 = min(self.width, max(1, 1 + x0 // self.font_width))
        row0 = min(self.height, max(1, 1 + y0 // self.font_height))
        col1 = min(self.width, max(1, 1 + x1 // self.font_width))
        row1 = min(self.height, max(1, 1 + y1 // self.font_height))
        return row0, col0, row1, col1

    def text_to_pixel_pos(self, row, col):
        """Convert text position to pixel position."""
        # area bounds are all inclusive
        return (
            (col-1) * self.font_width, (row-1) * self.font_height,
        )

    def text_to_pixel_area(self, row0, col0, row1, col1):
        """Convert text area to pixel area."""
        # area bounds are all inclusive
        return (
            (col0-1) * self.font_width, (row0-1) * self.font_height,
            (col1-col0+1) * self.font_width-1, (row1-row0+1) * self.font_height-1
        )

    def get_all_memory(self, screen):
        """Obtain a copy of all video memory."""
        return self.get_memory(screen, self.video_segment*0x10, self.page_size*self.num_pages)

    def set_all_memory(self, screen, mem_copy):
        """Restore a copy of all video memory."""
        return self.set_memory(screen, self.video_segment*0x10, mem_copy)

    def get_memory(self, screen, addr, num_bytes):
        """Retrieve bytes from video memory, stub."""

    def set_memory(self, screen, addr, bytes):
        """Set bytes in video memory, stub."""


##############################################################################
# text modes

class TextMode(VideoMode):
    """Default settings for a text mode."""

    def __init__(
            self, name, height, width,
            font_height, font_width, attr, palette, colours,
            num_pages, is_mono=False, has_blink=True
        ):
        """Initialise video mode settings."""
        video_segment = 0xb000 if is_mono else 0xb800
        page_size = 0x1000 if width == 80 else 0x800
        num_attr = 256
        VideoMode.__init__(
            self, name, height, width,
            font_height, font_width, attr, palette, colours,
            num_pages, has_blink, video_segment, page_size, num_attr
        )
        self.is_text_mode = True

    def get_memory(self, screen, addr, num_bytes):
        """Retrieve bytes from textmode video memory."""
        addr -= self.video_segment*0x10
        mem_bytes = bytearray(num_bytes)
        for i in xrange(num_bytes):
            page = (addr+i) // self.page_size
            offset = (addr+i) % self.page_size
            ccol = 1 + (offset % (self.width*2)) // 2
            crow = 1 + offset // (self.width*2)
            try:
                if (addr+i) % 2:
                    mem_bytes[i] = screen.text_screen.text.get_attr(page, crow, ccol)
                else:
                    mem_bytes[i] = screen.text_screen.text.get_char(page, crow, ccol)
            except IndexError:
                pass
        return mem_bytes

    def set_memory(self, screen, addr, mem_bytes):
        """Set bytes in textmode video memory."""
        addr -= self.video_segment*0x10
        last_row = 0
        for i in xrange(len(mem_bytes)):
            page = (addr+i) // self.page_size
            offset = (addr+i) % self.page_size
            ccol = 1 + (offset % (self.width*2)) // 2
            crow = 1 + offset // (self.width*2)
            try:
                if (addr+i) % 2:
                    c = screen.text_screen.text.get_char(page, crow, ccol)
                    a = mem_bytes[i]
                else:
                    c = mem_bytes[i]
                    a = screen.text_screen.text.get_attr(page, crow, ccol)
                screen.text_screen.text.put_char_attr(page, crow, ccol, int2byte(c), a)
                if last_row > 0 and last_row != crow:
                    screen.text_screen.refresh_range(page, last_row, 1, self.width)
            except IndexError:
                pass
            last_row = crow
        if last_row >= 1 and last_row <= self.height and page >= 0 and page < self.num_pages:
            screen.text_screen.refresh_range(page, last_row, 1, self.width)


class MonoTextMode(TextMode):
    """MDA-style text mode with underlining."""

    _colourmapper = MonoTextColourMapper


##############################################################################
# graphics modes

class GraphicsMode(VideoMode):
    """Default settings for a graphics mode."""

    # override these
    _tile_builder = lambda _: None
    _sprite_builder = lambda _: None

    def __init__(
            self, name, pixel_width, pixel_height,
            text_height, text_width,
            attr, palette, colours, bitsperpixel,
            interleave_times, bank_size,
            num_pages=None,
            has_blink=False,
            supports_artifacts=False,
            cursor_index=None,
            pixel_aspect=None, aspect=None,
            video_segment=0xb800,
        ):
        """Initialise video mode settings."""
        font_width = int(pixel_width // text_width)
        font_height = int(pixel_height // text_height)
        self.interleave_times = int(interleave_times)
        # cga bank_size = 0x2000 interleave_times=2
        self.bank_size = int(bank_size)
        page_size = self.interleave_times * self.bank_size
        num_attr = 2**bitsperpixel
        VideoMode.__init__(
            self, name, text_height, text_width,
            font_height, font_width, attr, palette, colours,
            num_pages, has_blink, video_segment, page_size, num_attr
        )
        self.is_text_mode = False
        self.bitsperpixel = int(bitsperpixel)
        # number of pixels referenced in each byte of a plane
        self.ppb = 8 // self.bitsperpixel
        self.bytes_per_row = int(pixel_width) * self.bitsperpixel // 8
        self.supports_artifacts = supports_artifacts
        self.cursor_index = cursor_index
        if pixel_aspect:
            self.pixel_aspect = pixel_aspect
        else:
            self.pixel_aspect = (self.pixel_height * aspect[0], self.pixel_width * aspect[1])
        # sprite and tile builders
        self.build_tile = self._tile_builder(self.bitsperpixel)
        self.sprite_builder = self._sprite_builder(self.bitsperpixel)

    def get_coords(self, addr):
        """Get video page and coordinates for address."""
        # override
        return 0, 0, 0

    def coord_ok(self, page, x, y):
        """Check if a page and coordinates are within limits."""
        return (
            page >= 0 and page < self.num_pages and
            x >= 0 and x < self.pixel_width and
            y >= 0 and y < self.pixel_height
        )

    def cutoff_coord(self, x, y):
        """Ensure coordinates are within screen + 1 pixel."""
        return min(self.pixel_width, max(-1, x)), min(self.pixel_height, max(-1, y))

    def set_plane(self, plane):
        """Set the current colour plane (EGA only)."""
        pass

    def set_plane_mask(self, mask):
        """Set the current colour plane mask (EGA only)."""
        pass

    def walk_memory(self, addr, num_bytes, factor=1):
        """Iterate over graphical memory (pixel-by-pixel, contiguous rows)."""
        # factor supports tandy-6 mode, which has 8 pixels per 2 bytes
        # with alternating planes in even and odd bytes (i.e. ppb==8)
        ppb = factor * self.ppb
        page_size = self.page_size//factor
        bank_size = self.bank_size//factor
        row_size = self.bytes_per_row//factor
        # first row
        page, x, y = self.get_coords(addr)
        offset = min(row_size - x//ppb, num_bytes)
        if self.coord_ok(page, x, y):
            yield page, x, y, 0, offset
        # full rows
        bank_offset, page_offset, start_y = 0, 0, y
        while page_offset + bank_offset + offset < num_bytes:
            y += self.interleave_times
            # not an integer number of rows in a bank
            if offset >= bank_size:
                bank_offset += bank_size
                start_y += 1
                offset, y = 0, start_y
                if bank_offset >= page_size:
                    page_offset += page_size
                    page += 1
                    bank_offset, offset = 0, 0
                    y, start_y = 0, 0
            if self.coord_ok(page, 0, y):
                ofs = page_offset + bank_offset + offset
                if ofs + row_size > num_bytes:
                    yield page, 0, y, ofs, num_bytes - ofs
                else:
                    yield page, 0, y, ofs, row_size
            offset += row_size


class CGAMode(GraphicsMode):
    """Default settings for a CGA graphics mode."""

    _tile_builder = PackedTileBuilder
    _sprite_builder = PackedSpriteBuilder

    def get_coords(self, addr):
        """Get video page and coordinates for address."""
        addr = int(addr) - self.video_segment * 0x10
        # modes 1-5: interleaved scan lines, pixels sequentially packed into bytes
        page, addr = addr//self.page_size, addr%self.page_size
        # 2 x interleaved scan lines of 80bytes
        bank, offset = addr//self.bank_size, addr%self.bank_size
        row, col = offset//self.bytes_per_row, offset%self.bytes_per_row
        x = col * 8 // self.bitsperpixel
        y = bank + self.interleave_times * row
        return page, x, y

    def set_memory(self, screen, addr, byte_array):
        """Set bytes in CGA memory."""
        for page, x, y, ofs, length in self.walk_memory(addr, len(byte_array)):
            #bytes_to_interval
            pixarray = bytematrix.ByteMatrix.frompacked(
                byte_array[ofs:ofs+length], height=1, items_per_byte=self.ppb
            )
            screen.drawing.put_interval(page, x, y, pixarray)

    def get_memory(self, screen, addr, num_bytes):
        """Retrieve bytes from CGA memory."""
        byte_array = bytearray(num_bytes)
        for page, x, y, ofs, length in self.walk_memory(addr, num_bytes):
            #interval_to_bytes
            pixarray = screen.pixels.pages[page].get_interval(x, y, length*self.ppb)
            byte_array[ofs:ofs+length] = pixarray.packed(self.ppb)
        return byte_array


class CGA4Mode(CGAMode):
    """Default settings for a CGA graphics mode."""

    _colourmapper = CGA4ColourMapper


class EGAMode(GraphicsMode):
    """Default settings for a EGA graphics mode."""

    _tile_builder = PlanedTileBuilder
    _sprite_builder = PlanedSpriteBuilder

    def __init__(
            self, name, pixel_width, pixel_height,
            text_height, text_width,
            attr, palette, colours, bitsperpixel,
            interleave_times, bank_size, num_pages,
            has_blink=False, planes_used=range(4),
            aspect=None
        ):
        """Initialise video mode settings."""
        GraphicsMode.__init__(
            self, name, pixel_width, pixel_height,
            text_height, text_width,
            attr, palette, colours, bitsperpixel,
            interleave_times, bank_size,
            num_pages, has_blink, aspect=aspect
        )
        # EGA uses colour planes, 1 bpp for each plane
        #self.ppb = 8
        self.bytes_per_row = pixel_width // 8
        self.video_segment = 0xa000
        self.planes_used = planes_used
        # additional colour plane mask
        self.master_plane_mask = sum([ 2**x for x in planes_used ])
        # current ega memory colour plane to read
        self.plane = 0
        # current ega memory colour planes to write to
        self.plane_mask = 0xff

    def set_plane(self, plane):
        """Set the current colour plane."""
        self.plane = plane

    def set_plane_mask(self, mask):
        """Set the current colour plane mask."""
        self.plane_mask = mask

    def get_coords(self, addr):
        """Get video page and coordinates for address."""
        addr = int(addr) - self.video_segment * 0x10
        # modes 7-9: 1 bit per pixel per colour plane
        page, addr = addr//self.page_size, addr%self.page_size
        x, y = (addr%self.bytes_per_row)*8, addr//self.bytes_per_row
        return page, x, y

    def get_memory(self, screen, addr, num_bytes):
        """Retrieve bytes from EGA memory."""
        plane = self.plane % (max(self.planes_used) + 1)
        byte_array = bytearray(num_bytes)
        if plane not in self.planes_used:
            return byte_array
        for page, x, y, ofs, length in self.walk_memory(addr, num_bytes):
            pixarray = screen.pixels.pages[page].get_interval(x, y, length*8)
            #byte_array[ofs:ofs+length] = interval_to_bytes(pixarray, self.ppb, plane)
            byte_array[ofs:ofs+length] = (pixarray >> plane).packed(8)
        return byte_array

    def set_memory(self, screen, addr, byte_array):
        """Set bytes in EGA video memory."""
        # EGA memory is planar with memory-mapped colour planes.
        # Within a plane, 8 pixels are encoded into each byte.
        # The colour plane is set through a port OUT and
        # determines which bit of each pixel's attribute is affected.
        mask = self.plane_mask & self.master_plane_mask
        # return immediately for unused colour planes
        if mask == 0:
            return
        for page, x, y, ofs, length in self.walk_memory(addr, len(byte_array)):
            #pixarray = bytes_to_interval(byte_array[ofs:ofs+length], self.ppb, mask)
            pixarray = (
                bytematrix.ByteMatrix.frompacked(
                    byte_array[ofs:ofs+length], height=1, items_per_byte=8
                ).render(0, mask)
            )
            screen.drawing.put_interval(page, x, y, pixarray, mask)


class EGAMonoMode(EGAMode):
    """Default settings for a EGA monochrome graphics mode (mode 10)."""

    _colourmapper = EGAMonoColourMapper


class Tandy6Mode(GraphicsMode):
    """Default settings for Tandy graphics mode 6."""

    _colourmapper = CGA4ColourMapper
    _tile_builder = PackedTileBuilder
    # initialising this with self.bitsperpixel should do the right thing
    _sprite_builder = PlanedSpriteBuilder

    def __init__(self, *args, **kwargs):
        """Initialise video mode settings."""
        GraphicsMode.__init__(self, *args, **kwargs)
        # mode 6: 4x interleaved scan lines, 8 pixels per two bytes,
        # low attribute bits stored in even bytes, high bits in odd bytes.
        self.bytes_per_row = self.pixel_width * 2 // 8
        self.video_segment = 0xb800

    def get_coords(self, addr):
        """Get video page and coordinates for address."""
        addr =  int(addr) - self.video_segment * 0x10
        page, addr = addr//self.page_size, addr%self.page_size
        # 4 x interleaved scan lines of 160bytes
        bank, offset = addr//self.bank_size, addr%self.bank_size
        row, col = offset//self.bytes_per_row, offset%self.bytes_per_row
        x = (col // 2) * 8
        y = bank + 4 * row
        return page, x, y

    def get_memory(self, screen, addr, num_bytes):
        """Retrieve bytes from Tandy 640x200x4 """
        # 8 pixels per 2 bytes
        # low attribute bits stored in even bytes, high bits in odd bytes.
        half_len = (num_bytes+1) // 2
        hbytes = bytearray(half_len), bytearray(half_len)
        for parity, byte_array in enumerate(hbytes):
            plane = parity ^ (addr % 2)
            for page, x, y, ofs, length in self.walk_memory(addr, num_bytes, 2):
                pixarray = screen.pixels.pages[page].get_interval(x, y, length * self.ppb * 2)
                #hbytes[parity][ofs:ofs+length] = interval_to_bytes(pixarray, self.ppb*2, plane)
                byte_array[ofs:ofs+length] = (pixarray >> plane).packed(self.ppb * 2)
        # resulting array may be too long by one byte, so cut to size
        return [_item for _pair in zip(*hbytes) for _item in _pair] [:num_bytes]

    def set_memory(self, screen, addr, byte_array):
        """Set bytes in Tandy 640x200x4 memory."""
        hbytes = byte_array[0::2], byte_array[1::2]
        # Tandy-6 encodes 8 pixels per byte, alternating colour planes.
        # I.e. even addresses are 'colour plane 0', odd ones are 'plane 1'
        for parity, half in enumerate(hbytes):
            plane = parity ^ (addr % 2)
            mask = 2 ** plane
            for page, x, y, ofs, length in self.walk_memory(addr, len(byte_array), 2):
                #pixarray = bytes_to_interval(hbytes[parity][ofs:ofs+length], 2*self.ppb, mask)
                pixarray = (
                    bytematrix.ByteMatrix.frompacked(
                        # what's the deal with the empty bytearrays here in some of the tests?
                        half[ofs:ofs+length], height=1, items_per_byte=2*self.ppb
                    ) << plane
                )
                screen.drawing.put_interval(page, x, y, pixarray, mask)
