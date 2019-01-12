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


# tinted monochrome monitors
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


# this is actually ignored, see MonoTextMode class
# remove after refactoring
MDA_PALETTE = (0,) * 16


#######################################################################################
# palette

class Palette(object):
    """Colour palette."""

    def __init__(self, queues, mode, capabilities):
        """Initialise palette."""
        self._capabilities = capabilities
        self._queues = queues
        self._mode = mode
        # map from fore/back attr to video adapter colour
        # interpretation is video mode dependent
        self._palette = list(mode.colourmap.default_palette)
        self.submit()

    def init_mode(self, mode):
        """Initialise for new mode."""
        self._mode = mode
        self._palette = list(mode.colourmap.default_palette)
        self.submit()

    def set_all(self, new_palette, force=False):
        """Set the colours for all attributes."""
        if force or self._mode_allows_palette():
            self._palette = list(new_palette)
            self.submit()

    def set_entry(self, index, colour, force=False):
        """Set a new colour for a given attribute."""
        if force or self._mode_allows_palette():
            self._palette[index] = colour
            # in text mode, we'd be setting more than one attribute
            # e.g. all true attributes with this number as foreground or background
            # and attr_to_rgb decides which
            self.submit()

    def submit(self):
        """Submit to interface."""
        # all attributes split into foreground RGB, background RGB, blink and underline
        rgb_table = [
            self._mode.colourmap.attr_to_rgb(_attr, self._palette)
            for _attr in range(self._mode.colourmap.num_attr)
        ]
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_PALETTE, (rgb_table, None)
        ))

    def get_entry(self, index):
        """Retrieve the colour for a given attribute."""
        return self._palette[index]

    def _mode_allows_palette(self):
        """Check if the video mode allows palette change."""
        # effective palette change is an error in CGA
        if self._capabilities in ('cga', 'cga_old', 'mda', 'hercules', 'olivetti'):
            raise error.BASICError(error.IFC)
        # ignore palette changes in Tandy/PCjr SCREEN 0
        elif self._capabilities in ('tandy', 'pcjr') and self._mode.is_text_mode:
            return False
        else:
            return True


###############################################################################
# colour mappers

class ColourMapper(object):
    """Palette and colourset."""

    def __init__(self, has_blink, num_attr, num_colours):
        """Initialise colour mapper."""
        # palette - maps the valid attributes to colour values
        # these are "palette attributes" - e.g. the 16 foreground attributes for text mode.
        self._default_palette = None
        # number of true attribute bytes. This is 256 for text modes.
        self.num_attr = num_attr
        # colour set - maps the valid colour values to RGB
        # can be used as the right hand side of a palette assignment
        # colours is a reference (changes with colorburst on composite)
        self._colours = None
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

    def set_colorburst(self, on):
        """Set the NTSC colorburst bit."""
        # not colourburst capable
        return False


class HerculesColourMapper(ColourMapper):
    """Hercules 16-greyscale palette."""

    def __init__(self, has_blink, num_attr, num_colours):
        """Initialise colour mapper."""
        ColourMapper.__init__(self, has_blink, num_attr, num_colours)
        self._default_palette = CGA2_PALETTE

    #FIXME - not being called
    def set_defaults(self, capabilities, low_intensity, monitor, mono_tint):
        self._colours = tuple(
            tuple(_tint * _int//255 for _tint in mono_tint) for _int in INTENSITY16
        )


class CGAColourMapper(ColourMapper):
    """CGA 2-colour, 16-colour palettes."""

    def __init__(self, has_blink, num_attr, num_colours):
        """Initialise colour mapper."""
        ColourMapper.__init__(self, has_blink, num_attr, num_colours)
        self._force_mono = False
        self._force_colour = False
        self._has_colorburst = False
        self._colours = COLOURS16
        if num_attr == 2:
            self._default_palette = CGA2_PALETTE
        elif num_attr == 16:
            self._default_palette = CGA16_PALETTE
        else:
            raise ValueError

    #FIXME - not being called
    def set_defaults(self, capabilities, low_intensity, monitor, mono_tint):
        """CGA 4-colour palette / mode 5 settings"""
        self._has_colorburst = capabilities in ('cga', 'cga_old', 'pcjr', 'tandy')
        # monochrome
        self._force_mono = monitor == 'mono'
        self._mono_tint = mono_tint
        # rgb monitor
        self._force_colour = monitor not in ('mono', 'composite')

    def set_colorburst(self, on):
        """Set the NTSC colorburst bit."""
        # On a composite monitor with CGA adapter (not EGA, VGA):
        # - on SCREEN 2 this enables artifacting
        # - on SCREEN 1 and 0 this switches between colour and greyscale
        # On an RGB monitor:
        # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
        # - ignored on other screens
        if self._has_colorburst:
            self._toggle_colour(on)

    def _toggle_colour(self, colour_on):
        """Toggle between colour and monochrome (for NTSC colorburst)."""
        if (colour_on and not self._force_mono) or self._force_colour:
            self._colours = COLOURS16
        else:
            # FIXME - should be intensity-mapped CGA colours
            # with potential hue adjustment to ensure all shades are different
            # this is the Hercules palette
            self._colours = tuple(
                tuple(_tint * _int//255 for _tint in self._mono_tint) for _int in INTENSITY16
            )


class CGA4ColourMapper(ColourMapper):
    """CGA 4-colour palettes."""

    def __init__(self, has_blink, num_attr, num_colours):
        """Initialise colour mapper."""
        ColourMapper.__init__(self, has_blink, num_attr, num_colours)
        self._tandy = False
        self._low_intensity = False
        self._has_mode_5 = False
        self._mode_5 = False
        self._has_colorburst = False
        self._force_mono = False
        self._force_colour = True
        # greyscale mono
        self._mono_tint = (255, 255, 255)
        self._palette_number = 1
        self._colours = COLOURS16

    #FIXME - not being called
    def set_defaults(self, capabilities, low_intensity, monitor, mono_tint):
        """CGA 4-colour palette / mode 5 settings"""
        self._has_colorburst = capabilities in ('cga', 'cga_old', 'pcjr', 'tandy')
        # pcjr/tandy does not have mode 5
        self._tandy = capabilities not in ('pcjr', 'tandy')
        self._has_mode_5 = capabilities in ('cga', 'cga_old')
        self._low_intensity = low_intensity
        # start with the cyan-magenta-white palette
        self._palette_number = 1
        self._mode_5 = False
        self._force_mono = monitor == 'mono'
        # rgb monitor
        self._force_colour = monitor not in ('mono', 'composite')
        self._mono_tint = mono_tint

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

    def set_colorburst(self, on):
        """Set the NTSC colorburst bit."""
        if not self._has_colorburst:
            return
        # On a composite monitor with CGA adapter (not EGA, VGA):
        # - on SCREEN 2 this enables artifacting
        # - on SCREEN 1 and 0 this switches between colour and greyscale
        # On an RGB monitor:
        # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
        # - ignored on other screens
        if self._force_colour:
            # ega ignores colorburst; tandy and pcjr have no mode 5
            self._mode_5 = not on
            self.set_cga4_palette(1)
        else:
            self._toggle_colour(on)

    def _toggle_colour(self, colour_on):
        """Toggle between colour and monochrome (for NTSC colorburst)."""
        if (colour_on and not self._force_mono) or self._force_colour:
            self._colours = COLOURS16
        else:
            # FIXME - should be intensity-mapped CGA colours
            # with potential hue adjustment to ensure all shades are different
            # this is the Hercules palette
            self._colours = tuple(
                tuple(_tint * _int//255 for _tint in self._mono_tint) for _int in INTENSITY16
            )


class EGAColourMapper(ColourMapper):
    """EGA 16-colour or 64-colour mapper."""

    def __init__(self, has_blink, num_attr, num_colours):
        """Initialise colour mapper."""
        ColourMapper.__init__(self, has_blink, num_attr, num_colours)
        #if num_attr == 4
        #    # SCREEN 9 with less than 128k EGA memory
        #    # attribute mapping is different
        #    self._colours = COLOURS16
        #    self._default_palette = EGA4_PALETTE
        if num_colours == 16:
            self._colours = COLOURS16
            self._default_palette = CGA16_PALETTE
        elif num_colours == 64:
            self._colours = COLOURS64
            self._default_palette = EGA_PALETTE
        else:
            raise ValueError


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

    def __init__(self, has_blink, num_attr, num_colours):
        """Initialise colour mapper."""
        ColourMapper.__init__(self, has_blink, num_attr, num_colours)
        # greyscale mono
        self._mono_tint = (255, 255, 255)
        self._set_colours()

    #FIXME - not being called
    def set_defaults(self, capabilities, low_intensity, monitor, mono_tint):
        """Palette / mode settings"""
        self._mono_tint = mono_tint
        self._set_colours()

    def _set_colours(self):
        """Calculate tinted monochromes."""
        # initialise tinted monochrome palettes
        self._colours = tuple(
            tuple(tint*i//255 for tint in self._mono_tint) for i in INTENSITY_MDA_MONO
        )

    @property
    def default_palette(self):
        """Default palette."""
        return MDA_PALETTE

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

    def __init__(self, has_blink, num_attr, num_colours):
        """Initialise colour mapper."""
        ColourMapper.__init__(self, has_blink, num_attr, num_colours)
        # greyscale mono
        self._mono_tint = (255, 255, 255)
        self._default_palette = EGA_MONO_PALETTE
        self._set_colours()

    #FIXME - not being called
    def set_defaults(self, capabilities, low_intensity, monitor, mono_tint):
        """Palette / mode settings"""
        self._mono_tint = mono_tint
        self._set_colours()

    def _set_colours(self):
        """Calculate tinted monochromes."""
        self._colours = tuple(
            tuple(tint*i//255 for tint in self._mono_tint) for i in INTENSITY_EGA_MONO
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
