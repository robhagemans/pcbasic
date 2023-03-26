"""
PC-BASIC - display.modes
Emulated video modes

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import error
from ..base import bytematrix
from .colours import CGA2ColourMapper, CGA4ColourMapper, CGA16ColourMapper
from .colours import EGA16ColourMapper, EGA64ColourMapper
from .colours import EGA4ColourMapper, Tandy4ColourMapper, Olivetti2ColourMapper
from .colours import EGA16TextColourMapper, EGA64TextColourMapper
from .colours import MonoTextColourMapper, EGAMonoColourMapper, HerculesColourMapper
from .framebuffer import TextMemoryMapper, GraphicsMemoryMapper
from .framebuffer import CGAMemoryMapper, EGAMemoryMapper, Tandy6MemoryMapper
from .framebuffer import PackedTileBuilder, PlanedTileBuilder
from .framebuffer import PackedSpriteBuilder, PlanedSpriteBuilder, Tandy6SpriteBuilder


##############################################################################
# SCREEN modes by number for each adapter

_MODES = {
    'cga': {
        (0, 40): 'cgatext40',
        (0, 80): 'cgatext80',
        1: '320x200x4',
        2: '640x200x2',
    },
    'ega': {
        (0, 40): 'egatext40',
        (0, 80): 'egatext80',
        1: '320x200x4',
        2: '640x200x2',
        7: '320x200x16',
        8: '640x200x16',
        9: '640x350x16',
    },
    'ega_64k': {
        (0, 40): 'egatext40',
        (0, 80): 'egatext80',
        1: '320x200x4',
        2: '640x200x2',
        7: '320x200x16',
        8: '640x200x16',
        # 64k EGA adapter only has a 4-attr @ 16-colour palette in SCREEN 9
        9: '640x350x4c',
    },
    'vga': {
        (0, 40): 'vgatext40',
        (0, 80): 'vgatext80',
        1: '320x200x4',
        2: '640x200x2',
        7: '320x200x16',
        8: '640x200x16',
        9: '640x350x16',
    },
    'mda': {
        (0, 40): 'mdatext40',
        (0, 80): 'mdatext80',
    },
    'ega_mono': {
        (0, 40): 'ega_monotext40',
        (0, 80): 'ega_monotext80',
        10: '640x350x4',
    },
    'hercules': {
        (0, 40): 'mdatext40',
        (0, 80): 'mdatext80',
        3: '720x348x2',
    },
    'tandy': {
        (0, 40): 'tandytext40',
        (0, 80): 'tandytext80',
        1: '320x200x4_8pg',
        2: '640x200x2_8pg',
        3: '160x200x16',
        4: '320x200x4pcjr',
        5: '320x200x16pcjr',
        6: '640x200x4',
    },
    'pcjr': {
        (0, 40): 'cgatext40',
        (0, 80): 'cgatext80',
        1: '320x200x4_8pg',
        2: '640x200x2_8pg',
        3: '160x200x16',
        4: '320x200x4pcjr',
        5: '320x200x16pcjr',
        6: '640x200x4',
    },
    'olivetti': {
        (0, 40): 'olivettitext40',
        (0, 80): 'olivettitext80',
        1: '320x200x4',
        2: '640x200x2',
        3: '640x400x2',
    },
}
# on Olivetti M24, all numbers 3-255 give the same 'super resolution'/'altissima risoluzione'
_MODES['olivetti'].update({_mode: '640x400x2' for _mode in range(4, 256)})


##############################################################################
# screen number switches on WIDTH
# if we're in mode x, what mode y does WIDTH w take us to? {x: {w: y}}
TO_WIDTH = {
    'cga': {
        0: {40: 0, 80: 0},
        1: {40: 1, 80: 2},
        2: {40: 1, 80: 2},
    },
    'ega': {
        0: {40: 0, 80: 0},
        1: {40: 1, 80: 2},
        2: {40: 1, 80: 2},
        7: {40: 7, 80: 8},
        8: {40: 7, 80: 8},
        9: {40: 1, 80: 9},
    },
    'mda': {
        0: {40: 0, 80: 0},
    },
    'ega_mono': {
        0: {40: 0, 80: 0},
        10: {40: 0, 80: 10},
    },
    'hercules': {
        0: {40: 0, 80: 0},
        3: {40: 0, 80: 3},
    },
    'pcjr': {
        0: {20: 3, 40: 0, 80: 0},
        1: {20: 3, 40: 1, 80: 2},
        2: {20: 3, 40: 1, 80: 2},
        3: {20: 3, 40: 1, 80: 2},
        4: {20: 3, 40: 4, 80: 2},
        5: {20: 3, 40: 5, 80: 6},
        6: {20: 3, 40: 5, 80: 6},
    },
    'olivetti': {
        0: {40: 0, 80: 0},
        1: {40: 1, 80: 2},
        2: {40: 1, 80: 2},
        3: {40: 1, 80: 3}, # assumption
    },
}

# also look up graphics modes by name
for _adapter in TO_WIDTH:
    TO_WIDTH[_adapter].update({
        _MODES[_adapter][_nr]: _switches for _nr, _switches in TO_WIDTH[_adapter].items() if _nr
    })

TO_WIDTH['ega_64k'] = TO_WIDTH['ega']
TO_WIDTH['vga'] = TO_WIDTH['ega']
TO_WIDTH['tandy'] = TO_WIDTH['pcjr']


def to_width(adapter, mode, to_width):
    """Get target mode number for WIDTH change."""
    if mode.is_text_mode and to_width in (40, 80):
        return 0
    else:
        try:
            return TO_WIDTH[adapter][mode.name][to_width]
        except KeyError:
            # raise an error if the width value doesn't make sense
            raise error.BASICError(error.IFC)


##############################################################################
# video mode number

_MODE_NUMBER = {
    '640x200x2': 6, '160x200x16': 8, '320x200x16pcjr': 9,
    '640x200x4': 10, '320x200x16': 13, '640x200x16': 14,
    '640x350x4': 15, '640x350x16': 16, '640x350x4c': 16, '640x400x2': 0x40,
    '320x200x4pcjr': 4, '320x200x4': 4
    # '720x348x2': ? # hercules - unknown
}

def get_mode_number(mode, colorswitch):
    """Get the low-level mode number used by mode switching interrupt."""
    if mode.is_text_mode:
        if mode.name in ('mdatext80', 'ega_monotext80'):
            return 7
        return (mode.width == 40) * 2 + colorswitch % 2
    elif mode.name == '320x200x4':
        return 4 + colorswitch % 2 # mode_5 if colorswitch == 1
    else:
        try:
            return _MODE_NUMBER[mode.name]
        except KeyError:
            return 0xff


##############################################################################
# video mode factory

def get_mode(number, width, adapter, monitor, video_mem_size):
    """Retrieve text or graphical mode by screen number."""
    try:
        if number:
            name = _MODES[adapter][number]
        else:
            name = _MODES[adapter][0, width]
    except KeyError:
        # no such mode
        raise error.BASICError(error.IFC)
    mode_data = dict(**_MODE_INFO[name])
    cls = mode_data.pop('layout')
    return cls(name=name, video_mem_size=video_mem_size, **mode_data)


##############################################################################
# video mode base class

class VideoMode(object):
    """Base class for video modes."""

    is_text_mode = None
    is_cga_hires = False

    def __init__(
            self, name, height, width, font_height, font_width, attr, cursor_shape, colourmap
        ):
        """Initialise video mode settings."""
        self.name = name
        self.height = height
        self.width = width
        self.font_height = font_height
        self.font_width = font_width
        self.pixel_height = height * font_height
        self.pixel_width = width * font_width
        # initial/default attribute
        self.attr = attr
        # override these
        self.memorymap = None
        self.cursor_shape = cursor_shape
        self.colourmap = colourmap

    @property
    def num_pages(self):
        """Number of available pages."""
        return self.memorymap.num_pages

    def __eq__(self, rhs):
        """Equality with another mode or mode name."""
        if isinstance(rhs, VideoMode):
            return self.name == rhs.name
        else:
            return self.name == rhs

    def __ne__(self, rhs):
        """Inequality with another mode or mode name."""
        return not self.__eq__(rhs)


##############################################################################
# text modes

class TextMode(VideoMode):
    """Default settings for a text mode."""

    _textmemorymapper = TextMemoryMapper
    is_text_mode = True

    def __init__(
            self, name, rows, columns, font_height, font_width, attr, cursor_shape,
            video_mem_size, max_pages, mono, colourmap
        ):
        """Initialise video mode settings."""
        VideoMode.__init__(
            self, name, rows, columns, font_height, font_width, attr, cursor_shape, colourmap
        )
        self.memorymap = self._textmemorymapper(rows, columns, video_mem_size, max_pages, mono)


##############################################################################
# graphics modes


class GraphicsMode(VideoMode):
    """Default settings for a graphics mode."""

    # override these
    _memorymapper = GraphicsMemoryMapper
    _tile_builder = lambda _: None
    _sprite_builder = lambda _: None

    # text mode flag
    is_text_mode = False

    def __init__(
            self, name, width, height, rows, columns,
            attr, bitsperpixel, interleave_times, bank_size, video_mem_size, max_pages,
            cursor_attr, colourmap, is_cga_hires=False
        ):
        """Initialise video mode settings."""
        font_width = width // columns
        # ceildiv for hercules (14-px font on 348 lines)
        font_height = -(-height // rows)
        # block cursor in graphics mode
        cursor_shape = (0, font_height-1)
        VideoMode.__init__(
            self, name, rows, columns, font_height, font_width, attr, cursor_shape, colourmap
        )
        self.is_cga_hires = is_cga_hires
        # override pixel dimensions
        self.pixel_height = height
        self.pixel_width = width
        # used in display.py to initialise pixelbuffer
        self.bitsperpixel = bitsperpixel
        self.memorymap = self._memorymapper(
            height, width, video_mem_size, max_pages, interleave_times, bank_size, bitsperpixel
        )
        # cursor attribute
        self.cursor_attr = cursor_attr
        # sprite and tile builders
        self.build_tile = self._tile_builder(self.bitsperpixel)
        self.sprite_builder = self._sprite_builder(self.bitsperpixel)


class CGAMode(GraphicsMode):
    """Default settings for a CGA graphics mode."""

    _memorymapper = CGAMemoryMapper
    _tile_builder = PackedTileBuilder
    _sprite_builder = PackedSpriteBuilder


class EGAMode(GraphicsMode):
    """Default settings for a EGA graphics mode."""

    _memorymapper = EGAMemoryMapper
    _tile_builder = PlanedTileBuilder
    _sprite_builder = PlanedSpriteBuilder

    def __init__(
            self, name, width, height, rows, columns,
            attr, bitsperpixel, interleave_times, bank_size, video_mem_size, max_pages,
            cursor_attr, colourmap, planes_used=range(4)
        ):
        """Initialise video mode settings."""
        GraphicsMode.__init__(
            self, name, width, height, rows, columns,
            attr, bitsperpixel, interleave_times, bank_size, video_mem_size, max_pages,
            cursor_attr, colourmap
        )
        # EGA memorymap settings
        self.memorymap.set_planes_used(planes_used)


class Tandy6Mode(GraphicsMode):
    """Default settings for Tandy graphics mode 6."""

    _memorymapper = Tandy6MemoryMapper
    _tile_builder = PackedTileBuilder
    # initialising this with self.bitsperpixel should do the right thing
    _sprite_builder = Tandy6SpriteBuilder



##############################################################################
# mode definitions

_MODE_INFO = {
    # text modes

    'vgatext40': dict(
        rows=25, columns=40, font_height=16, font_width=9, attr=7, max_pages=8, mono=False,
        cursor_shape=(15, 15), layout=TextMode, colourmap=EGA64TextColourMapper
    ),
    'vgatext80': dict(
        rows=25, columns=80, font_height=16, font_width=9, attr=7, max_pages=4, mono=False,
        cursor_shape=(15, 15), layout=TextMode, colourmap=EGA64TextColourMapper
    ),
    'egatext40': dict(
        rows=25, columns=40, font_height=14, font_width=8, attr=7, max_pages=8, mono=False,
        cursor_shape=(12, 12), layout=TextMode, colourmap=EGA64TextColourMapper
    ),
    'egatext80': dict(
        rows=25, columns=80, font_height=14, font_width=8, attr=7, max_pages=4, mono=False,
        cursor_shape=(12, 12), layout=TextMode, colourmap=EGA64TextColourMapper
    ),
    'ega_monotext40': dict(
        rows=25, columns=40, font_height=14, font_width=8, attr=7, max_pages=8, mono=True,
        cursor_shape=(12, 12), layout=TextMode, colourmap=MonoTextColourMapper
    ),
    'ega_monotext80': dict(
        rows=25, columns=80, font_height=14, font_width=8, attr=7, max_pages=4, mono=True,
        cursor_shape=(12, 12), layout=TextMode, colourmap=MonoTextColourMapper
    ),
    'mdatext40': dict(
        rows=25, columns=40, font_height=14, font_width=9, attr=7, max_pages=1, mono=True,
        cursor_shape=(13, 13), layout=TextMode, colourmap=MonoTextColourMapper
    ),
    'mdatext80': dict(
        rows=25, columns=80, font_height=14, font_width=9, attr=7, max_pages=1, mono=True,
        cursor_shape=(13, 13), layout=TextMode, colourmap=MonoTextColourMapper
    ),
    'tandytext40': dict(
        rows=25, columns=40, font_height=9, font_width=8, attr=7, max_pages=8, mono=False,
        cursor_shape=(7, 7), layout=TextMode, colourmap=EGA16TextColourMapper
    ),
    'tandytext80': dict(
        rows=25, columns=80, font_height=9, font_width=8, attr=7, max_pages=4, mono=False,
        cursor_shape=(7, 7), layout=TextMode, colourmap=EGA16TextColourMapper
    ),
    'cgatext40': dict(
        rows=25, columns=40, font_height=8, font_width=8, attr=7, max_pages=8, mono=False,
        cursor_shape=(7, 7), layout=TextMode, colourmap=EGA16TextColourMapper
    ),
    'cgatext80': dict(
        rows=25, columns=80, font_height=8, font_width=8, attr=7, max_pages=4, mono=False,
        cursor_shape=(7, 7), layout=TextMode, colourmap=EGA16TextColourMapper
    ),
    'olivettitext40': dict(
        rows=25, columns=40, font_height=16, font_width=8, attr=7, max_pages=8, mono=False,
        cursor_shape=(15, 15), layout=TextMode, colourmap=EGA16TextColourMapper
    ),
    'olivettitext80': dict(
        rows=25, columns=80, font_height=16, font_width=8, attr=7, max_pages=4, mono=False,
        cursor_shape=(15, 15), layout=TextMode, colourmap=EGA16TextColourMapper
    ),

    # graphics modes

    '320x200x4': dict(
        # 04h 320x200x4  16384B 2bpp 0xb8000    screen 1
        # cga/ega: 1 page only
        width=320, height=200, rows=25, columns=40, attr=3, cursor_attr=None,
        bitsperpixel=2, interleave_times=2, bank_size=0x2000, max_pages=1,
        layout=CGAMode, colourmap=CGA4ColourMapper
    ),
    '640x200x2': dict(
        # 06h 640x200x2  16384B 1bpp 0xb8000    screen 2
        width=640, height=200, rows=25, columns=80, attr=1, cursor_attr=None,
        bitsperpixel=1, interleave_times=2, bank_size=0x2000, max_pages=1,
        layout=CGAMode, colourmap=CGA2ColourMapper, is_cga_hires=True
    ),
    '160x200x16': dict(
        # 08h 160x200x16 16384B 4bpp 0xb8000    PCjr/Tandy screen 3
        width=160, height=200, rows=25, columns=20, attr=15, cursor_attr=3,
        bitsperpixel=4, interleave_times=2, bank_size=0x2000, max_pages=8,
        layout=CGAMode, colourmap=CGA16ColourMapper
    ),
    '320x200x4pcjr': dict(
        #     320x200x4  16384B 2bpp 0xb8000   Tandy/PCjr screen 4
        width=320, height=200, rows=25, columns=40, attr=3, cursor_attr=3,
        bitsperpixel=2, interleave_times=2, bank_size=0x2000, max_pages=8,
        layout=CGAMode, colourmap=Tandy4ColourMapper
    ),
    '320x200x16pcjr': dict(
        # 09h 320x200x16 32768B 4bpp 0xb8000    Tandy/PCjr screen 5
        width=320, height=200, rows=25, columns=40, attr=15, cursor_attr=3,
        bitsperpixel=4, interleave_times=4, bank_size=0x2000, max_pages=4,
        layout=CGAMode, colourmap=CGA16ColourMapper
    ),
    '640x200x4': dict(
        # 0Ah 640x200x4  32768B 2bpp 0xb8000   Tandy/PCjr screen 6
        width=640, height=200, rows=25, columns=80, attr=3, cursor_attr=3,
        bitsperpixel=2, interleave_times=4, bank_size=0x2000, max_pages=4,
        layout=Tandy6Mode, colourmap=Tandy4ColourMapper
    ),
    '320x200x16': dict(
        # 0Dh 320x200x16 32768B 4bpp 0xa0000    EGA screen 7
        width=320, height=200, rows=25, columns=40, attr=15, cursor_attr=None,
        bitsperpixel=4, interleave_times=1, bank_size=0x2000, max_pages=None,
        layout=EGAMode, colourmap=EGA16ColourMapper
    ),
    '640x200x16': dict(
        # 0Eh 640x200x16    EGA screen 8
        width=640, height=200, rows=25, columns=80, attr=15, cursor_attr=None,
        bitsperpixel=4, interleave_times=1, bank_size=0x4000, max_pages=None,
        layout=EGAMode, colourmap=EGA16ColourMapper
    ),
    '640x350x16': dict(
        # 10h 640x350x16    EGA screen 9
        width=640, height=350, rows=25, columns=80, attr=15, cursor_attr=None,
        bitsperpixel=4, interleave_times=1, bank_size=0x8000, max_pages=None,
        layout=EGAMode, colourmap=EGA64ColourMapper
    ),
    '640x350x4c': dict(
        # 10h 640x350x16    EGA screen 9 with 64K
        width=640, height=350, rows=25, columns=80, attr=3, cursor_attr=None,
        bitsperpixel=2, interleave_times=1, bank_size=0x8000, max_pages=None,
        layout=EGAMode, colourmap=EGA4ColourMapper
    ),
    '640x350x4': dict(
        # 0Fh 640x350x4     EGA monochrome screen 10
        width=640, height=350, rows=25, columns=80, attr=1, cursor_attr=None,
        bitsperpixel=2, interleave_times=1, bank_size=0x8000, max_pages=None, planes_used=(1, 3),
        layout=EGAMode, colourmap=EGAMonoColourMapper
    ),
    '640x400x2': dict(
        # 40h 640x400x2   1bpp  olivetti screen 3-255
        width=640, height=400, rows=25, columns=80, attr=1, cursor_attr=None,
        bitsperpixel=1, interleave_times=4, bank_size=0x2000, max_pages=1,
        layout=CGAMode, colourmap=Olivetti2ColourMapper
    ),
    '720x348x2': dict(
        # hercules screen 3
        # SCREEN 3 supports two pages (0 and 1);
        # SCREEN 0 used with Hercules supports only one page.
        # see MS KB 21839, https://jeffpar.github.io/kbarchive/kb/021/Q21839/
        width=720, height=348, rows=25, columns=80, attr=1, cursor_attr=None,
        bitsperpixel=1, interleave_times=4, bank_size=0x2000, max_pages=2,
        layout=CGAMode, colourmap=HerculesColourMapper
    ),
}

# tandy/pcjr 8-page versions of standard CGA modes (?)
_MODE_INFO['320x200x4_8pg'] = _MODE_INFO['320x200x4']
_MODE_INFO['640x200x2_8pg'] = _MODE_INFO['640x200x2']
_MODE_INFO['320x200x4_8pg']['max_pages'] = 8
_MODE_INFO['640x200x2_8pg']['max_pages'] = 8
