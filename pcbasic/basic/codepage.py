"""
PC-BASIC - codepage.py
Codepage conversions

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unicodedata
import logging
import os

from six import iteritems, int2byte, unichr


# characters in the printable ASCII range 0x20-0x7E cannot be redefined
# but can have their glyphs subsituted - they will work and transcode as the
# ASCII but show as the subsitute glyph. Used e.g. for YEN SIGN in Shift-JIS
# see http://www.siao2.com/2005/09/17/469941.aspx
PRINTABLE_ASCII = tuple(int2byte(_c) for _c in range(0x20, 0x7F))

# on the terminal, these values are not shown as special graphic chars but as their normal effect
# BEL, TAB, LF, HOME, CLS, CR, RIGHT, LEFT, UP, DOWN  (and not BACKSPACE)
CONTROL = (b'\x07', b'\x09', b'\x0A', b'\x0B', b'\x0C', b'\x0D', b'\x1C', b'\x1D', b'\x1E', b'\x1F')

# default is codepage 437
DEFAULT_CODEPAGE = {int2byte(_i): _c for _i, _c in enumerate(
    u'\x00\u263a\u263b\u2665\u2666\u2663\u2660\u2022\u25d8\u25cb\u25d9\u2642\u2640\u266a\u266b'
    u'\u263c\u25ba\u25c4\u2195\u203c\xb6\xa7\u25ac\u21a8\u2191\u2193\u2192\u2190\u221f\u2194\u25b2'
    u'\u25bc!"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrst'
    u'uvwxyz{|}~\u2302\xc7\xfc\xe9\xe2\xe4\xe0\xe5\xe7\xea\xeb\xe8\xef\xee\xec\xc4\xc5\xc9\xe6\xc6'
    u'\xf4\xf6\xf2\xfb\xf9\xff\xd6\xdc\xa2\xa3\xa5\u20a7\u0192\xe1\xed\xf3\xfa\xf1\xd1\xaa\xba\xbf'
    u'\u2310\xac\xbd\xbc\xa1\xab\xbb\u2591\u2592\u2593\u2502\u2524\u2561\u2562\u2556\u2555\u2563'
    u'\u2551\u2557\u255d\u255c\u255b\u2510\u2514\u2534\u252c\u251c\u2500\u253c\u255e\u255f\u255a'
    u'\u2554\u2569\u2566\u2560\u2550\u256c\u2567\u2568\u2564\u2565\u2559\u2558\u2552\u2553\u256b'
    u'\u256a\u2518\u250c\u2588\u2584\u258c\u2590\u2580\u03b1\xdf\u0393\u03c0\u03a3\u03c3\xb5\u03c4'
    u'\u03a6\u0398\u03a9\u03b4\u221e\u03c6\u03b5\u2229\u2261\xb1\u2265\u2264\u2320\u2321\xf7\u2248'
    u'\xb0\u2219\xb7\u221a\u207f\xb2\u25a0\xa0'
)}


###############################################################################
# codepages

class Codepage(object):
    """Codepage tables."""

    def __init__(self, codepage_dict=None, box_protect=True):
        """Load and initialise codepage tables."""
        # is the current codepage a double-byte codepage?
        self.dbcs = False
        # load codepage (overrides the above)
        self._load(codepage_dict or DEFAULT_CODEPAGE)
        # protect box drawing sequences under dbcs?
        self.box_protect = box_protect

    def _load(self, codepage_dict):
        """Load codepage to Unicode dict."""
        # lead and trail bytes
        self.lead = set()
        self.trail = set()
        self.box_left = [set(), set()]
        self.box_right = [set(), set()]
        self.cp_to_unicode = {}
        self.dbcs_num_chars = 0
        for cp_point, grapheme_cluster in iteritems(codepage_dict):
            # do not redefine printable ASCII, but substitute glyphs
            if (
                    cp_point in PRINTABLE_ASCII and
                    (len(grapheme_cluster) > 1 or ord(grapheme_cluster) != ord(cp_point))
                ):
                ascii_cp = unichr(ord(cp_point))
                self.cp_to_unicode[cp_point] = ascii_cp
            else:
                self.cp_to_unicode[cp_point] = grapheme_cluster
            # track lead and trail bytes
            if len(cp_point) == 2:
                self.lead.add(cp_point[0])
                self.trail.add(cp_point[1])
                self.dbcs_num_chars += 1
            # track box drawing chars
            else:
                for i in (0, 1):
                    if grapheme_cluster in box_left_unicode[i]:
                        self.box_left[i].add(cp_point[0])
                    if grapheme_cluster in box_right_unicode[i]:
                        self.box_right[i].add(cp_point[0])
        # fill up any undefined 1-byte codepoints
        for c in range(256):
            if int2byte(c) not in self.cp_to_unicode:
                self.cp_to_unicode[int2byte(c)] = u'\0'
        self.unicode_to_cp = dict((reversed(item) for item in iteritems(self.cp_to_unicode)))
        if self.dbcs_num_chars > 0:
            self.dbcs = True

    def connects(self, c, d, bset):
        """Return True if c and d connect according to box-drawing set bset."""
        return c in self.box_right[bset] and d in self.box_left[bset]

    def from_unicode(self, uc, errors='ignore'):
        """Convert normalised unicode grapheme cluster to codepage char sequence."""
        # pass through eascii clusters
        if uc and uc[0] == u'\0':
            return b''.join(int2byte(min(255, ord(c))) for c in uc)
        # bring cluster on C normal form (combine what can be combined)
        if len(uc) > 1:
            uc = unicodedata.normalize('NFC', uc)
        try:
            # try to codepage-encode the unicode char
            return self.unicode_to_cp[uc]
        except KeyError:
            # pass control sequences as ascii. this includes \r.
            # control sequences are not in the dictionary
            # because it holds their graphical replacement characters.
            # ignore everything else (unicode chars not in codepage)
            return uc.encode('ascii', errors=errors)

    def str_from_unicode(self, ucs, errors='ignore'):
        """Convert unicode string to codepage string."""
        return b''.join(self.from_unicode(uc, errors=errors) for uc in split_graphemes(ucs))

    def to_unicode(self, cp, replace=u''):
        """Convert codepage point to unicode grapheme cluster """
        return self.cp_to_unicode.get(cp, replace)

    def str_to_unicode(self, cps, preserve=b'', box_protect=True):
        """Convert codepage string to unicode string."""
        return Converter(self, preserve, box_protect).to_unicode(cps, flush=True)

    def get_converter(self, preserve=b''):
        """Get converter from codepage to unicode."""
        return Converter(self, preserve, self.box_protect)


########################################
# box drawing protection

# left-connecting box drawing chars [ single line, double line ]
box_left_unicode = [u'\u2500', u'\u2550']

# right-connecting box drawing chars [ single line, double line ]
box_right_unicode = [u'\u2500', u'\u2550']

# left-connecting
## single line:
# 0x2500, 0x252c, 0x2534, 0x253c, 0x2510, 0x2518, 0x2524,
# mixed single / double
# 0x2556, 0x255c, 0x2562, 0x2565, 0x2568, 0x256b, 0x256e,
# dotted lines
# 0x2504, 0x2508, 0x254c,
# mixed thick / thin line
# 0x251a, 0x2526, 0x2527, 0x2528, 0x252e, 0x2530, 0x2532, 0x2536, 0x2538, 0x253a, 0x253e,
# 0x2540, 0x2541, 0x2542, 0x2544, 0x2546, 0x254a, 0x257c
# rounded corners and half-lines
# 0x256f, 0x2574,
## double line:
# 0x2550, 0x2566, 0x2569, 0x256c,0x2557, 0x255d, 0x2563,
# mixed single / double line
# 0x2555, 0x255b, 0x2561, 0x2564, 0x2567, 0x256a,

# right-connecting
# single line
## 0x2500, 0x252c, 0x2534, 0x253c,
## 0x250c, 0x2514, 0x251c,
# dotted
# 0x2504, 0x2508,
# mixed
# 0x2516, 0x251e, 0x251f, 0x2520, 0x252d,
# 0x2530, 0x2531, 0x2535, 0x2538, 0x2539, 0x253d,
# 0x2540, 0x2541, 0x2542, 0x2543, 0x2545, 0x2549, 0x254c,
# 0x2553, 0x2559, 0x255f, 0x2565, 0x2568, 0x256b, 0x256d, 0x2570, 0x2576, 0x257e
# double line
## 0x2550, 0x2566, 0x2569, 0x256c,
## 0x2554, 0x255a, 0x2560,
# 0x2552, 0x2558, 0x255e, 0x2564, 0x2567, 0x256a,


##################################################
# conversion with box protection

class Converter(object):
    """Buffered converter to Unicode - supports DBCS and box-drawing protection."""

    def __init__(self, codepage, preserve=b'', box_protect=None):
        """Initialise with empty buffer."""
        self._cp = codepage
        # hold one or two bytes
        # lead byte without trail byte, or box-protectable dbcs
        self._buf = b''
        self._preserve = set(preserve)
        # may override box protection defaults
        self._box_protect = box_protect or self._cp.box_protect
        self._dbcs = self._cp.dbcs
        self._bset = -1
        self._last = b''

    def mark(self, s, flush=False):
        """Process codepage string, returning list of grouped code sequences when ready."""
        if not self._dbcs:
            # stateless if not dbcs
            return list(s)
        else:
            unistr = [seq for c in s for seq in self._process(c)]
            if flush:
                unistr += self._flush()
            return unistr

    def to_unicode(self, s, flush=False):
        """Process codepage string, returning unicode string when ready."""
        return u''.join(
            (
                seq.decode('ascii', errors='ignore')
                if (seq in self._preserve)
                else self._cp.to_unicode(seq)
            )
            for seq in self.mark(s, flush)
        )

    def _flush(self, num=None):
        """Empty buffer and return contents."""
        out = []
        if num is None:
            num = len(self._buf)
        if self._buf:
            # can be one or two-byte sequence in self._buf
            out.append(self._buf[:num])
        self._buf = self._buf[num:]
        return out

    def _process(self, c):
        """Process a single char, returning unicode char sequences when ready """
        if not self._box_protect:
            return self._process_nobox(c)
        out = []
        if c in self._preserve:
            # control char; flush buffer as SBCS and add control char unchanged
            out += self._flush() + [c]
            self._bset = -1
            self._last = b''
        elif self._bset == -1:
            if not self._buf:
                out += self._process_case0(c)
            elif len(self._buf) == 1:
                out += self._process_case1(c)
            elif len(self._buf) == 2:
                out += self._process_case2(c)
            else:
                # not allowed
                logging.debug(b'DBCS buffer corrupted: %d %s', self._bset, repr(self._buf))
        elif len(self._buf) == 2:
            out += self._process_case3(c)
        elif not self._buf:
            out += self._process_case4(c)
        else:
            # not allowed
            logging.debug(b'DBCS buffer corrupted: %d %s', self._bset, repr(self._buf))
        return out

    def _process_nobox(self, c):
        """Process a single char, no box drawing protection """
        out = []
        if c in self._preserve:
            # control char; flush buffer as SBCS and add control char unchanged
            out += self._flush() + [c]
            return out
        elif self._buf:
            if c in self._cp.trail:
                # add a DBCS character
                self._buf += c
                out += self._flush()
                return out
            else:
                # flush buffer
                out += self._flush()
        if c in self._cp.lead:
            self._buf = c
        else:
            out.append(c)
        return out

    def _process_case0(self, c):
        """Process a single char with box drawing protection; case 0, starting point """
        out = []
        if c not in self._cp.lead:
            out.append(c)
            # goes to case 0
        else:
            self._buf += c
            # goes to case 1
        return out

    def _process_case1(self, c):
        """Process a single char with box drawing protection; case 1 """
        out = []
        if c not in self._cp.trail:
            out += self._flush() + [c]
            # goes to case 0
        else:
            for bset in (0, 1):
                if self._cp.connects(self._buf, c, bset):
                    self._bset = bset
                    self._buf += c
                    break
                    # goes to case 3
            else:
                # no connection
                self._buf += c
                # goes to case 2
        return out

    def _process_case2(self, c):
        """Process a single char with box drawing protection; case 2 """
        out = []
        if c not in self._cp.lead:
            out += self._flush() + [c]
            # goes to case 0
        else:
            for bset in (0, 1):
                if self._cp.connects(self._buf[-1], c, bset):
                    self._bset = bset
                    # take out only first byte
                    out += self._flush(1)
                    self._buf += c
                    break
                    # goes to case 3
            else:
                # no connection found
                out += self._flush()
                self._buf += c
                # goes to case 1
        return out

    def _process_case3(self, c):
        """Process a single char with box drawing protection; case 3 """
        out = []
        if c not in self._cp.lead:
            out += self._flush() + [c]
        elif self._cp.connects(self._buf[-1], c, self._bset):
            self._last = self._buf[-1]
            # output box drawing
            out += self._flush(1) + self._flush(1) + [c]
            # goes to case 4
        else:
            out += self._flush()
            self._buf = c
            self._bset = -1
            # goes to case 1
        return out

    def _process_case4(self, c):
        """Process a single char with box drawing protection; case 4, continuing box drawing """
        out = []
        if c not in self._cp.lead:
            out.append(c)
            # goes to case 0
        elif self._cp.connects(self._last, c, self._bset):
            self._last = c
            out.append(c)
            # goes to case 4
        else:
            self._buf += c
            self._bset = -1
            # goes to case 1
        return out


##################################################
# grapheme cluster boundaries

class BaseInterval(object):
    """Implement a contiguous interval of integers."""

    def __init__(self, lower, upper=None):
        """Initialise the interval. Lower bound is inclusive, upper is exlusive."""
        self._lower = lower
        self._upper = upper if upper is not None else lower+1

    def __contains__(self, value):
        """Implement the `in` operator."""
        return self._lower <= value < self._upper


class Interval(BaseInterval):
    """Implement a non-contiguous interval of integers."""

    def __init__(self, base_intervals):
        """Initialise from tuples as a sequence of contiguous intervals."""
        self._base_intervals = tuple(BaseInterval(*bounds) for bounds in base_intervals)

    def __contains__(self, value):
        """Implement the `in` operator."""
        return any(value in base for base in self._base_intervals)


# sets of code points by grapheme break property
# http://www.unicode.org/Public/UCD/latest/ucd/auxiliary/GraphemeBreakProperty.txt
GRAPHEME_BREAK = {
    'LF': Interval(((10,),)),
    'CR': Interval(((13,),)),
    'Regional_Indicator': Interval(((127462, 127488),)),
    'Control': Interval((
        (0, 10), (11, 13), (14, 32), (127, 160), (173,),
        (1536, 1542), (1564,), (1757,), (1807,), (6158,),
        (8203,), (8206, 8208), (8232, 8239), (8288, 8304),
        (55296, 57344), (65279,), (65520, 65532), (69821,),
        (113824, 113828), (119155, 119163), (917504, 917760),
        (918000, 921600)
    )),
    'Extend': Interval((
        (768, 880), (1155, 1162),
        (1425, 1470), (1471,), (1473, 1475), (1476, 1478), (1479,),
        (1552, 1563), (1611, 1632), (1648,), (1750, 1757),
        (1759, 1765), (1767, 1769), (1770, 1774), (1809,),
        (1840, 1867), (1958, 1969), (2027, 2036), (2070, 2074),
        (2075, 2084), (2085, 2088), (2089, 2094),
        (2137, 2140), (2275, 2307), (2362,), (2364,), (2369, 2377),
        (2381,), (2385, 2392), (2402, 2404), (2433,), (2492,), (2494,),
        (2497, 2501), (2509,), (2519,), (2530, 2532), (2561, 2563),
        (2620,), (2625, 2627), (2631, 2633), (2635, 2638), (2641,),
        (2672, 2674), (2677,), (2689, 2691), (2748,), (2753, 2758),
        (2759, 2761), (2765,), (2786, 2788), (2817,), (2876,),
        (2878, 2880), (2881, 2885), (2893,), (2902, 2904),
        (2914, 2916), (2946,), (3006,), (3008,), (3021,), (3031,), (3072,),
        (3134, 3137), (3142, 3145), (3146, 3150), (3157, 3159),
        (3170, 3172), (3201,), (3260,), (3263,), (3266,), (3270,),
        (3276, 3278), (3285, 3287), (3298, 3300), (3329,), (3390,),
        (3393, 3397), (3405,), (3415,), (3426, 3428), (3530,), (3535,),
        (3538, 3541), (3542,), (3551,), (3633,), (3636, 3643),
        (3655, 3663), (3761,), (3764, 3770), (3771, 3773),
        (3784, 3790), (3864, 3866), (3893,), (3895,), (3897,),
        (3953, 3967), (3968, 3973), (3974, 3976), (3981, 3992),
        (3993, 4029), (4038,), (4141, 4145), (4146, 4152),
        (4153, 4155), (4157, 4159), (4184, 4186), (4190, 4193),
        (4209, 4213), (4226,), (4229, 4231), (4237,), (4253,),
        (4957, 4960), (5906, 5909), (5938, 5941), (5970, 5972),
        (6002, 6004), (6068, 6070), (6071, 6078), (6086,),
        (6089, 6100), (6109,), (6155, 6158), (6313,), (6432, 6435),
        (6439, 6441), (6450,), (6457, 6460), (6679, 6681), (6683,),
        (6742,), (6744, 6751), (6752,), (6754,), (6757, 6765),
        (6771, 6781), (6783,), (6832, 6847), (6912, 6916), (6964,),
        (6966, 6971), (6972,), (6978,), (7019, 7028), (7040, 7042),
        (7074, 7078), (7080, 7082), (7083, 7086), (7142,),
        (7144, 7146), (7149,), (7151, 7154), (7212, 7220),
        (7222, 7224), (7376, 7379), (7380, 7393), (7394, 7401),
        (7405,), (7412,), (7416, 7418), (7616, 7670),
        (7676, 7680), (8204, 8206), (8400, 8433), (11503, 11506),
        (11647,), (11744, 11776), (12330, 12336), (12441, 12443),
        (42607, 42611), (42612, 42622), (42654, 42656),
        (42736, 42738), (43010,), (43014,), (43019,), (43045, 43047),
        (43204,), (43232, 43250), (43302, 43310), (43335, 43346),
        (43392, 43395), (43443,), (43446, 43450), (43452,), (43493,),
        (43561, 43567), (43569, 43571), (43573, 43575), (43587,),
        (43596,), (43644,), (43696,), (43698, 43701), (43703, 43705),
        (43710, 43712), (43713,), (43756, 43758), (43766,), (44005,),
        (44008,), (44013,), (64286,), (65024, 65040), (65056, 65072),
        (65438, 65440), (66045,), (66272,), (66422, 66427), (68097, 68100),
        (68101, 68103), (68108, 68112), (68152, 68155),
        (68159,), (68325, 68327), (69633,), (69688, 69703), (69759, 69762),
        (69811, 69815), (69817, 69819), (69888, 69891),
        (69927, 69932), (69933, 69941), (70003,), (70016, 70018),
        (70070, 70079), (70090, 70093), (70191, 70194), (70196,),
        (70198, 70200), (70367,), (70371, 70379), (70400, 70402),
        (70460,), (70462,), (70464,), (70487,), (70502, 70509), (70512, 70517),
        (70832,), (70835, 70841), (70842,), (70845,), (70847, 70849),
        (70850, 70852), (71087,), (71090, 71094), (71100, 71102),
        (71103, 71105), (71132, 71134), (71219, 71227),
        (71229,), (71231, 71233), (71339,), (71341,), (71344, 71350),
        (71351,), (71453, 71456), (71458, 71462), (71463, 71468),
        (92912, 92917), (92976, 92983), (94095, 94099),
        (113821, 113823), (119141,), (119143, 119146), (119150, 119155),
        (119163, 119171), (119173, 119180), (119210, 119214),
        (119362, 119365), (121344, 121399), (121403, 121453),
        (121461,), (121476,), (121499, 121504), (121505, 121520),
        (125136, 125143), (917760, 918000)
    )),
    'SpacingMark': Interval((
        (2307,), (2363,), (2366, 2369), (2377, 2381),
        (2382, 2384), (2434, 2436), (2495, 2497), (2503, 2505),
        (2507, 2509), (2563,), (2622, 2625), (2691,), (2750, 2753),
        (2761,), (2763, 2765), (2818, 2820), (2880,), (2887, 2889),
        (2891, 2893), (3007,), (3009, 3011), (3014, 3017),
        (3018, 3021), (3073, 3076), (3137, 3141), (3202, 3204),
        (3262,), (3264, 3266), (3267, 3269), (3271, 3273),
        (3274, 3276), (3330, 3332), (3391, 3393), (3398, 3401),
        (3402, 3405), (3458, 3460), (3536, 3538),
        (3544, 3551), (3570, 3572), (3635,), (3763,), (3902, 3904),
        (3967,), (4145,), (4155, 4157), (4182, 4184), (4228,), (6070,),
        (6078, 6086), (6087, 6089), (6435, 6439), (6441, 6444),
        (6448, 6450), (6451, 6457), (6681, 6683), (6741,),
        (6743,), (6765, 6771), (6916,), (6965,), (6971,), (6973, 6978),
        (6979, 6981), (7042,), (7073,), (7078, 7080), (7082,), (7143,),
        (7146, 7149), (7150,), (7154, 7156), (7204, 7212),
        (7220, 7222), (7393,), (7410, 7412), (43043, 43045),
        (43047,), (43136, 43138), (43188, 43204), (43346, 43348),
        (43395,), (43444, 43446), (43450, 43452), (43453, 43457),
        (43567, 43569), (43571, 43573), (43597,), (43755,), (43758, 43760),
        (43765,), (44003, 44005), (44006, 44008), (44009, 44011),
        (44012,), (69632,), (69634,), (69762,), (69808, 69811),
        (69815, 69817), (69932,), (70018,), (70067, 70070), (70079, 70081),
        (70188, 70191), (70194, 70196), (70197,), (70368, 70371),
        (70402, 70404), (70463,), (70465, 70469), (70471, 70473),
        (70475, 70478), (70498, 70500), (70833, 70835),
        (70841,), (70843, 70845), (70846,), (70849,), (71088, 71090),
        (71096, 71100), (71102,), (71216, 71219), (71227, 71229),
        (71230,), (71340,), (71342, 71344), (71350,), (71456, 71458),
        (71462,), (94033, 94079), (119142,), (119149,)
    )),
    'V': Interval(((4448, 4520), (55216, 55239))),
    'L': Interval(((4352, 4448), (43360, 43389))),
    'T': Interval(((4520, 4608), (55243, 55292))),
    'LV': Interval((
        (44032,), (44060,), (44088,), (44116,), (44144,), (44172,), (44200,),
        (44228,), (44256,), (44284,), (44312,), (44340,), (44368,), (44396,),
        (44424,), (44452,), (44480,), (44508,), (44536,), (44564,), (44592,),
        (44620,), (44648,), (44676,), (44704,), (44732,), (44760,), (44788,),
        (44816,), (44844,), (44872,), (44900,), (44928,), (44956,), (44984,),
        (45012,), (45040,), (45068,), (45096,), (45124,), (45152,), (45180,),
        (45208,), (45236,), (45264,), (45292,), (45320,), (45348,), (45376,),
        (45404,), (45432,), (45460,), (45488,), (45516,), (45544,), (45572,),
        (45600,), (45628,), (45656,), (45684,), (45712,), (45740,), (45768,),
        (45796,), (45824,), (45852,), (45880,), (45908,), (45936,), (45964,),
        (45992,), (46020,), (46048,), (46076,), (46104,), (46132,), (46160,),
        (46188,), (46216,), (46244,), (46272,), (46300,), (46328,), (46356,),
        (46384,), (46412,), (46440,), (46468,), (46496,), (46524,), (46552,),
        (46580,), (46608,), (46636,), (46664,), (46692,), (46720,), (46748,),
        (46776,), (46804,), (46832,), (46860,), (46888,), (46916,), (46944,),
        (46972,), (47000,), (47028,), (47056,), (47084,), (47112,), (47140,),
        (47168,), (47196,), (47224,), (47252,), (47280,), (47308,), (47336,),
        (47364,), (47392,), (47420,), (47448,), (47476,), (47504,), (47532,),
        (47560,), (47588,), (47616,), (47644,), (47672,), (47700,), (47728,),
        (47756,), (47784,), (47812,), (47840,), (47868,), (47896,), (47924,),
        (47952,), (47980,), (48008,), (48036,), (48064,), (48092,), (48120,),
        (48148,), (48176,), (48204,), (48232,), (48260,), (48288,), (48316,),
        (48344,), (48372,), (48400,), (48428,), (48456,), (48484,), (48512,),
        (48540,), (48568,), (48596,), (48624,), (48652,), (48680,), (48708,),
        (48736,), (48764,), (48792,), (48820,), (48848,), (48876,), (48904,),
        (48932,), (48960,), (48988,), (49016,), (49044,), (49072,), (49100,),
        (49128,), (49156,), (49184,), (49212,), (49240,), (49268,), (49296,),
        (49324,), (49352,), (49380,), (49408,), (49436,), (49464,), (49492,),
        (49520,), (49548,), (49576,), (49604,), (49632,), (49660,), (49688,),
        (49716,), (49744,), (49772,), (49800,), (49828,), (49856,), (49884,),
        (49912,), (49940,), (49968,), (49996,), (50024,), (50052,), (50080,),
        (50108,), (50136,), (50164,), (50192,), (50220,), (50248,), (50276,),
        (50304,), (50332,), (50360,), (50388,), (50416,), (50444,), (50472,),
        (50500,), (50528,), (50556,), (50584,), (50612,), (50640,), (50668,),
        (50696,), (50724,), (50752,), (50780,), (50808,), (50836,), (50864,),
        (50892,), (50920,), (50948,), (50976,), (51004,), (51032,), (51060,),
        (51088,), (51116,), (51144,), (51172,), (51200,), (51228,), (51256,),
        (51284,), (51312,), (51340,), (51368,), (51396,), (51424,), (51452,),
        (51480,), (51508,), (51536,), (51564,), (51592,), (51620,), (51648,),
        (51676,), (51704,), (51732,), (51760,), (51788,), (51816,), (51844,),
        (51872,), (51900,), (51928,), (51956,), (51984,), (52012,), (52040,),
        (52068,), (52096,), (52124,), (52152,), (52180,), (52208,), (52236,),
        (52264,), (52292,), (52320,), (52348,), (52376,), (52404,), (52432,),
        (52460,), (52488,), (52516,), (52544,), (52572,), (52600,), (52628,),
        (52656,), (52684,), (52712,), (52740,), (52768,), (52796,), (52824,),
        (52852,), (52880,), (52908,), (52936,), (52964,), (52992,), (53020,),
        (53048,), (53076,), (53104,), (53132,), (53160,), (53188,), (53216,),
        (53244,), (53272,), (53300,), (53328,), (53356,), (53384,), (53412,),
        (53440,), (53468,), (53496,), (53524,), (53552,), (53580,), (53608,),
        (53636,), (53664,), (53692,), (53720,), (53748,), (53776,), (53804,),
        (53832,), (53860,), (53888,), (53916,), (53944,), (53972,), (54000,),
        (54028,), (54056,), (54084,), (54112,), (54140,), (54168,), (54196,),
        (54224,), (54252,), (54280,), (54308,), (54336,), (54364,), (54392,),
        (54420,), (54448,), (54476,), (54504,), (54532,), (54560,), (54588,),
        (54616,), (54644,), (54672,), (54700,), (54728,), (54756,), (54784,),
        (54812,), (54840,), (54868,), (54896,), (54924,), (54952,), (54980,),
        (55008,), (55036,), (55064,), (55092,), (55120,), (55148,), (55176,)
    )),
    'LVT': Interval((
        (44033, 44060), (44061, 44088), (44089, 44116),
        (44117, 44144), (44145, 44172), (44173, 44200),
        (44201, 44228), (44229, 44256), (44257, 44284),
        (44285, 44312), (44313, 44340), (44341, 44368),
        (44369, 44396), (44397, 44424), (44425, 44452),
        (44453, 44480), (44481, 44508), (44509, 44536),
        (44537, 44564), (44565, 44592), (44593, 44620),
        (44621, 44648), (44649, 44676), (44677, 44704),
        (44705, 44732), (44733, 44760), (44761, 44788),
        (44789, 44816), (44817, 44844), (44845, 44872),
        (44873, 44900), (44901, 44928), (44929, 44956),
        (44957, 44984), (44985, 45012), (45013, 45040),
        (45041, 45068), (45069, 45096), (45097, 45124),
        (45125, 45152), (45153, 45180), (45181, 45208),
        (45209, 45236), (45237, 45264), (45265, 45292),
        (45293, 45320), (45321, 45348), (45349, 45376),
        (45377, 45404), (45405, 45432), (45433, 45460),
        (45461, 45488), (45489, 45516), (45517, 45544),
        (45545, 45572), (45573, 45600), (45601, 45628),
        (45629, 45656), (45657, 45684), (45685, 45712),
        (45713, 45740), (45741, 45768), (45769, 45796),
        (45797, 45824), (45825, 45852), (45853, 45880),
        (45881, 45908), (45909, 45936), (45937, 45964),
        (45965, 45992), (45993, 46020), (46021, 46048),
        (46049, 46076), (46077, 46104), (46105, 46132),
        (46133, 46160), (46161, 46188), (46189, 46216),
        (46217, 46244), (46245, 46272), (46273, 46300),
        (46301, 46328), (46329, 46356), (46357, 46384),
        (46385, 46412), (46413, 46440), (46441, 46468),
        (46469, 46496), (46497, 46524), (46525, 46552),
        (46553, 46580), (46581, 46608), (46609, 46636),
        (46637, 46664), (46665, 46692), (46693, 46720),
        (46721, 46748), (46749, 46776), (46777, 46804),
        (46805, 46832), (46833, 46860), (46861, 46888),
        (46889, 46916), (46917, 46944), (46945, 46972),
        (46973, 47000), (47001, 47028), (47029, 47056),
        (47057, 47084), (47085, 47112), (47113, 47140),
        (47141, 47168), (47169, 47196), (47197, 47224),
        (47225, 47252), (47253, 47280), (47281, 47308),
        (47309, 47336), (47337, 47364), (47365, 47392),
        (47393, 47420), (47421, 47448), (47449, 47476),
        (47477, 47504), (47505, 47532), (47533, 47560),
        (47561, 47588), (47589, 47616), (47617, 47644),
        (47645, 47672), (47673, 47700), (47701, 47728),
        (47729, 47756), (47757, 47784), (47785, 47812),
        (47813, 47840), (47841, 47868), (47869, 47896),
        (47897, 47924), (47925, 47952), (47953, 47980),
        (47981, 48008), (48009, 48036), (48037, 48064),
        (48065, 48092), (48093, 48120), (48121, 48148),
        (48149, 48176), (48177, 48204), (48205, 48232),
        (48233, 48260), (48261, 48288), (48289, 48316),
        (48317, 48344), (48345, 48372), (48373, 48400),
        (48401, 48428), (48429, 48456), (48457, 48484),
        (48485, 48512), (48513, 48540), (48541, 48568),
        (48569, 48596), (48597, 48624), (48625, 48652),
        (48653, 48680), (48681, 48708), (48709, 48736),
        (48737, 48764), (48765, 48792), (48793, 48820),
        (48821, 48848), (48849, 48876), (48877, 48904),
        (48905, 48932), (48933, 48960), (48961, 48988),
        (48989, 49016), (49017, 49044), (49045, 49072),
        (49073, 49100), (49101, 49128), (49129, 49156),
        (49157, 49184), (49185, 49212), (49213, 49240),
        (49241, 49268), (49269, 49296), (49297, 49324),
        (49325, 49352), (49353, 49380), (49381, 49408),
        (49409, 49436), (49437, 49464), (49465, 49492),
        (49493, 49520), (49521, 49548), (49549, 49576),
        (49577, 49604), (49605, 49632), (49633, 49660),
        (49661, 49688), (49689, 49716), (49717, 49744),
        (49745, 49772), (49773, 49800), (49801, 49828),
        (49829, 49856), (49857, 49884), (49885, 49912),
        (49913, 49940), (49941, 49968), (49969, 49996),
        (49997, 50024), (50025, 50052), (50053, 50080),
        (50081, 50108), (50109, 50136), (50137, 50164),
        (50165, 50192), (50193, 50220), (50221, 50248),
        (50249, 50276), (50277, 50304), (50305, 50332),
        (50333, 50360), (50361, 50388), (50389, 50416),
        (50417, 50444), (50445, 50472), (50473, 50500),
        (50501, 50528), (50529, 50556), (50557, 50584),
        (50585, 50612), (50613, 50640), (50641, 50668),
        (50669, 50696), (50697, 50724), (50725, 50752),
        (50753, 50780), (50781, 50808), (50809, 50836),
        (50837, 50864), (50865, 50892), (50893, 50920),
        (50921, 50948), (50949, 50976), (50977, 51004),
        (51005, 51032), (51033, 51060), (51061, 51088),
        (51089, 51116), (51117, 51144), (51145, 51172),
        (51173, 51200), (51201, 51228), (51229, 51256),
        (51257, 51284), (51285, 51312), (51313, 51340),
        (51341, 51368), (51369, 51396), (51397, 51424),
        (51425, 51452), (51453, 51480), (51481, 51508),
        (51509, 51536), (51537, 51564), (51565, 51592),
        (51593, 51620), (51621, 51648), (51649, 51676),
        (51677, 51704), (51705, 51732), (51733, 51760),
        (51761, 51788), (51789, 51816), (51817, 51844),
        (51845, 51872), (51873, 51900), (51901, 51928),
        (51929, 51956), (51957, 51984), (51985, 52012),
        (52013, 52040), (52041, 52068), (52069, 52096),
        (52097, 52124), (52125, 52152), (52153, 52180),
        (52181, 52208), (52209, 52236), (52237, 52264),
        (52265, 52292), (52293, 52320), (52321, 52348),
        (52349, 52376), (52377, 52404), (52405, 52432),
        (52433, 52460), (52461, 52488), (52489, 52516),
        (52517, 52544), (52545, 52572), (52573, 52600),
        (52601, 52628), (52629, 52656), (52657, 52684),
        (52685, 52712), (52713, 52740), (52741, 52768),
        (52769, 52796), (52797, 52824), (52825, 52852),
        (52853, 52880), (52881, 52908), (52909, 52936),
        (52937, 52964), (52965, 52992), (52993, 53020),
        (53021, 53048), (53049, 53076), (53077, 53104),
        (53105, 53132), (53133, 53160), (53161, 53188),
        (53189, 53216), (53217, 53244), (53245, 53272),
        (53273, 53300), (53301, 53328), (53329, 53356),
        (53357, 53384), (53385, 53412), (53413, 53440),
        (53441, 53468), (53469, 53496), (53497, 53524),
        (53525, 53552), (53553, 53580), (53581, 53608),
        (53609, 53636), (53637, 53664), (53665, 53692),
        (53693, 53720), (53721, 53748), (53749, 53776),
        (53777, 53804), (53805, 53832), (53833, 53860),
        (53861, 53888), (53889, 53916), (53917, 53944),
        (53945, 53972), (53973, 54000), (54001, 54028),
        (54029, 54056), (54057, 54084), (54085, 54112),
        (54113, 54140), (54141, 54168), (54169, 54196),
        (54197, 54224), (54225, 54252), (54253, 54280),
        (54281, 54308), (54309, 54336), (54337, 54364),
        (54365, 54392), (54393, 54420), (54421, 54448),
        (54449, 54476), (54477, 54504), (54505, 54532),
        (54533, 54560), (54561, 54588), (54589, 54616),
        (54617, 54644), (54645, 54672), (54673, 54700),
        (54701, 54728), (54729, 54756), (54757, 54784),
        (54785, 54812), (54813, 54840), (54841, 54868),
        (54869, 54896), (54897, 54924), (54925, 54952),
        (54953, 54980), (54981, 55008), (55009, 55036),
        (55037, 55064), (55065, 55092), (55093, 55120),
        (55121, 55148), (55149, 55176), (55177, 55204)
    ))
}

def _get_grapheme_break(c):
    """Get grapheme break property of unicode char."""
    for key, value in iteritems(GRAPHEME_BREAK):
        if ord(c) in value:
            return key
    # no grapheme break property found
    return ''

def _is_grapheme_boundary(last_c, current_c):
    """Return whether a grapheme boundary occurs between two chars."""
    # see http://bugs.python.org/issue18406
    # and http://www.unicode.org/reports/tr29/#Grapheme_Cluster_Boundaries
    # Break at the start and end of the text.
    if last_c == u'' or current_c == u'':
        return True
    last = _get_grapheme_break(last_c)
    current = _get_grapheme_break(current_c)
    # Don't break within CRLF.
    if last == 'CR' and current == 'LF':
        return False
    # Otherwise break before and after controls (including CR and LF).
    if (last == 'Control' or current == 'Control'):
        return True
    # Don't break Hangul syllable sequences.
    if (last == 'L' and current in ['L', 'V', 'LV', 'LVT']):
        return False
    if (last in ['LV', 'V'] and current in ['V', 'T']):
        return False
    if (last in ['LVT', 'T'] and current == 'T'):
        return False
    # Don't break between regional indicator symbols.
    if (last == 'Regional_Indicator' and current == 'Regional_Indicator'):
        return False
    # Don't break just before Extend characters.
    if current == 'Extend':
        return False
    # Don't break before SpacingMarks.
    if current == 'SpacingMark':
        return False
    # Don't break after Prepend characters.
    if last == 'Prepend':
        return False
    # Otherwise, break everywhere.
    return True

def split_graphemes(ucs):
    """Split unicode string to list of grapheme clusters."""
    # generate pairs do_break, character_after
    split_iter = (
        (_is_grapheme_boundary(a, b), b) for a, b in zip([u''] + list(ucs), list(ucs) + [u''])
    )
    # split string on breaks
    grapheme_list = []
    current_grapheme = u''
    for do_break, after in split_iter:
        if do_break:
            grapheme_list.append(current_grapheme)
            current_grapheme = u''
        current_grapheme += after
    # return all except first element, which is always empty string
    return grapheme_list[1:]
