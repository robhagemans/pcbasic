"""
PC-BASIC - codepage.py
Codepage conversions

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unicodedata
import logging
import codecs
import os
import io

from ..compat import iterchar, iteritems, int2byte, unichr
from ..compat import StreamWrapper, is_readable_text_stream, is_writable_text_stream
from .data import DEFAULT_CODEPAGE

# characters in the printable ASCII range 0x20-0x7E cannot be redefined
# but can have their glyphs subsituted - they will work and transcode as the
# ASCII but show as the subsitute glyph. Used e.g. for YEN SIGN in Shift-JIS
# see http://www.siao2.com/2005/09/17/469941.aspx
PRINTABLE_ASCII = tuple(int2byte(_c) for _c in range(0x20, 0x7F))

# on the terminal, these values are not shown as special graphic chars but as their normal effect
# BEL, TAB, LF, HOME, CLS, CR, RIGHT, LEFT, UP, DOWN  (and not BACKSPACE)
CONTROL = (b'\x07', b'\x09', b'\x0A', b'\x0B', b'\x0C', b'\x0D', b'\x1C', b'\x1D', b'\x1E', b'\x1F')

# left-connecting box drawing chars for two box-character sets (single line, double line)
_BOX_LEFT_UNICODE = (u'\u2500', u'\u2550')

# right-connecting box drawing chars (single line, double line)
_BOX_RIGHT_UNICODE = (u'\u2500', u'\u2550')


# all box-drawing chars
# these were not actually supported by mbcs TSRs and aren't used by PC-BASIC
# but kept here for reference

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


###############################################################################
# codepages

class Codepage(object):
    """Codepage tables."""

    def __init__(self, codepage_dict=None, box_protect=True):
        """Load and initialise codepage tables."""
        codepage_dict = codepage_dict or {
            int2byte(_i): _c
            for _i, _c in enumerate(DEFAULT_CODEPAGE)
        }
        # protect box drawing sequences under dbcs?
        self.box_protect = box_protect
        # lead and trail bytes
        self.lead = set()
        self.trail = set()
        # box-protection sets
        self._box_left = [set(), set()]
        self._box_right = [set(), set()]
        # main dictionary
        self._cp_to_unicode = {}
        # glyph subsitutes for printable ascii
        self._substitutes = {}
        dbcs_num_chars = 0
        for cp_point, unicode_cluster in iteritems(codepage_dict):
            # normalise clusters so we can match later
            unicode_cluster = unicodedata.normalize('NFC', unicode_cluster)
            # do not redefine printable ASCII, but substitute glyphs
            if (
                    cp_point in PRINTABLE_ASCII and
                    (len(unicode_cluster) > 1 or ord(unicode_cluster) != ord(cp_point))
                ):
                ascii_cp = unichr(ord(cp_point))
                self._cp_to_unicode[cp_point] = ascii_cp
                self._substitutes[cp_point] = unicode_cluster
            else:
                self._cp_to_unicode[cp_point] = unicode_cluster
            # track lead and trail bytes
            if len(cp_point) == 2:
                self.lead.add(cp_point[0:1])
                self.trail.add(cp_point[1:2])
                dbcs_num_chars += 1
            # track box drawing chars
            else:
                for i in (0, 1):
                    if unicode_cluster in _BOX_LEFT_UNICODE[i]:
                        self._box_left[i].add(cp_point[0:1])
                    if unicode_cluster in _BOX_RIGHT_UNICODE[i]:
                        self._box_right[i].add(cp_point[0:1])
        # fill up any undefined 1-byte codepoints
        for c in range(256):
            if int2byte(c) not in self._cp_to_unicode:
                self._cp_to_unicode[int2byte(c)] = u'\0'
        self._unicode_to_cp = dict((reversed(_item) for _item in iteritems(self._cp_to_unicode)))
        self._inverse_substitutes = dict((reversed(_item) for _item in iteritems(self._substitutes)))
        # keep set of clusters of more than one unicode code point
        self._unicode_clusters = set(
            _cluster for _cluster in self._unicode_to_cp if len(_cluster) > 1
        )
        # ensure longest sequences get checked first (greedy clustering)
        self._unicode_clusters = list(reversed(sorted(self._unicode_clusters, key=len)))
        # is the current codepage a double-byte codepage?
        self.dbcs = dbcs_num_chars > 0

    def connects(self, c, d, bset):
        """Return True if c and d connect according to box-drawing set bset."""
        return c in self._box_right[bset] and d in self._box_left[bset]

    def _from_unicode(self, uc, errors='ignore'):
        """Convert NFC unicode cluster to codepage char sequence."""
        # pass through eascii clusters
        if uc.startswith(u'\0'):
            return b''.join(int2byte(min(255, ord(c))) for c in uc)
        try:
            return self._inverse_substitutes[uc]
        except KeyError:
            pass
        try:
            # try to codepage-encode the unicode char
            return self._unicode_to_cp[uc]
        except KeyError:
            # pass control sequences as ascii. this includes \r.
            # control sequences are not in the dictionary
            # because it holds their graphical replacement characters.
            # ignore/raise/replace everything else (unicode chars not in codepage)
            return uc.encode('ascii', errors=errors)

    def _split_unicode(self, ucs):
        """Split unicode string into codepage-dependent clusters; preserve e-ascii clusters."""
        # clusters are stored as C normal form (combine what can be combined)
        ucs = unicodedata.normalize('NFC', ucs)
        clusters = []
        while ucs:
            if ucs[0] == u'\0' and ucs[1:2] and ord(ucs[1:2]) < 256:
                # preserve e-ascii clusters
                length = 2
            else:
                # if a cluster is matched, preserve that; otherwise, use single unicode point
                # i.e. if a perceived grapheme cluster is not contained in the codepage
                # it will be passed codepoint-by-codepoint (and likely ignored/raised/replaced)
                length = 1
                for cluster in self._unicode_clusters:
                    if ucs.startswith(cluster):
                        length = len(cluster)
                        break
            clusters.append(ucs[:length])
            ucs = ucs[length:]
        return clusters

    def unicode_to_bytes(self, ucs, errors='ignore'):
        """Convert unicode string to codepage string."""
        return b''.join(self._from_unicode(uc, errors=errors) for uc in self._split_unicode(ucs))

    def codepoint_to_unicode(self, cp, replace=u'', use_substitutes=False):
        """Convert codepage point to unicode grapheme cluster."""
        if use_substitutes and self._substitutes:
            try:
                return self._substitutes[cp]
            except KeyError:
                pass
        return self._cp_to_unicode.get(cp, replace)

    def bytes_to_unicode(self, cps, preserve=(), box_protect=None, use_substitutes=False):
        """Convert codepage string to unicode string."""
        if box_protect is None:
            box_protext = self.box_protect
        return Converter(self, preserve, box_protect, use_substitutes).to_unicode(cps, flush=True)

    def get_converter(self, preserve=(), use_substitutes=False):
        """Get converter from codepage to unicode."""
        return Converter(self, preserve, self.box_protect, use_substitutes=use_substitutes)

    def wrap_output_stream(self, stream, preserve=()):
        """Wrap a stream so that we can write codepage bytes to it."""
        # check for file-like objects that expect unicode, raw output otherwise
        if not is_writable_text_stream(stream):
            return stream
        return OutputStreamWrapper(stream, self, preserve)

    def wrap_input_stream(self, stream, replace_newlines=False):
        """Wrap a stream so that we can read codepage bytes from it."""
        # check for file-like objects that expect unicode, raw output otherwise
        if is_readable_text_stream(stream):
            stream = InputStreamWrapper(stream, self)
        if replace_newlines:
            return NewlineWrapper(stream)
        return stream


##############################################################################
# stream wrappers


class OutputStreamWrapper(StreamWrapper):
    """
    Converter stream wrapper, takes bytes input.
    Stream must be a unicode (text) stream.
    """

    def __init__(self, stream, codepage, preserve=()):
        """Set up codec."""
        self._conv = codepage.get_converter(preserve)
        self._stream = stream

    def write(self, s):
        """Write bytes to codec stream."""
        # decode BASIC bytes --(codepage)-> unicode
        self._stream.write(self._conv.to_unicode(s))


class InputStreamWrapper(StreamWrapper):
    """
    Converter stream wrapper, produces bytes output.
    Stream must be a unicode (text) stream.
    """

    def __init__(self, stream, codepage):
        """Set up codec."""
        self._codepage = codepage
        self._stream = stream
        self._buffer = b''

    def read(self, n=-1):
        """Read n bytes from stream with codepage conversion."""
        if n > len(self._buffer):
            unistr = self._stream.read(n - len(self._buffer))
        elif n == -1:
            unistr = self._stream.read()
        else:
            unistr = u''
        converted = (self._buffer + self._codepage.unicode_to_bytes(unistr, errors='replace'))
        if n < 0:
            output = converted
        else:
            output, self._buffer = converted[:n], converted[n:]
        return output


class NewlineWrapper(StreamWrapper):
    """Replace newlines on input stream. Wraps a bytes stream."""

    def __init__(self, stream):
        """Set up codec."""
        StreamWrapper.__init__(self, stream)
        self._last = b''

    def read(self, n=-1):
        """Read n bytes from stream with codepage conversion."""
        if n == 0:
            return b''
        output = b''
        while n < 0 or len(output) < n:
            new_bytes = self._stream.read(n - len(output))
            # empty means end of file
            if not new_bytes:
                break
            last, self._last = self._last, new_bytes[-1:]
            # absorb CR LF
            if last == b'\r' and new_bytes[:1] == b'\n':
                new_bytes = new_bytes[1:]
            output += new_bytes
        output = output.replace(b'\n', b'\r')
        return output


##################################################
# conversion with box protection

class Converter(object):
    """Buffered converter to Unicode - supports DBCS and box-drawing protection."""

    def __init__(self, codepage, preserve=(), box_protect=None, use_substitutes=False):
        """Initialise with empty buffer."""
        self._cp = codepage
        # hold one or two bytes
        # lead byte without trail byte, or box-protectable dbcs
        self._buf = b''
        # preserve is a tuple/list of bytes that should keep the same ordinal
        # this is mainly for control characters that have alternate graphical symbols
        self._preserve = set(preserve)
        # may override box protection defaults
        self._box_protect = box_protect or self._cp.box_protect
        self._use_substitutes = use_substitutes
        self._dbcs = self._cp.dbcs
        self._bset = -1
        self._last = b''

    def to_unicode(self, s, flush=False):
        """Process codepage string, returning unicode string when ready."""
        return u''.join(self.to_unicode_list(s, flush))

    def to_unicode_list(self, s, flush=False):
        """Convert codepage to list of unicode with fullwidth marked by trailing u''."""
        tuples = ((_seq,) if len(_seq) == 1 else (_seq, b'') for _seq in self._mark(s, flush))
        sequences = (_seq for _tup in tuples for _seq in _tup)
        return [
            (
                _seq.decode('ascii', errors='ignore')
                if (_seq in self._preserve)
                else self._cp.codepoint_to_unicode(_seq, use_substitutes=self._use_substitutes)
            )
            for _seq in sequences
        ]

    def _mark(self, s, flush=False):
        """Convert bytes to list of codepage bytes."""
        if not self._dbcs:
            # stateless if not dbcs
            return list(iterchar(s))
        else:
            sequences = [seq for c in iterchar(s) for seq in self._process(c)]
            if flush:
                sequences += self._flush()
            return sequences

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
            else:  # pragma: no cover
                # not allowed
                logging.debug(b'DBCS buffer corrupted: %d %s', self._bset, repr(self._buf))
        elif len(self._buf) == 2:
            out += self._process_case3(c)
        elif not self._buf:
            out += self._process_case4(c)
        else:  # pragma: no cover
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
                if self._cp.connects(self._buf[-1:], c, bset):
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
        elif self._cp.connects(self._buf[-1:], c, self._bset):
            self._last = self._buf[-1:]
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
