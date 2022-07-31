"""
PC-BASIC - data package
UCP codepage loader

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import binascii

from ..compat import unichr

from .resources import get_data, listdir

CODEPAGE_DIR = u'codepages'
CODEPAGE_PATTERN = u'{path}/{name}.ucp'
CODEPAGES = [
    name.split(u'.', 1)[0]
    for name in listdir(CODEPAGE_DIR)
    if name.lower().endswith(u'.ucp')
]


def read_codepage(codepage_name):
    """Read a codepage file and convert to codepage dict."""
    codepage = {}
    for line in get_data(CODEPAGE_PATTERN, path=CODEPAGE_DIR, name=codepage_name).splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == b'#'):
            continue
        # strip off comments; split unicodepoint and hex string
        splitline = line.split(b'#')[0].split(b':')
        # ignore malformed lines
        if len(splitline) < 2:
            continue
        try:
            # extract codepage point
            cp_point = binascii.unhexlify(splitline[0].strip())
            # allow sequence of code points separated by commas
            grapheme_cluster = u''.join(
                unichr(int(ucs_str.strip(), 16)) for ucs_str in splitline[1].split(b',')
            )
            codepage[cp_point] = grapheme_cluster
        except (ValueError, TypeError):
            logging.warning('Could not parse line in codepage file: %s', repr(line))
    return codepage
