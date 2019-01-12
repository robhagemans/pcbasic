"""
PC-BASIC - display.modes
Emulated video modes

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import error
from ..base import bytematrix
from .colours import MONO_TINT, ColourMapper, CGAColourMapper, CGA4ColourMapper, EGAColourMapper
from .colours import MonoTextColourMapper, EGAMonoColourMapper, HerculesColourMapper
from .framebuffer import TextMemoryMapper, GraphicsMemoryMapper
from .framebuffer import CGAMemoryMapper, EGAMemoryMapper, Tandy6MemoryMapper
from .framebuffer import PackedTileBuilder, PlanedTileBuilder
from .framebuffer import PackedSpriteBuilder, PlanedSpriteBuilder


class Video(object):
    """Mode factory."""

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


    ###########################################################################
    # video modes

    def prepare_modes(self, video_mem_size):
        """Build lists of allowed graphics modes."""
        video_mem_size = int(video_mem_size)
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
                num_colours=16, bitsperpixel=2, interleave_times=2, bank_size=0x2000,
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
                num_colours=16, bitsperpixel=1, interleave_times=2, bank_size=0x2000, num_pages=1,
                aspect=self.aspect, supports_artifacts=True
            ),
            # 08h 160x200x16 16384B 4bpp 0xb8000    PCjr/Tandy screen 3
            '160x200x16': CGAMode(
                '160x200x16', 160, 200, 25, 20, 15,
                num_colours=16, bitsperpixel=4, interleave_times=2, bank_size=0x2000,
                num_pages=video_mem_size//(2*0x2000), pixel_aspect=(1968, 1000), cursor_index=3
            ),
            #     320x200x4  16384B 2bpp 0xb8000   Tandy/PCjr screen 4
            '320x200x4pcjr': CGA4Mode(
                '320x200x4pcjr', 320, 200, 25, 40, 3,
                num_colours=4, bitsperpixel=2, interleave_times=2, bank_size=0x2000,
                num_pages=video_mem_size//(2*0x2000), aspect=self.aspect, cursor_index=3
            ),
            # 09h 320x200x16 32768B 4bpp 0xb8000    Tandy/PCjr screen 5
            '320x200x16pcjr': CGAMode(
                '320x200x16pcjr', 320, 200, 25, 40, 15,
                num_colours=16, bitsperpixel=4, interleave_times=4, bank_size=0x2000,
                num_pages=video_mem_size // (4*0x2000), aspect=self.aspect, cursor_index=3
            ),
            # 0Ah 640x200x4  32768B 2bpp 0xb8000   Tandy/PCjr screen 6
            '640x200x4': Tandy6Mode(
                '640x200x4', 640, 200, 25, 80, 3,
                num_colours=4, bitsperpixel=2, interleave_times=4, bank_size=0x2000,
                num_pages=video_mem_size // (4*0x2000), aspect=self.aspect, cursor_index=3
            ),
            # 0Dh 320x200x16 32768B 4bpp 0xa0000    EGA screen 7
            '320x200x16': EGAMode(
                '320x200x16', 320, 200, 25, 40, 15,
                num_colours=16, bitsperpixel=4, interleave_times=1, bank_size=0x2000,
                num_pages=video_mem_size // (4*0x2000), aspect=self.aspect
            ),
            # 0Eh 640x200x16    EGA screen 8
            '640x200x16': EGAMode(
                '640x200x16', 640, 200, 25, 80, 15,
                num_colours=16, bitsperpixel=4, interleave_times=1, bank_size=0x4000,
                num_pages=video_mem_size // (4*0x4000), aspect=self.aspect,
            ),
            # 10h 640x350x16    EGA screen 9
            '640x350x16': EGAMode(
                '640x350x16', 640, 350, 25, 80, 15,
                num_colours=64, bitsperpixel=4, interleave_times=1, bank_size=0x8000,
                num_pages=video_mem_size // (4*0x8000), aspect=self.aspect
            ),
            # 0Fh 640x350x4     EGA monochrome screen 10
            '640x350x4': EGAMonoMode(
                '640x350x16', 640, 350, 25, 80, 1,
                num_colours=9, bitsperpixel=2, interleave_times=1, bank_size=0x8000,
                num_pages=video_mem_size // (2*0x8000),
                aspect=self.aspect, has_blink=True, planes_used=(1, 3)
            ),
            # 40h 640x400x2   1bpp  olivetti screen 3
            '640x400x2': CGAMode(
                '640x400x2', 640, 400, 25, 80, 1,
                num_colours=2, bitsperpixel=1, interleave_times=4, bank_size=0x2000,
                num_pages=1, aspect=self.aspect, has_blink=True
            ),
            # hercules screen 3
            '720x348x2': HerculesMode(
                # this actually produces 350, not 348
                '720x348x2', 720, 350, 25, 80, 1,
                num_colours=16, bitsperpixel=1,
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
                40: TextMode('vgatext40', 25, 40, 16, 9, 7, num_colours=64, num_pages=8),
                80: TextMode('vgatext80', 25, 80, 16, 9, 7, num_colours=64, num_pages=4)
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
                40: TextMode('egatext40', 25, 40, 14, 8, 7, num_colours=64, num_pages=8),
                80: TextMode('egatext80', 25, 80, 14, 8, 7, num_colours=64, num_pages=4)
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
                    'ega_monotext40', 25, 40, 14, 8, 7, num_colours=None, is_mono=True, num_pages=8
                ),
                80: MonoTextMode(
                    'ega_monotext80', 25, 80, 14, 8, 7, num_colours=None, is_mono=True, num_pages=4
                )
            }
            self._mode_data = {
                10: graphics_mode['640x350x4']
            }
        elif self.capabilities == 'mda':
            self._text_data = {
                40: MonoTextMode(
                    'mdatext40', 25, 40, 14, 9, 7, num_colours=None, is_mono=True, num_pages=1
                ),
                80: MonoTextMode(
                    'mdatext80', 25, 80, 14, 9, 7, num_colours=None, is_mono=True, num_pages=1
                )
            }
            self._mode_data = {}
        elif self.capabilities in ('cga', 'cga_old', 'pcjr', 'tandy'):
            if self.capabilities == 'tandy':
                self._text_data = {
                    40: TextMode('tandytext40', 25, 40, 9, 8, 7, num_colours=16, num_pages=8),
                    80: TextMode('tandytext80', 25, 80, 9, 8, 7, num_colours=16, num_pages=4)
                }
            else:
                self._text_data = {
                    40: TextMode('cgatext40', 25, 40, 8, 8, 7, num_colours=16, num_pages=8),
                    80: TextMode('cgatext80', 25, 80, 8, 8, 7, num_colours=16, num_pages=4)
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
                    'herculestext40', 25, 40, 14, 9, 7, num_colours=None, is_mono=True, num_pages=2
                ),
                80: MonoTextMode(
                    'herculestext80', 25, 80, 14, 9, 7, num_colours=None, is_mono=True, num_pages=2
                )
            }
            self._mode_data = {
                3: graphics_mode['720x348x2']
            }
        elif self.capabilities == 'olivetti':
            self._text_data = {
                40: TextMode('olivettitext40', 25, 40, 16, 8, 7, num_colours=16, num_pages=8),
                80: TextMode('olivettitext80', 25, 80, 16, 8, 7, num_colours=16, num_pages=4)
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
# video mode base class

class VideoMode(object):
    """Base class for video modes."""

    _colourmapper = ColourMapper

    def __init__(
            self, name, height, width, font_height, font_width,
            attr, num_colours, num_attr, num_pages, has_blink
        ):
        """Initialise video mode settings."""
        self.is_text_mode = False
        self.name = name
        self.height = height
        self.width = width
        self.font_height = font_height
        self.font_width = font_width
        self.pixel_height = height * font_height
        self.pixel_width = width * font_width
        self.attr = attr
        self.num_pages = num_pages # or video_mem_size // page_size
        # override this
        self.memorymap = None
        self.colourmap = self._colourmapper(has_blink, num_attr, num_colours)

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


##############################################################################
# text modes

class TextMode(VideoMode):
    """Default settings for a text mode."""

    _colourmapper = EGAColourMapper
    _textmemorymapper = TextMemoryMapper

    def __init__(
            self, name, height, width,
            font_height, font_width, attr, num_colours,
            num_pages, is_mono=False, has_blink=True
        ):
        """Initialise video mode settings."""
        video_segment = 0xb000 if is_mono else 0xb800
        page_size = 0x1000 if width == 80 else 0x800
        num_attr = 256
        VideoMode.__init__(
            self, name, height, width,
            font_height, font_width, attr, num_colours, num_attr,
            num_pages, has_blink
        )
        self.is_text_mode = True
        self.memorymap = self._textmemorymapper(
           height, width, self.pixel_height, self.pixel_width,
           num_pages, video_segment, page_size
        )


class MonoTextMode(TextMode):
    """MDA-style text mode with underlining."""

    _colourmapper = MonoTextColourMapper


class CGATextMode(TextMode):
    """MDA-style text mode with underlining."""

    _colourmapper = CGAColourMapper


##############################################################################
# graphics modes

class GraphicsMode(VideoMode):
    """Default settings for a graphics mode."""

    _memorymapper = GraphicsMemoryMapper
    # override these
    _tile_builder = lambda _: None
    _sprite_builder = lambda _: None

    def __init__(
            self, name, pixel_width, pixel_height,
            text_height, text_width,
            attr, num_colours, bitsperpixel,
            interleave_times, bank_size,
            num_pages=None,
            has_blink=False,
            supports_artifacts=False,
            cursor_index=None,
            pixel_aspect=None, aspect=None,
            video_segment=0xb800,
        ):
        """Initialise video mode settings."""
        font_width = pixel_width // text_width
        font_height = pixel_height // text_height
        num_attr = 2**bitsperpixel
        VideoMode.__init__(
            self, name, text_height, text_width,
            font_height, font_width, attr, num_colours, num_attr,
            num_pages, has_blink
        )
        self.is_text_mode = False
        # used in display.py to initialise pixelbuffer
        self.bitsperpixel = bitsperpixel
        self.memorymap = self._memorymapper(
            text_height, text_width, pixel_height, pixel_width,
            num_pages, video_segment, interleave_times, bank_size,
            bitsperpixel
        )
        self.supports_artifacts = supports_artifacts
        self.cursor_index = cursor_index
        if pixel_aspect:
            self.pixel_aspect = pixel_aspect
        else:
            self.pixel_aspect = (self.pixel_height * aspect[0], self.pixel_width * aspect[1])
        # sprite and tile builders
        self.build_tile = self._tile_builder(self.bitsperpixel)
        self.sprite_builder = self._sprite_builder(self.bitsperpixel)


class CGAMode(GraphicsMode):
    """Default settings for a CGA graphics mode."""

    _memorymapper = CGAMemoryMapper
    _colourmapper = CGAColourMapper
    _tile_builder = PackedTileBuilder
    _sprite_builder = PackedSpriteBuilder


class CGA4Mode(CGAMode):
    """Default settings for a CGA graphics mode."""

    _colourmapper = CGA4ColourMapper


class HerculesMode(CGAMode):
    """Default settings for a CGA graphics mode."""

    _colourmapper = HerculesColourMapper


class EGAMode(GraphicsMode):
    """Default settings for a EGA graphics mode."""

    _memorymapper = EGAMemoryMapper
    _colourmapper = EGAColourMapper
    _tile_builder = PlanedTileBuilder
    _sprite_builder = PlanedSpriteBuilder

    def __init__(
            self, name, pixel_width, pixel_height,
            text_height, text_width,
            attr, num_colours, bitsperpixel,
            interleave_times, bank_size, num_pages,
            has_blink=False, planes_used=range(4),
            aspect=None
        ):
        """Initialise video mode settings."""
        GraphicsMode.__init__(
            self, name, pixel_width, pixel_height,
            text_height, text_width,
            attr, num_colours, bitsperpixel,
            interleave_times, bank_size,
            num_pages, has_blink, aspect=aspect
        )
        # EGA memorymap settings
        self.memorymap.set_planes_used(planes_used)


class EGAMonoMode(EGAMode):
    """Default settings for a EGA monochrome graphics mode (mode 10)."""

    _colourmapper = EGAMonoColourMapper


class Tandy6Mode(GraphicsMode):
    """Default settings for Tandy graphics mode 6."""

    _memorymapper = Tandy6MemoryMapper
    _colourmapper = CGA4ColourMapper
    _tile_builder = PackedTileBuilder
    # initialising this with self.bitsperpixel should do the right thing
    _sprite_builder = PlanedSpriteBuilder
