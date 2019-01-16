"""
PC-BASIC - display.modes
Emulated video modes

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import error
from ..base import bytematrix
from .colours import CGA2ColourMapper, CGA4ColourMapper, CGA16ColourMapper
from .colours import EGA16ColourMapper, EGA64ColourMapper
from .colours import EGA16TextColourMapper, EGA64TextColourMapper
from .colours import MonoTextColourMapper, EGAMonoColourMapper, HerculesColourMapper
from .framebuffer import TextMemoryMapper, GraphicsMemoryMapper
from .framebuffer import CGAMemoryMapper, EGAMemoryMapper, Tandy6MemoryMapper
from .framebuffer import PackedTileBuilder, PlanedTileBuilder
from .framebuffer import PackedSpriteBuilder, PlanedSpriteBuilder


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
        1: '320x200x4',
        2: '640x200x2',
        3: '160x200x16',
        4: '320x200x4pcjr',
        5: '320x200x16pcjr',
        6: '640x200x4',
    },
    'pcjr': {
        (0, 40): 'cgatext40',
        (0, 80): 'cgatext80',
        1: '320x200x4',
        2: '640x200x2',
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

TO_WIDTH['vga'] = TO_WIDTH['ega']
TO_WIDTH['tandy'] = TO_WIDTH['pcjr']


def get_mode(number, width, adapter, monitor, video_mem_size):
    """Retrieve text or graphical mode by screen number."""
    try:
        if number:
            name = _MODES[adapter][number]
            return _get_graphics_mode(name, adapter, monitor, video_mem_size)
        else:
            name = _MODES[adapter][0, width]
            return _get_text_mode(name, adapter, monitor, video_mem_size)
    except KeyError:
        # no such mode
        raise error.BASICError(error.IFC)

def _get_graphics_mode(name, adapter, monitor, video_mem_size):
    """Retrieve graphical mode by name."""
    if name == '320x200x4':
        # 04h 320x200x4  16384B 2bpp 0xb8000    screen 1
        # tandy:2 pages if 32k memory; ega: 1 page only
        return CGAMode(
            '320x200x4', 320, 200, 25, 40, 3,
            bitsperpixel=2, interleave_times=2, bank_size=0x2000,
            video_mem_size=video_mem_size,
            max_pages=(2 if adapter in ('pcjr', 'tandy') else 1),
            cursor_index=None,
            colourmap=CGA4ColourMapper(adapter, monitor)
        )
    elif name == '640x200x2':
        # 06h 640x200x2  16384B 1bpp 0xb8000    screen 2
        return CGAMode(
            '640x200x2', 640, 200, 25, 80, 1,
            bitsperpixel=1, interleave_times=2, bank_size=0x2000,
            video_mem_size=video_mem_size, max_pages=1, cursor_index=None,
            colourmap=CGA2ColourMapper(adapter, monitor)
        )
    elif name == '160x200x16':
        # 08h 160x200x16 16384B 4bpp 0xb8000    PCjr/Tandy screen 3
        return CGAMode(
            '160x200x16', 160, 200, 25, 20, 15,
            bitsperpixel=4, interleave_times=2, bank_size=0x2000,
            video_mem_size=video_mem_size, max_pages=None, cursor_index=3,
            colourmap=CGA16ColourMapper(adapter, monitor)
        )
    elif name == '320x200x4pcjr':
        #     320x200x4  16384B 2bpp 0xb8000   Tandy/PCjr screen 4
        return CGAMode(
            '320x200x4pcjr', 320, 200, 25, 40, 3,
            bitsperpixel=2, interleave_times=2, bank_size=0x2000,
            video_mem_size=video_mem_size, max_pages=None, cursor_index=3,
            colourmap=CGA4ColourMapper(adapter, monitor)
        )
    elif name == '320x200x16pcjr':
        # 09h 320x200x16 32768B 4bpp 0xb8000    Tandy/PCjr screen 5
        return CGAMode(
            '320x200x16pcjr', 320, 200, 25, 40, 15,
            bitsperpixel=4, interleave_times=4, bank_size=0x2000,
            video_mem_size=video_mem_size, max_pages=None, cursor_index=3,
            colourmap=CGA16ColourMapper(adapter, monitor)
        )
    elif name == '640x200x4':
        # 0Ah 640x200x4  32768B 2bpp 0xb8000   Tandy/PCjr screen 6
        return Tandy6Mode(
            '640x200x4', 640, 200, 25, 80, 3,
            bitsperpixel=2, interleave_times=4, bank_size=0x2000,
            video_mem_size=video_mem_size, max_pages=None, cursor_index=3,
            colourmap=CGA4ColourMapper(adapter, monitor)
        )
    elif name == '320x200x16':
        # 0Dh 320x200x16 32768B 4bpp 0xa0000    EGA screen 7
        return EGAMode(
            '320x200x16', 320, 200, 25, 40, 15,
            bitsperpixel=4, interleave_times=1, bank_size=0x2000,
            video_mem_size=video_mem_size, max_pages=None, cursor_index=None,
            colourmap=EGA16ColourMapper(adapter, monitor)
        )
    elif name == '640x200x16':
        # 0Eh 640x200x16    EGA screen 8
        return EGAMode(
            '640x200x16', 640, 200, 25, 80, 15,
            bitsperpixel=4, interleave_times=1, bank_size=0x4000,
            video_mem_size=video_mem_size, max_pages=None, cursor_index=None,
            colourmap=EGA16ColourMapper(adapter, monitor)
        )
    elif name == '640x350x16':
        # 10h 640x350x16    EGA screen 9
        return EGAMode(
            '640x350x16', 640, 350, 25, 80, 15,
            bitsperpixel=4, interleave_times=1, bank_size=0x8000,
            video_mem_size=video_mem_size, max_pages=None, cursor_index=None,
            colourmap=EGA64ColourMapper(adapter, monitor)
        )
    elif name == '640x350x4':
        # 0Fh 640x350x4     EGA monochrome screen 10
        return EGAMode(
            '640x350x16', 640, 350, 25, 80, 1,
            bitsperpixel=2, interleave_times=1, bank_size=0x8000,
            video_mem_size=video_mem_size, max_pages=None, cursor_index=None,
            planes_used=(1, 3),
            colourmap=EGAMonoColourMapper(adapter, monitor)
        )
    elif name == '640x400x2':
        # 40h 640x400x2   1bpp  olivetti screen 3-255
        return CGAMode(
            '640x400x2', 640, 400, 25, 80, 1,
            bitsperpixel=1, interleave_times=4, bank_size=0x2000,
            video_mem_size=video_mem_size, max_pages=1, cursor_index=None,
            colourmap=CGA2ColourMapper(adapter, monitor)
        )
    elif name == '720x348x2':
        # hercules screen 3
        # SCREEN 3 supports two pages (0 and 1);
        # SCREEN 0 used with Hercules supports only one page.
        # see MS KB 21839, https://jeffpar.github.io/kbarchive/kb/021/Q21839/
        return CGAMode(
            '720x348x2', 720, 348, 25, 80, 1,
            bitsperpixel=1, interleave_times=4, bank_size=0x2000,
            video_mem_size=video_mem_size, max_pages=2, cursor_index=None,
            colourmap=HerculesColourMapper(adapter, monitor)
        )

def _get_text_mode(name, adapter, monitor, video_mem_size):
    """Retrieve graphical mode by name."""
    if name == 'vgatext40':
        return TextMode(
            'vgatext40', 25, 40, 16, 9, 7,
            video_mem_size=video_mem_size, max_pages=8, mono=False,
            colourmap=EGA64TextColourMapper(adapter, monitor)
        )
    elif name == 'vgatext80':
        return TextMode(
            'vgatext80', 25, 80, 16, 9, 7,
            video_mem_size=video_mem_size, max_pages=4, mono=False,
            colourmap=EGA64TextColourMapper(adapter, monitor)
        )
    elif name == 'egatext40':
        return TextMode(
            'egatext40', 25, 40, 14, 8, 7,
            video_mem_size=video_mem_size, max_pages=8, mono=False,
            colourmap=EGA64TextColourMapper(adapter, monitor)
        )
    elif name == 'egatext80':
        return TextMode(
            'egatext80', 25, 80, 14, 8, 7,
            video_mem_size=video_mem_size, max_pages=4, mono=False,
            colourmap=EGA64TextColourMapper(adapter, monitor)
        )
    elif name == 'ega_monotext40':
        return TextMode(
            'ega_monotext40', 25, 40, 14, 8, 7,
            video_mem_size=video_mem_size, max_pages=8, mono=True,
            colourmap=MonoTextColourMapper(adapter, monitor)
        )
    elif name == 'ega_monotext80':
        return TextMode(
            'ega_monotext80', 25, 80, 14, 8, 7,
            video_mem_size=video_mem_size, max_pages=4, mono=True,
            colourmap=MonoTextColourMapper(adapter, monitor)
        )
    elif name == 'mdatext40':
        return TextMode(
            'mdatext40', 25, 40, 14, 9, 7,
            video_mem_size=video_mem_size, max_pages=1, mono=True,
            colourmap=MonoTextColourMapper(adapter, monitor)
        )
    elif name == 'mdatext80':
        return TextMode(
            'mdatext80', 25, 80, 14, 9, 7,
            video_mem_size=video_mem_size, max_pages=1, mono=True,
            colourmap=MonoTextColourMapper(adapter, monitor)
        )
    elif name == 'tandytext40':
        return TextMode(
            'tandytext40', 25, 40, 9, 8, 7,
            video_mem_size=video_mem_size, max_pages=8, mono=False,
            colourmap=EGA16TextColourMapper(adapter, monitor)
        )
    elif name == 'tandytext80':
        return TextMode(
            'tandytext80', 25, 80, 9, 8, 7,
            video_mem_size=video_mem_size, max_pages=4, mono=False,
            colourmap=EGA16TextColourMapper(adapter, monitor)
        )
    elif name == 'cgatext40':
        return TextMode(
            'cgatext40', 25, 40, 8, 8, 7,
            video_mem_size=video_mem_size, max_pages=8, mono=False,
            colourmap=EGA16TextColourMapper(adapter, monitor)
        )
    elif name == 'cgatext80':
        return TextMode(
            'cgatext80', 25, 80, 8, 8, 7,
            video_mem_size=video_mem_size, max_pages=4, mono=False,
            colourmap=EGA16TextColourMapper(adapter, monitor)
        )
    elif name == 'olivettitext40':
        return TextMode(
            'olivettitext40', 25, 40, 16, 8, 7,
            video_mem_size=video_mem_size, max_pages=8, mono=False,
            colourmap=EGA16ColourMapper(adapter, monitor)
        )
    elif name == 'olivettitext80':
        return TextMode(
            'olivettitext80', 25, 80, 16, 8, 7,
            video_mem_size=video_mem_size, max_pages=4, mono=False,
            colourmap=EGA16ColourMapper(adapter, monitor)
        )


##############################################################################
# video mode base class

class VideoMode(object):
    """Base class for video modes."""

    def __init__(
            self, name, height, width, font_height, font_width, attr, colourmap
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
        self.is_text_mode = None
        self.memorymap = None
        self.colourmap = colourmap

    @property
    def num_pages(self):
        """Number of available pages."""
        return self.memorymap.num_pages

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

    def __eq__(self, rhs):
        """Check equality with another mode or mode name."""
        if isinstance(rhs, VideoMode):
            return self.name == rhs.name
        else:
            return self.name == rhs


##############################################################################
# text modes

class TextMode(VideoMode):
    """Default settings for a text mode."""

    _textmemorymapper = TextMemoryMapper

    def __init__(
            self, name, height, width, font_height, font_width, attr,
            video_mem_size, max_pages, mono, colourmap
        ):
        """Initialise video mode settings."""
        VideoMode.__init__(
            self, name, height, width, font_height, font_width, attr, colourmap
        )
        self.is_text_mode = True
        self.memorymap = self._textmemorymapper(height, width, video_mem_size, max_pages, mono)


##############################################################################
# graphics modes

class GraphicsMode(VideoMode):
    """Default settings for a graphics mode."""

    # override these
    _memorymapper = GraphicsMemoryMapper
    _tile_builder = lambda _: None
    _sprite_builder = lambda _: None

    def __init__(
            self, name, pixel_width, pixel_height, text_height, text_width,
            attr, bitsperpixel, interleave_times, bank_size, video_mem_size, max_pages,
            cursor_index, colourmap
        ):
        """Initialise video mode settings."""
        font_width = pixel_width // text_width
        # ceildiv for hercules (14-px font on 348 lines)
        font_height = -(-pixel_height // text_height)
        VideoMode.__init__(
            self, name, text_height, text_width, font_height, font_width, attr, colourmap
        )
        # override pixel dimensions
        self.pixel_height = pixel_height
        self.pixel_width = pixel_width
        # text mode flag
        self.is_text_mode = False
        # used in display.py to initialise pixelbuffer
        self.bitsperpixel = bitsperpixel
        self.memorymap = self._memorymapper(
            pixel_height, pixel_width, video_mem_size, max_pages,
            interleave_times, bank_size, bitsperpixel
        )
        # cursor attribute
        self.cursor_index = cursor_index
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
            self, name, pixel_width, pixel_height, text_height, text_width,
            attr, bitsperpixel, interleave_times, bank_size, video_mem_size, max_pages,
            cursor_index, colourmap, planes_used=range(4)
        ):
        """Initialise video mode settings."""
        GraphicsMode.__init__(
            self, name, pixel_width, pixel_height, text_height, text_width,
            attr, bitsperpixel, interleave_times, bank_size, video_mem_size, max_pages,
            cursor_index, colourmap
        )
        # EGA memorymap settings
        self.memorymap.set_planes_used(planes_used)


class Tandy6Mode(GraphicsMode):
    """Default settings for Tandy graphics mode 6."""

    _memorymapper = Tandy6MemoryMapper
    _tile_builder = PackedTileBuilder
    # initialising this with self.bitsperpixel should do the right thing
    _sprite_builder = PlanedSpriteBuilder
