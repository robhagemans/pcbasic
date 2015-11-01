"""
PC-BASIC - video_graphical.py
Graphical interface base class

(c) 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import plat
import video

try:
    import numpy
except ImportError:
    numpy = None

if plat.system == 'Windows':
    # Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
    # see https://bitbucket.org/pygame/pygame/issues/245/wrong-resolution-unless-you-use-ctypes
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        # old versions of Windows don't have this in user32.dll
        pass

# percentage of the screen to leave unused for window decorations etc.
display_slack = 15




class VideoGraphical(video.VideoPlugin):
    """ Graphical video plugin, base class """

    def __init__(self, **kwargs):
        """ Initialise video plugin parameters. """
        video.VideoPlugin.__init__(self)
        # use native pixel sizes
        self.force_native_pixel = kwargs.get('force_native_pixel', False)
        # display dimensions
        self.force_display_size = kwargs.get('force_display_size', None)
        # aspect ratio
        self.aspect = kwargs.get('aspect', (4, 3))
        # border width percentage
        self.border_width = kwargs.get('border_width', 0)
        # start in fullscreen mode
        self.fullscreen = kwargs.get('fullscreen', False)
        # request smooth scaling
        self.smooth = kwargs.get('smooth', False)
        # ignore ALT+F4 and window X button
        self.nokill = kwargs.get('nokill', False)
        # window caption/title
        self.caption = kwargs.get('caption', '')
        # if no composite palette available for this card, ignore.
        self.composite_monitor = kwargs.get('composite_monitor', False)
        # video card to emulate (only used for composite)
        self.composite_card = kwargs.get('composite_card')
        # don't try composite unless our video card supports it
        self.composite_monitor = self.composite_monitor and self.composite_card in composite_640
        # these must be overwritten by child classes
        self.physical_size = None


    ###########################################################################
    # miscellaneous helper functions

    def _find_display_size(self, canvas_x, canvas_y, border_width):
        """ Determine the optimal size for the display. """
        # comply with requested size unless we're fullscreening
        if self.force_display_size and not self.fullscreen:
            return self.force_display_size
        if not self.force_native_pixel:
            # this assumes actual display aspect ratio is wider than 4:3
            # scale y to fit screen
            canvas_y = (1 - display_slack/100.) * (
                        self.physical_size[1] // int(1 + border_width/100.))
            # scale x to match aspect ratio
            canvas_x = (canvas_y * self.aspect[0]) / self.aspect[1]
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
            target = self.aspect[0]/(1.0*self.aspect[1])
            current = xmult*canvas_x / (1.0*ymult*canvas_y)
            # find the absolute multiplicative distance (always > 1)
            best = max(current, target) / min(current, target)
            apx = xmult, ymult
            for mx in range(1, xmult+1):
                my = min(ymult,
                         int(round(mx*canvas_x*self.aspect[1] / (1.0*canvas_y*self.aspect[0]))))
                current = mx*pixel_x / (1.0*my*pixel_y)
                dist = max(current, target) / min(current, target)
                # prefer larger multipliers if distance is equal
                if dist <= best:
                    best = dist
                    apx = mx, my
            return apx[0] * pixel_x, apx[1] * pixel_y


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

def apply_composite_artifacts(src_array, pixels=4):
    """ Process the canvas to apply composite colour artifacts. """
    width, height = src_array.shape
    s = [None]*pixels
    for p in range(pixels):
        s[p] = src_array[p:width:pixels]&(4//pixels)
    for p in range(1,pixels):
        s[0] = s[0]*2 + s[p]
    return numpy.repeat(s[0], pixels, axis=0)
