"""
PC-BASIC - data.codepages
Codepage definition files

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import binascii

from ...compat import resources, unichr


# list of available codepages
CODEPAGES = tuple(
    name.split(u'.', 1)[0]
    for name in resources.contents(__package__)
    if name.lower().endswith('.ucp') and resources.is_resource(__package__, name)
)


def read_codepage(codepage_name):
    """Read a codepage file and convert to codepage dict."""
    codepage_name += '.ucp'
    codepage = {}
    for line in resources.read_binary(__package__, codepage_name).splitlines():
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
