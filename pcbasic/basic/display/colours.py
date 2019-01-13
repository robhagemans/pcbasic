"""
PC-BASIC - display.colours
Palettes and colour sets

(c) 2013--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import error
from ..base import signals


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
    ),
    # not used, retained for reference
    'cga_old': (
        (0x00, 0x00, 0x00), (0x00, 0x71, 0x00), (0x00, 0x3f, 0xff), (0x00, 0xab, 0xff),
        (0xc3, 0x00, 0x67), (0x73, 0x73, 0x73), (0xe6, 0x39, 0xff), (0x8c, 0xa8, 0xff),
        (0x53, 0x44, 0x00), (0x00, 0xcd, 0x00), (0x73, 0x73, 0x73), (0x00, 0xfc, 0x7e),
        (0xff, 0x39, 0x00), (0xe2, 0xca, 0x00), (0xff, 0x7c, 0xf4), (0xff, 0xff, 0xff)
    ),
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


#######################################################################################
# tinted monochrome monitors

MONO_TINT = {
    'green': (0, 255, 0),
    'amber': (255, 128, 0),
    'grey': (255, 255, 255),
    'mono': (0, 255, 0),
}

# apparent intensity
# these correspond to NTSC, ITU-R Recommendation BT.  601-2
# see https://poynton.ca/notes/colour_and_gamma/ColorFAQ.html#RTFToC3
#_RGB_INTENSITY = (0.299, 0.587, 0.114)
# some monitors seemed to show increasing intensity for the 16 shades,
# see https://www.vogons.org/viewtopic.php?t=29101
# also https://nerdlypleasures.blogspot.com/2014/03/the-monochrome-experience-cga-ega-and.html
_RGB_INTENSITY = (0.5, 0.3, 0.2)


def _adjust_tint(rgb, mono_tint, mono):
    """Convert (r, g, b) tuple to tinted monochrome."""
    if not mono:
        return rgb
    intensity = sum(_value * _weight for _value, _weight in zip(rgb, _RGB_INTENSITY))
    return tuple(int(_tint * intensity) // 255 for _tint in mono_tint)


#######################################################################################
# palette

class Palette(object):
    """Wrapper for ColourMapper to submit to interface on palette changes."""

    def __init__(self, queues, mode):
        """Initialise palette."""
        self._queues = queues
        self._colourmap = mode.colourmap
        # map from fore/back attr to video adapter colour
        # interpretation is video mode dependent
        self._colourmap.reset_palette()
        self.submit()

    def init_mode(self, mode, colorswitch):
        """Initialise for new mode and colorswitch parameter."""
        self._colourmap = mode.colourmap
        self._colourmap.set_colorswitch(colorswitch)
        self.reset()

    def set_colorburst(self, on=True):
        """Set the NTSC colorburst bit (machine port &h03d8)."""
        self._colourmap.set_colorburst(on)
        # reset the palette to reflect the new mono or mode-5 situation
        # this sends the signal to the interface as well
        self.reset()

    def set_cga4_palette(self, num):
        """Set the default 4-colour CGA palette."""
        self._colourmap.set_cga4_palette(num)
        self.submit()

    def set_cga4_intensity(self, high):
        """Set/unset the palette intensity."""
        self._colourmap.set_cga4_intensity(high)
        self.submit()

    def reset(self):
        """Initialise for new mode."""
        self._colourmap.reset_palette()
        self.submit()

    def set_all(self, new_palette, force=False):
        """Set the colours for all attributes."""
        if force or self._colourmap.allows_palette_change():
            self._colourmap.palette = list(new_palette)
            self.submit()

    def set_entry(self, index, colour, force=False):
        """Set a new colour for a given attribute."""
        if force or self._colourmap.allows_palette_change():
            self._colourmap.palette[index] = colour
            # in text mode, we'd be setting more than one attribute
            # e.g. all true attributes with this number as foreground or background
            # and attr_to_rgb decides which
            self.submit()

    def submit(self):
        """Submit to interface."""
        # all attributes split into foreground RGB, background RGB, blink and underline
        rgb_table, compo_parms = self._colourmap.get_rgb_table()
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_PALETTE, (rgb_table, compo_parms)
        ))

    def get_entry(self, index):
        """Retrieve the colour for a given attribute."""
        return self._colourmap.palette[index]


###############################################################################
# colour mappers

class _ColourMapper(object):
    """Palette and colourset."""

    # override these

    # palette - lookup table that maps the valid attributes to colour values
    # these are "palette attributes" - e.g. the 16 foreground attributes for text mode.
    default_palette = ()

    # colour set - maps the valid colour values to RGB
    # int values that can be used as the right hand side of a palette assignment
    _colours = ()

    # interpret colours as monochrome intensity
    _mono_tint = MONO_TINT['mono']
    _mono = False

    def __init__(self, capabilities, monitor):
        """Initialise colour map."""
        if monitor in MONO_TINT:
            self._mono = monitor in MONO_TINT
            self._mono_tint = MONO_TINT[monitor]
        self.palette = list(self.default_palette)
        # policy on PALETTE changes
        # effective palette change is an error in CGA
        if capabilities in ('cga', 'cga_old', 'mda', 'hercules', 'olivetti'):
            self._palette_change_policy = 'error'
        # ignore palette changes in Tandy/PCjr SCREEN 0
        elif capabilities in ('tandy', 'pcjr') and self.num_attr == 256:
            self._palette_change_policy = 'deny'
        else:
            self._palette_change_policy = 'allow'

    def allows_palette_change(self):
        """Check if the video mode allows palette change."""
        if self._palette_change_policy == 'error':
            raise error.BASICError(error.IFC)
        return self._palette_change_policy != 'deny'

    def reset_palette(self):
        """Reset to default palette."""
        self.palette = list(self.default_palette)

    @property
    def num_palette(self):
        """Number of values in palette."""
        return len(self.default_palette)

    @property
    def num_colours(self):
        """Number of values in colour set."""
        return len(self._colours)

    @property
    def num_attr(self):
        """Number of attributes."""
        # attributes
        # there's 256 of these in text mode (fore/back/blink/underscore)
        # and in graphics mode this is likely the same as num_palette
        return len(self.default_palette)

    def split_attr(self, attr):
        """Split attribute byte into constituent parts."""
        return attr & 0xf, 0, False, False

    def join_attr(self, fore, back, blink, underline):
        """Join constituent parts into textmode attribute byte."""
        return fore & 0xf

    def get_rgb_table(self):
        """List of RGB/blink/underline for all attributes, given a palette."""
        return (
            [self.attr_to_rgb(_attr) for _attr in range(self.num_attr)],
            None
        )

    def attr_to_rgb(self, attr):
        """Convert attribute to RGB/blink/underline, given a palette."""
        rgb = _adjust_tint(self._colours[self.palette[attr]], self._mono_tint, self._mono)
        return rgb, rgb, False, False

    def get_cga4_palette(self):
        """CGA palette setting (accessible from memory)."""
        return 1

    def set_cga4_palette(self, num):
        """Set the default 4-colour CGA palette."""

    def set_cga4_intensity(self, high):
        """Set/unset the palette intensity."""

    def set_colorswitch(self, colorswitch):
        """Set the SCREEN colorswitch parameter."""
        # in SCREEN 0, set the colorburst
        # in SCREEN 1, set the colorburst (inverted)
        # in SCREEN 2, ignore parameter and turn off colorburst

    def set_colorburst(self, on):
        """Set the NTSC colorburst bit."""
        # not colourburst capable
        return False


class _TextColourMixin(object):
    """Translate text attributes to palette attributes."""

    @property
    def num_attr(self):
        """Number of attributes."""
        # attributes
        # there's 256 of these in text mode (fore/back/blink/underscore)
        # and in graphics mode this is likely the same as num_palette
        return 256

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

    def attr_to_rgb(self, attr):
        """Convert attribute to RGB/blink/underline, given a palette."""
        fore, back, blink, underline = self.split_attr(attr)
        fore_rgb = _adjust_tint(self._colours[self.palette[fore]], self._mono_tint, self._mono)
        back_rgb = _adjust_tint(self._colours[self.palette[back]], self._mono_tint, self._mono)
        return fore_rgb, back_rgb, blink, underline

    def set_colorswitch(self, colorswitch):
        """Set the SCREEN colorswitch parameter."""
        self.set_colorburst(colorswitch)


class HerculesColourMapper(_ColourMapper):
    """Hercules 16-greyscale palette."""

    # Hercules graphics has no PALETTE
    # see MS KB 21839, https://jeffpar.github.io/kbarchive/kb/021/Q21839/
    default_palette = (0, 1)
    _colours = ((0, 0, 0), (255, 255, 255))
    _mono = True


class _CGAColourMapper(_ColourMapper):
    """CGA 2-colour, 16-colour palettes."""

    _colours = COLOURS16

    def __init__(self, capabilities, monitor):
        """Initialise colour map."""
        _ColourMapper.__init__(self, capabilities, monitor)
        self._has_colorburst = capabilities in ('cga', 'cga_old', 'pcjr', 'tandy')
        # monochrome
        self._force_mono = monitor in MONO_TINT
        # rgb monitor
        self._force_colour = not self._force_mono and monitor != 'composite'

    def set_colorburst(self, colour_on):
        """Set the NTSC colorburst bit."""
        # On a composite monitor with CGA adapter (not EGA, VGA):
        # - on SCREEN 2 this enables artifacting
        # - on SCREEN 1 and 0 this switches between colour and greyscale
        # On an RGB monitor:
        # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
        # - ignored on other screens
        if self._has_colorburst:
            self._mono = self._force_mono or (not colour_on and not self._force_colour)


class _CompositeMixin(object):
    """Overrides to deal with NTSC composite artifacts."""

    def __init__(self, capabilities, monitor):
        """Initialise colour map."""
        self._has_composite = monitor == 'composite' and self._has_colorburst and capabilities
        self._composite = False

    def set_colorburst(self, colour_on):
        """Set the NTSC colorburst bit."""
        # On a composite monitor with CGA adapter (not EGA, VGA):
        # - on SCREEN 2 this enables artifacting
        self._composite = colour_on and self._has_composite

    @property
    def num_attr(self):
        """Number of attributes."""
        if self._composite:
            return len(COMPOSITE[self._composite])
        else:
            return len(self.default_palette)

    def get_rgb_table(self):
        """List of RGB/blink/underline for all attributes, given a palette."""
        if self._composite:
            compo_palette = tuple((_c, _c, False, False) for _c in COMPOSITE[self._composite])
            # 4bpp composite (16 shades), 1bpp original
            return (compo_palette, (4, 1))
        return _CGAColourMapper.get_rgb_table(self)


class CGA2ColourMapper(_CompositeMixin, _CGAColourMapper):
    """CGA 2-colour palettes, with composite support."""

    default_palette = CGA2_PALETTE

    def __init__(self, capabilities, monitor):
        """Initialise colour map."""
        _CompositeMixin.__init__(self, capabilities, monitor)
        _CGAColourMapper.__init__(self, capabilities, monitor)

    def set_colorswitch(self, colorswitch):
        """Set the SCREEN colorswitch parameter."""
        # in SCREEN 2 the colorswitch parameter has no effect
        # the color burst can only be changed through the CGA mode control register at port 03D8h
        self.set_colorburst(False)


class CGA16ColourMapper(_CGAColourMapper):
    """CGA 16-colour palettes."""

    default_palette = CGA16_PALETTE


class CGA4ColourMapper(_CGAColourMapper):
    """CGA 4-colour palettes, with colorburst setting, intensity setting and mode 5."""

    def __init__(self, capabilities, monitor):
        """Initialise colour map."""
        self._has_colorburst = capabilities in ('cga', 'cga_old', 'pcjr', 'tandy')
        # pcjr/tandy does not have mode 5
        self._tandy = capabilities in ('pcjr', 'tandy')
        self._has_mode_5 = capabilities in ('cga', 'cga_old')
        self._low_intensity = False
        # start with the cyan-magenta-white palette
        self._palette_number = 1
        self._mode_5 = False
        _CGAColourMapper.__init__(self, capabilities, monitor)

    def get_cga4_palette(self):
        """CGA palette setting (accessible from memory)."""
        return self._palette_number

    def set_cga4_palette(self, num):
        """Set the default 4-colour CGA palette."""
        self._palette_number = num % 2
        self.reset_palette()

    def set_cga4_intensity(self, high):
        """Set/unset the palette intensity."""
        self._low_intensity = not high
        self.reset_palette()

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

    def set_colorswitch(self, colorswitch):
        """Set the SCREEN colorswitch parameter."""
        # in SCREEN 1 the SCREEN colorswitch parameter works the other way around
        self.set_colorburst(not colorswitch)

    def set_colorburst(self, colour_on):
        """Set the NTSC colorburst bit."""
        if not self._has_colorburst:
            return
        # On a composite monitor with CGA adapter (not EGA, VGA):
        # - on SCREEN 1 and 0 this switches between colour and greyscale
        # On an RGB monitor:
        # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
        if self._force_colour:
            # ega ignores colorburst; tandy and pcjr have no mode 5
            self._mode_5 = not colour_on
            self.set_cga4_palette(1)
        else:
            self._mono = self._force_mono or not colour_on


class EGA16ColourMapper(_ColourMapper):
    """EGA 16-colour mapper."""

    #if num_attr == 4
    #    # SCREEN 9 with less than 128k EGA memory
    #    # attribute mapping is different
    #    self._colours = COLOURS16
    #    self._default_palette = EGA4_PALETTE

    _colours = COLOURS16
    default_palette = CGA16_PALETTE


class EGA64ColourMapper(_ColourMapper):
    """EGA 64-colour mapper."""

    _colours = COLOURS64
    default_palette = EGA_PALETTE


class EGA16TextColourMapper(_TextColourMixin, EGA16ColourMapper):
    """EGA 16-colour mapper for text."""

class EGA64TextColourMapper(_TextColourMixin, EGA64ColourMapper):
    """EGA 64-colour mapper for text."""


class MonoTextColourMapper(_ColourMapper):
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
    # Attribute 78h displays as dark green on green.
    #       In fact, depending on timing and on the design of the monitor,
    #       it may have a bright green 'halo' where the dark green and bright green bits meet.
    # Attribute F0h displays as a blinking version of 70h
    #       (if blinking is enabled); as black on bright green otherwise.
    # Attribute F8h displays as a blinking version of 78h
    #       (if blinking is enabled); as dark green on bright green otherwise.

    # see also http://support.microsoft.com/KB/35148
    # --> archived on https://github.com/jeffpar/kbarchive/tree/master/kb/035/Q35148

    # https://www.pcjs.org/pubs/pc/reference/microsoft/kb/Q44412/

    # this should agree with palettes for EGA mono for COLOR values, see:
    # http://qbhlp.uebergeord.net/screen-statement-details-colors.html

    # EGA mono attributes are actually different on the intermediate, non-standard byte attributes
    # see https://nerdlypleasures.blogspot.com/2014/03/the-monochrome-experience-cga-ega-and.html
    # and http://www.vcfed.org/forum/showthread.php?50674-EGA-Monochrome-Compatibility

    _colours = tuple((_i, _i, _i) for _i in INTENSITY_MDA_MONO)

    @property
    def default_palette(self):
        """Default palette."""
        # this is actually ignored
        # remove after refactoring
        return (0,) * 16

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
        fore_rgb = _adjust_tint(self._colours[fore], self._mono_tint, self._mono)
        back_rgb = _adjust_tint(self._colours[back], self._mono_tint, self._mono)
        return fore_rgb, back_rgb, blink, underline


class EGAMonoColourMapper(_ColourMapper):
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

    default_palette = EGA_MONO_PALETTE
    _colours = tuple((_i, _i, _i) for _i in INTENSITY_EGA_MONO)

    @property
    def num_colours(self):
        """Number of colour values."""
        return len(self._pseudocolours)

    def attr_to_rgb(self, attr, palette):
        """Convert colour attribute to RGB/blink/underline, given a palette."""
        fore, back = self._pseudocolours[palette[attr] % len(self._pseudocolours)]
        # intensity 0, 1, 2 to RGB; apply mono tint
        fore_rgb = _adjust_tint(self._colours[fore], self._mono_tint, self._mono)
        back_rgb = _adjust_tint(self._colours[back], self._mono_tint, self._mono)
        # fore, back, blink, underline
        return fore_rgb, back_rgb, fore != back, False
